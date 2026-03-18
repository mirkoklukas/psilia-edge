"""Standalone camera capture test.

Verifies that cv2.VideoCapture honors the requested FPS, pixel format,
and resolution. Reports requested vs. configured vs. measured values.

Usage:
    python tests/test_camera_capture.py
    python tests/test_camera_capture.py --device /dev/video0 --fps 15 --frames 60
    python tests/test_camera_capture.py --device /dev/video0 --format YUYV --width 640 --height 480
"""

import argparse
import sys
import time

import cv2


_FOURCC = {
    "MJPG": cv2.VideoWriter_fourcc("M", "J", "P", "G"),
    "YUYV": cv2.VideoWriter_fourcc("Y", "U", "Y", "V"),
}

_FPS_TOLERANCE = 0.15   # 15% — cv2 timer resolution isn't perfect
_DIM_TOLERANCE = 0      # dimensions must match exactly


def parse_args():
    p = argparse.ArgumentParser(description="Camera capture test")
    p.add_argument("--device", default=None, help="Device path, e.g. /dev/video0")
    p.add_argument("--format", dest="pixel_format", default=None, choices=["MJPG", "YUYV"])
    p.add_argument("--width", type=int, default=None)
    p.add_argument("--height", type=int, default=None)
    p.add_argument("--fps", type=int, default=None)
    p.add_argument("--frames", type=int, default=60, help="Frames to capture for FPS measurement")
    return p.parse_args()


def auto_detect():
    """Try to auto-detect a camera via hotplug (Linux only)."""
    try:
        from psilia_edge.runtime.hotplug import pick_camera_device
        cam = pick_camera_device()
        if cam:
            print(f"[auto-detect] found: {cam}")
            return cam
    except ImportError:
        pass
    # Fallback: just try /dev/video0 with defaults
    return {"device": "/dev/video0", "pixel_format": "MJPG", "width": 640, "height": 480, "fps": 30}


def section(title):
    print(f"\n{'─' * 50}")
    print(f"  {title}")
    print(f"{'─' * 50}")


def row(label, requested, configured, measured=None, ok=None):
    r = str(requested)
    c = str(configured)
    m = str(measured) if measured is not None else "—"
    status = ""
    if ok is True:
        status = "✓"
    elif ok is False:
        status = "✗  <-- MISMATCH"
    print(f"  {label:<14}  req={r:<10} cfg={c:<10} meas={m:<10}  {status}")


def main():
    args = parse_args()

    # Resolve config — args override auto-detect
    detected = auto_detect()
    device       = args.device       or detected["device"]
    pixel_format = args.pixel_format or detected.get("pixel_format", "MJPG")
    width        = args.width        or detected.get("width", 640)
    height       = args.height       or detected.get("height", 480)
    fps          = args.fps          or detected.get("fps", 30)
    n_frames     = args.frames

    section("Requested config")
    print(f"  device={device}  format={pixel_format}  {width}x{height}  fps={fps}  measure_over={n_frames} frames")

    # --- Open ---
    section("Opening camera")
    backend = cv2.CAP_V4L2 if sys.platform == "linux" else cv2.CAP_ANY
    cap = cv2.VideoCapture(device, backend)
    if not cap.isOpened():
        print(f"  ERROR: could not open {device}")
        sys.exit(1)
    print(f"  Opened {device}")

    fourcc = _FOURCC.get(pixel_format)
    if fourcc:
        cap.set(cv2.CAP_PROP_FOURCC, fourcc)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    cap.set(cv2.CAP_PROP_FPS, fps)

    # Read back what the driver actually configured
    cfg_fourcc  = int(cap.get(cv2.CAP_PROP_FOURCC))
    cfg_fmt     = "".join(chr((cfg_fourcc >> (8 * i)) & 0xFF) for i in range(4)).strip("\x00")
    cfg_width   = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cfg_height  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cfg_fps     = cap.get(cv2.CAP_PROP_FPS)

    # --- Warmup: discard first few frames (buffered/stale) ---
    section("Warming up (5 frames)")
    for _ in range(5):
        cap.read()

    # --- Capture N frames and time it ---
    section(f"Capturing {n_frames} frames")
    t0 = time.monotonic()
    captured = 0
    for i in range(n_frames):
        ret, frame = cap.read()
        if not ret:
            print(f"  WARNING: failed to read frame {i}")
            break
        captured += 1
        if (i + 1) % 10 == 0:
            elapsed = time.monotonic() - t0
            print(f"  frame {i+1:>4}/{n_frames}  elapsed={elapsed:.2f}s")

    elapsed = time.monotonic() - t0
    measured_fps = captured / elapsed if elapsed > 0 else 0.0

    actual_h, actual_w = frame.shape[:2] if ret else (0, 0)

    cap.release()

    # --- Report ---
    section("Results")

    fps_ok  = abs(measured_fps - fps) / fps <= _FPS_TOLERANCE
    fmt_ok  = cfg_fmt == pixel_format
    dim_ok  = (cfg_width == width) and (cfg_height == height)

    row("pixel format", pixel_format,        cfg_fmt,                              ok=fmt_ok)
    row("resolution",  f"{width}x{height}",  f"{cfg_width}x{cfg_height}",
        f"{actual_w}x{actual_h}",            ok=dim_ok)
    row("fps",         fps,                  f"{cfg_fps:.1f}",
        f"{measured_fps:.2f}",               ok=fps_ok)

    print()
    passed = fps_ok and fmt_ok and dim_ok
    if passed:
        print("  PASS — all checks within tolerance")
    else:
        print("  FAIL — one or more checks failed")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
