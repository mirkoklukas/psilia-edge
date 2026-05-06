"""CameraStream — threaded UVC camera capture.

Threading model
---------------
Two threads interact with this class:

  Capture thread (_capture_loop)
    Runs in the background. Calls cap.read() in a tight loop — this call
    blocks until the camera delivers a frame. On each successful read it
    stores the frame and appends a timestamp, then immediately loops back
    to read the next frame. It never sleeps; the camera's hardware timing
    is the natural throttle.

  Caller thread (open / close / pop_latest_frame / get_latest_timed_frame)
    Any consumer (ROS timer callback, FastAPI route, etc.). It never
    touches cap directly — it only reads _latest_frame via
    pop_latest_frame() or get_latest_timed_frame().

Shared state and synchronisation
---------------------------------
  _frame_lock (threading.Lock)
    Protects _latest_frame and capture_times, written by the capture
    thread and read by the caller thread. The lock is held only for the
    short assignment/append — cap.read() runs outside it so callers are
    never blocked waiting for the camera.

  _stop_event (threading.Event)
    Signals the capture thread to exit cleanly. Set by open() before
    (re)opening — in case a thread from a previous session is still
    running — and by close().

  _cap (cv2.VideoCapture)
    Owned exclusively by the capture thread once open() returns. The
    capture thread sets _cap = None before returning on failure, which
    is the signal that triggers a reopen on the next caller request.

Note: this module is shared between the host-side `lite` mode and the
ROS `camera_node`. A copy currently lives in
`ros/psilia_runtime/psilia_runtime/camera_stream.py` for the in-container
ROS package; consolidate once `psilia-edge` is pip-installed inside the
container.
"""

from __future__ import annotations

import collections
import threading
import time

import cv2


_FOURCC = {
    "MJPG": cv2.VideoWriter_fourcc("M", "J", "P", "G"),
    "YUYV": cv2.VideoWriter_fourcc("Y", "U", "Y", "V"),
}


class CameraStream:
    def __init__(
        self,
        device: str,
        pixel_format: str,
        width: int,
        height: int,
        fps: int,
        logger=None,
    ):
        self.device = device
        self.pixel_format = pixel_format
        self.width = width
        self.height = height
        self.fps = fps
        self._logger = logger

        self._cap = None
        self._latest_frame: tuple | None = None
        self._frame_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._callbacks: list = []

        self.capture_times: collections.deque = collections.deque(maxlen=256)

    def open(self) -> bool:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

        # On macOS, force the AVFoundation backend so integer device indices
        # map to AVCaptureDevice indices rather than whatever CAP_ANY defaults to.
        import sys

        if sys.platform == "darwin":
            cap = cv2.VideoCapture(self.device, cv2.CAP_AVFOUNDATION)
        else:
            cap = cv2.VideoCapture(self.device)
        if not cap.isOpened():
            self._log_warn(f"Could not open camera device: {self.device}")
            return False

        fourcc = _FOURCC.get(self.pixel_format)
        if fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        if self.width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if self.fps:
            cap.set(cv2.CAP_PROP_FPS, self.fps)

        self._log_info(
            f"Camera opened: {self.device} "
            f"({self.pixel_format} {self.width}x{self.height} @ {self.fps}fps)"
        )

        cfg_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        cfg_fmt = "".join(chr((cfg_fourcc >> (8 * i)) & 0xFF) for i in range(4)).strip(
            "\x00"
        )
        cfg_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        cfg_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cfg_fps = cap.get(cv2.CAP_PROP_FPS)
        self.width = cfg_width
        self.height = cfg_height
        self.fps = cfg_fps

        self._log_info(
            f"Camera configured: {cfg_fmt} {self.width}x{self.height} @ {self.fps:.1f}fps"
        )

        self._cap = cap
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        return True

    def close(self):
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        with self._frame_lock:
            self._latest_frame = None

    def add_on_capture_callback(self, fn):
        with self._frame_lock:
            self._callbacks.append(fn)

    def remove_on_capture_callback(self, fn):
        with self._frame_lock:
            self._callbacks.remove(fn)

    def pop_latest_frame(self):
        with self._frame_lock:
            entry = self._latest_frame
            self._latest_frame = None
        return entry[1] if entry is not None else None

    def get_latest_timed_frame(self):
        with self._frame_lock:
            return self._latest_frame

    @property
    def is_open(self) -> bool:
        return self._cap is not None

    @property
    def estimated_fps(self) -> float | None:
        with self._frame_lock:
            times = list(self.capture_times)
        if len(times) < 2:
            return None
        return (len(times) - 1) / (times[-1] - times[0])

    def _capture_loop(self):
        while not self._stop_event.is_set():
            ret, frame = self._cap.read()
            if not ret:
                self._log_warn(
                    "Capture thread: failed to read frame — camera disconnected"
                )
                self._cap.release()
                self._cap = None
                return
            t = time.time()
            with self._frame_lock:
                self._latest_frame = (t, frame)
                self.capture_times.append(t)
                for cb in self._callbacks:
                    cb(t, frame)

    def _log_info(self, msg: str):
        if self._logger is not None:
            self._logger.info(msg)

    def _log_warn(self, msg: str):
        if self._logger is not None:
            self._logger.warning(msg)
