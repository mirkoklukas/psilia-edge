"""Lite mode — minimal camera preview + recording.

No Docker, no ROS. A single FastAPI process opens a UVC camera with
CameraStream, encodes frames as JPEG, and serves them as an MJPEG
multipart stream. Recording dumps the same JPEG bytes to a .mjpg file
(concatenated frames; ffmpeg can read with `-f mjpeg`).

Camera selection happens entirely from the web UI — the CLI just starts
the server. macOS index discovery via cv2 is unreliable enough that
manual selection is the right default everywhere; see hotplug.probe_cv2_cameras.

Lifecycle: blocking foreground command (psilia runtime lite). Ctrl+C
shuts down uvicorn, closes the camera, and finalises any open recording.
"""

from __future__ import annotations

import logging
import socket
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from psilia_edge.utils import read_yaml, write_yaml

import cv2
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from psilia_edge.camera_stream import CameraStream
from psilia_edge.runtime.server import WEB_DIR

logger = logging.getLogger(__name__)


class _LiteState:
    def __init__(self) -> None:
        self.camera: CameraStream | None = None
        self.camera_info: dict = {}
        self.selected_cv_index: int | None = None
        self.data_dir: Path | None = None

        self.lock = threading.Lock()  # protects frame + recording state
        self.cam_lock = threading.Lock()  # serialises camera swaps
        self.latest_jpeg: bytes | None = None
        self.latest_seq: int = 0

        # JPEG quality applied to both the live stream and recording. Higher =
        # bigger files / more bandwidth, less compression artefacts. 100 is the
        # max cv2 supports (JPEG is still lossy at 100 but very close to source).
        self.jpeg_quality: int = 95

        self.recording_fp = None
        self.recording_path: Path | None = None
        self.recording_frames: int = 0
        self.recording_started: float = 0.0

    def on_frame(self, t: float, frame) -> None:
        ok, buf = cv2.imencode(
            ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
        )
        if not ok:
            return
        jpeg = buf.tobytes()
        with self.lock:
            self.latest_jpeg = jpeg
            self.latest_seq += 1
            if self.recording_fp is not None:
                self.recording_fp.write(jpeg)
                self.recording_frames += 1


_state = _LiteState()

app = FastAPI(title="Psilia Lite", docs_url=None, redoc_url=None)


# ── Camera selection ────────────────────────────────────────────────────────


def _resolve_handle(cv_index: int):
    """Convert a cv_index into the cv2 handle for this platform.

    Linux: "/dev/video<N>" (path; works with cv2 + V4L2 backend).
    macOS: int N (passed alongside cv2.CAP_AVFOUNDATION inside CameraStream).
    """
    if sys.platform == "darwin":
        return cv_index
    return f"/dev/video{cv_index}"


def _select_camera(cv_index: int, width: int = 0, height: int = 0) -> dict:
    """Open the camera at cv_index, replacing the current one if any.

    width/height = 0 → open at the camera's default (CameraStream skips
    cap.set() when these are zero). Caller must hold _state.cam_lock.
    Recording must not be active. Returns the new camera_info dict on success.
    """
    handle = _resolve_handle(cv_index)
    new_info = {
        "device": handle,
        "cv_index": cv_index,
        "pixel_format": "MJPG",
        "width": width,
        "height": height,
        "fps": 30,
    }

    new_cam = CameraStream(
        device=handle,
        pixel_format="MJPG",
        width=width,
        height=height,
        fps=0,
        logger=logger,
    )
    new_cam.add_on_capture_callback(_state.on_frame)
    if not new_cam.open():
        raise RuntimeError(f"Failed to open camera at {handle}")

    new_info["width"] = new_cam.width
    new_info["height"] = new_cam.height
    new_info["fps"] = new_cam.fps

    # Tear down the previous camera only after the new one is up so we don't
    # leave the UI without a stream if the new open fails.
    old = _state.camera
    _state.camera = new_cam
    _state.camera_info = new_info
    _state.selected_cv_index = cv_index
    if old is not None:
        old.close()

    logger.info(
        f"Selected camera cv_index={cv_index} ({new_cam.width}x{new_cam.height} @ {new_cam.fps:.1f}fps)"
    )
    return new_info


# ── API routes ──────────────────────────────────────────────────────────────


@app.get("/api/lite/cameras")
def api_cameras() -> JSONResponse:
    from psilia_edge.runtime.hotplug import probe_cv2_cameras

    cams = probe_cv2_cameras()
    sel_idx = _state.selected_cv_index
    sel_w = _state.camera_info.get("width") if sel_idx is not None else None
    sel_h = _state.camera_info.get("height") if sel_idx is not None else None
    for cam in cams:
        cam["selected"] = cam["cv_index"] == sel_idx
    return JSONResponse(
        {
            "cameras": cams,
            "selected": {"cv_index": sel_idx, "width": sel_w, "height": sel_h}
            if sel_idx is not None
            else None,
        }
    )


@app.post("/api/lite/camera/select")
def api_camera_select(cv_index: int, width: int = 0, height: int = 0) -> JSONResponse:
    with _state.lock:
        if _state.recording_fp is not None:
            raise HTTPException(409, "stop recording before changing camera")

    with _state.cam_lock:
        try:
            info = _select_camera(cv_index, width=width, height=height)
        except RuntimeError as e:
            raise HTTPException(500, str(e))

    return JSONResponse(info)


@app.get("/api/lite/status")
def api_status() -> JSONResponse:
    with _state.lock:
        rec_active = _state.recording_fp is not None
        rec = {
            "active": rec_active,
            "path": str(_state.recording_path) if _state.recording_path else None,
            "frames": _state.recording_frames,
            "elapsed_s": (time.time() - _state.recording_started)
            if rec_active
            else 0.0,
        }
    cam = _state.camera
    return JSONResponse(
        {
            "camera": _state.camera_info,
            "selected_cv_index": _state.selected_cv_index,
            "estimated_fps": cam.estimated_fps if cam else None,
            "data_dir": str(_state.data_dir) if _state.data_dir else None,
            "recording": rec,
            "jpeg_quality": _state.jpeg_quality,
        }
    )


@app.post("/api/lite/quality")
def api_quality(value: int) -> JSONResponse:
    if not 1 <= value <= 100:
        raise HTTPException(400, "quality must be in 1..100")
    _state.jpeg_quality = value
    return JSONResponse({"jpeg_quality": _state.jpeg_quality})


@app.get("/api/lite/stream")
def api_stream() -> StreamingResponse:
    boundary = "psilia-lite-frame"
    sep = b"--" + boundary.encode() + b"\r\n"

    def gen():
        last_seq = -1
        while True:
            with _state.lock:
                seq = _state.latest_seq
                jpeg = _state.latest_jpeg
            if jpeg is None or seq == last_seq:
                time.sleep(0.005)
                continue
            last_seq = seq
            yield (
                sep
                + b"Content-Type: image/jpeg\r\n"
                + b"Content-Length: "
                + str(len(jpeg)).encode()
                + b"\r\n\r\n"
                + jpeg
                + b"\r\n"
            )

    return StreamingResponse(
        gen(),
        media_type=f"multipart/x-mixed-replace; boundary={boundary}",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/lite/snapshot")
def api_snapshot():
    with _state.lock:
        jpeg = _state.latest_jpeg
    if jpeg is None:
        raise HTTPException(503, "no frame yet")
    return Response(content=jpeg, media_type="image/jpeg")


def _make_recording_stem(session: str, data_dir: Path) -> str:
    """Build a recording stem matching the ROS recording_node convention.

    Format: {device}_{session}_{counter}_{time}
    e.g.    borne_lab-test_3_2026-05-06_11-39
    """
    device = socket.gethostname().split(".")[0]
    counter = _next_counter(device, session, data_dir)
    when = datetime.now().strftime("%Y-%m-%d_%H-%M")
    return f"{device}_{session}_{counter}_{when}"


def _next_counter(device: str, session: str, data_dir: Path) -> int:
    if not data_dir.exists():
        return 0
    counters = []
    for p in data_dir.glob(f"{device}_{session}_[0-9]*_*"):
        if not p.is_dir():
            continue
        try:
            counters.append(int(p.name.split("_")[2]))
        except (IndexError, ValueError):
            pass
    return max(counters, default=-1) + 1


@app.post("/api/lite/record/start")
def api_record_start(session: str | None = None) -> JSONResponse:
    if _state.data_dir is None:
        raise HTTPException(500, "data_dir not configured")
    if _state.camera is None:
        raise HTTPException(409, "no camera selected")
    with _state.lock:
        if _state.recording_fp is not None:
            raise HTTPException(409, "already recording")
        _state.data_dir.mkdir(parents=True, exist_ok=True)
        stem = _make_recording_stem(session or "session", _state.data_dir)
        rec_dir = _state.data_dir / stem
        rec_dir.mkdir(parents=True, exist_ok=True)
        path = rec_dir / f"{stem}.mjpg"
        _state.recording_fp = open(path, "wb")
        _state.recording_path = path
        _state.recording_frames = 0
        _state.recording_started = time.time()
    logger.info(f"Recording started: {path}")
    return JSONResponse({"path": str(path)})


@app.post("/api/lite/record/stop")
def api_record_stop() -> JSONResponse:
    with _state.lock:
        if _state.recording_fp is None:
            raise HTTPException(409, "not recording")
        path = _state.recording_path
        frames = _state.recording_frames
        elapsed = time.time() - _state.recording_started
        _state.recording_fp.close()
        _state.recording_fp = None
        _state.recording_path = None

    fps = (frames / elapsed) if elapsed > 0 else 0.0
    meta = {
        "frames": frames,
        "duration_s": round(elapsed, 3),
        "fps": round(fps, 2),
        "width": _state.camera_info.get("width"),
        "height": _state.camera_info.get("height"),
        "pixel_format": _state.camera_info.get("pixel_format"),
        "device": str(_state.camera_info.get("device"))
        if _state.camera_info.get("device") is not None
        else None,
        "jpeg_quality": _state.jpeg_quality,
    }
    if path is not None:
        write_yaml(path.parent / "metadata.yaml", meta)
    logger.info(
        f"Recording stopped: {path} ({frames} frames, {elapsed:.1f}s, {fps:.1f} fps)"
    )
    return JSONResponse({"path": str(path), **meta})


def _recording_paths(name: str) -> tuple[Path, Path]:
    """Return (mjpg_path, metadata_path) for a recording directory `name`."""
    if _state.data_dir is None:
        raise HTTPException(500, "data_dir not configured")
    if "/" in name or "\\" in name or ".." in name:
        raise HTTPException(400, "invalid name")
    rec_dir = _state.data_dir / name
    if not rec_dir.is_dir():
        raise HTTPException(404, f"not found: {name}")
    return rec_dir / f"{name}.mjpg", rec_dir / "metadata.yaml"


@app.get("/api/lite/recordings")
def api_recordings() -> JSONResponse:
    if _state.data_dir is None or not _state.data_dir.exists():
        return JSONResponse([])
    out = []
    for d in sorted(
        _state.data_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        if not d.is_dir():
            continue
        mjpg = d / f"{d.name}.mjpg"
        if not mjpg.exists():
            continue
        meta = {}
        meta_path = d / "metadata.yaml"
        if meta_path.exists():
            try:
                meta = read_yaml(meta_path) or {}
            except Exception:
                pass
        out.append(
            {
                "name": d.name,
                "size": mjpg.stat().st_size,
                "mtime": mjpg.stat().st_mtime,
                "frames": meta.get("frames"),
                "duration_s": meta.get("duration_s"),
                "fps": meta.get("fps"),
                "width": meta.get("width"),
                "height": meta.get("height"),
            }
        )
    return JSONResponse(out)


@app.get("/api/lite/recordings/{name}/stream")
def api_recording_stream(name: str) -> StreamingResponse:
    path, meta_path = _recording_paths(name)
    if not path.exists():
        raise HTTPException(404, f"not found: {name}")

    fps = 30.0
    if meta_path.exists():
        try:
            fps = float((read_yaml(meta_path) or {}).get("fps") or 30.0)
        except Exception:
            pass
    fps = max(fps, 1.0)

    boundary = "psilia-lite-playback"
    sep = b"--" + boundary.encode() + b"\r\n"

    def gen():
        data = path.read_bytes()
        offsets = []
        i = 0
        while True:
            j = data.find(b"\xff\xd8\xff", i)
            if j < 0:
                break
            offsets.append(j)
            i = j + 1
        frame_dt = 1.0 / fps
        next_t = time.monotonic()
        for k, s in enumerate(offsets):
            e = offsets[k + 1] if k + 1 < len(offsets) else len(data)
            jpeg = data[s:e]
            # Skip the trailing spurious SOI we sometimes write.
            if len(jpeg) < 1000:
                continue
            yield (
                sep
                + b"Content-Type: image/jpeg\r\n"
                + b"Content-Length: "
                + str(len(jpeg)).encode()
                + b"\r\n\r\n"
                + jpeg
                + b"\r\n"
            )
            next_t += frame_dt
            sleep_t = next_t - time.monotonic()
            if sleep_t > 0:
                time.sleep(sleep_t)

    return StreamingResponse(
        gen(),
        media_type=f"multipart/x-mixed-replace; boundary={boundary}",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Static files (catch-all, must be last).
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="static")


def serve(data_dir: Path, host: str = "0.0.0.0", port: int = 8080) -> None:
    """Run FastAPI in foreground. No camera is opened until the user picks one."""
    _state.data_dir = data_dir
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    finally:
        with _state.cam_lock:
            if _state.camera is not None:
                _state.camera.close()
                _state.camera = None
        with _state.lock:
            if _state.recording_fp is not None:
                _state.recording_fp.close()
                _state.recording_fp = None
