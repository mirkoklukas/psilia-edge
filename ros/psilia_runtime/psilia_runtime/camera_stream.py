"""
CameraStream — threaded UVC camera capture.

Threading model
---------------
Two threads interact with this class:

  Capture thread (_capture_loop)
    Runs in the background. Calls cap.read() in a tight loop — this call
    blocks until the camera delivers a frame. On each successful read it
    stores the frame and appends a timestamp, then immediately loops back
    to read the next frame. It never sleeps; the camera's hardware timing
    is the natural throttle.

  Caller thread (open / close / get_latest_frame)
    The ROS timer callback or any other consumer. It never touches cap
    directly — it only reads _latest_frame via get_latest_frame().

Shared state and synchronisation
---------------------------------
  _frame_lock (threading.Lock)
    Protects _latest_frame and capture_times, which are written by the
    capture thread and read by the caller thread. The lock is held only
    for the short assignment/append — cap.read() itself runs outside it
    so the caller is never blocked waiting for the camera.

  _stop_event (threading.Event)
    Signals the capture thread to exit cleanly. Set by open() before
    (re)opening — in case a thread from a previous session is still
    running — and by close(). The capture loop checks it on every
    iteration; once set the thread returns on the next iteration.
    open() calls thread.join() after setting the event to ensure the
    old thread has fully exited before a new cap is created.

  _cap (cv2.VideoCapture)
    Owned exclusively by the capture thread once open() returns. The
    caller thread checks is_open (reads _cap is not None) to decide
    whether to retry open(), but never calls cap.read() or cap.release()
    itself. The capture thread sets _cap = None before returning on
    failure, which is the signal that triggers a reopen on the next
    publish_frame() call.

Usage:
    stream = CameraStream("/dev/video0", "MJPG", 640, 480, 30, logger)
    stream.open()
    ...
    frame = stream.get_latest_frame()  # None if no new frame yet
    ...
    stream.close()
"""
import collections
import threading
import time

import cv2


_FOURCC = {
    "MJPG": cv2.VideoWriter_fourcc("M", "J", "P", "G"),
    "YUYV": cv2.VideoWriter_fourcc("Y", "U", "Y", "V"),
}


class CameraStream:
    def __init__(self, device: str, pixel_format: str, width: int, height: int, fps: int, logger=None):
        self.device = device
        self.pixel_format = pixel_format
        self.width = width
        self.height = height
        self.fps = fps
        self._logger = logger

        self._cap = None
        self._latest_frame = None  # written by capture thread, read by caller
        self._frame_lock = threading.Lock()
        self._stop_event = threading.Event()  # set → capture thread should exit
        self._thread = None

        # Monotonic timestamps (time.monotonic()) appended by the capture thread
        # on every successful frame read. Useful for measuring actual FPS and
        # frame jitter. Capped at 256 entries (rolling window).
        self.capture_times: collections.deque = collections.deque(maxlen=256)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def open(self) -> bool:
        """Open the camera and start the capture thread. Returns True on success.

        Safe to call multiple times — stops any existing capture thread first.
        """
        # Signal any running capture thread to stop and wait for it to exit
        # before touching _cap, so we never have two threads owning the same cap.
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

        cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        if not cap.isOpened():
            self._log_warn(f"Could not open camera device: {self.device}")
            return False

        fourcc = _FOURCC.get(self.pixel_format)
        if fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        cap.set(cv2.CAP_PROP_FPS, self.fps)

        self._log_info(
            f"Camera opened: {self.device} "
            f"({self.pixel_format} {self.width}x{self.height} @ {self.fps}fps)"
        )

        cfg_fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
        cfg_fmt    = "".join(chr((cfg_fourcc >> (8 * i)) & 0xFF) for i in range(4)).strip("\x00")
        cfg_width  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        cfg_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cfg_fps    = cap.get(cv2.CAP_PROP_FPS)
        self._log_info(
            f"Camera configured: {cfg_fmt} {cfg_width}x{cfg_height} @ {cfg_fps:.1f}fps"
        )

        self._cap = cap
        self._stop_event.clear()  # arm the stop event for the new thread
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        return True

    def close(self):
        """Stop the capture thread and release the camera."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        with self._frame_lock:
            self._latest_frame = None

    def get_latest_frame(self):
        """Return the latest captured frame and clear it, or None if none is available.

        Clears the frame after returning it so the same frame is never published twice.
        """
        with self._frame_lock:
            frame = self._latest_frame
            self._latest_frame = None
        return frame

    @property
    def is_open(self) -> bool:
        """True if the camera is open and the capture thread is running."""
        return self._cap is not None

    @property
    def estimated_fps(self) -> float | None:
        """Estimate actual FPS from the capture timestamp buffer.

        Computed as (n - 1) / (last - first) over all timestamps currently
        in the buffer. Returns None if fewer than 2 timestamps are available.
        """
        with self._frame_lock:
            times = list(self.capture_times)
        if len(times) < 2:
            return None
        return (len(times) - 1) / (times[-1] - times[0])

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _capture_loop(self):
        """Background thread: read frames from the camera as fast as it delivers them.

        cap.read() blocks until the camera produces a frame — this is the natural
        frame-rate throttle, no sleep needed. The lock is acquired only for the
        short assignment so the caller thread is never blocked waiting for a frame.

        On read failure the cap is released and _cap is set to None, which signals
        is_open = False. The caller (publish_frame) detects this and calls open()
        to restart the stream.
        """
        while not self._stop_event.is_set():
            ret, frame = self._cap.read()  # blocks until next frame is ready
            if not ret:
                self._log_warn("Capture thread: failed to read frame — camera disconnected")
                self._cap.release()
                self._cap = None  # signals is_open = False to the caller thread
                return
            with self._frame_lock:
                self._latest_frame = frame
                self.capture_times.append(time.monotonic())

    def _log_info(self, msg: str):
        if self._logger is not None:
            self._logger.info(msg)

    def _log_warn(self, msg: str):
        if self._logger is not None:
            self._logger.warn(msg)
