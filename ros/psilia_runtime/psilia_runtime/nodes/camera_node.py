"""
Camera node — reads from a UVC camera and publishes on /psilia/stereo/image_raw.

Optionally publishes CameraInfo on /psilia/stereo/left/camera_info and
/psilia/stereo/right/camera_info if a calibration file is provided.

Parameters (set via launch_params.yaml):
  device           — /dev/video path (e.g. /dev/video0)
  pixel_format     — capture format: MJPG or YUYV
  width            — capture width in pixels
  height           — capture height in pixels
  fps              — capture frame rate
  calibration_file — path to a Kalibr calibration YAML (optional)
  camera_left      — camera name for the left image (default: cam0)
  camera_right     — camera name for the right image (default: cam1)

If the device cannot be opened, the node logs a warning and retries every second.
"""
import array
import time

import numpy as np

import rclpy # type: ignore
from builtin_interfaces.msg import Time # type: ignore
from rclpy.node import Node # type: ignore
from sensor_msgs.msg import CameraInfo, Image # type: ignore
from std_msgs.msg import Header # type: ignore
from psilia_runtime.better_ros import better_node, ROSValue, every_seconds
from psilia_runtime.camera_stream import CameraStream
from psilia_runtime.camera import CameraCalibration, StereoCalibration


@better_node
class CameraNode(Node):
    device: ROSValue = "/dev/video0"
    pixel_format: ROSValue = "MJPG"
    width: ROSValue = 640
    height: ROSValue = 480
    fps: ROSValue = 30
    calibration_file: ROSValue = ""
    camera_left: ROSValue = "cam0"
    camera_right: ROSValue = "cam1"

    def __node_init__(self):
        self.get_logger().info(
            f"CameraNode init: device={self.device} format={self.pixel_format} "
            f"{self.width}x{self.height} fps={self.fps}"
        )
        self.pub = self.create_publisher(Image, "/psilia/stereo/image_raw", 10)
        self._setup_camera_info()
        self._stream = CameraStream(
            self.device, self.pixel_format, self.width, self.height, self.fps,
            logger=self.get_logger(),
        )
        self._stream.open()
        self._last_open_attempt = 0.0
        self.frame_count = 0
        # Pre-allocated publish buffer reused every frame. _np_buf is a numpy
        # view into _buf (shared memory), so np.copyto(_np_buf, ...) writes
        # directly into the array.array that rclpy can bulk-copy at the C level.
        self._buf = array.array('B', bytes(self.width * self.height * 3))
        self._np_buf = np.frombuffer(self._buf, dtype=np.uint8)
        self.create_timer(1.0 / self.fps, self.publish_frame)

    def _setup_camera_info(self):
        """Load calibration and build CameraInfo messages for left and right cameras.

        Each CameraInfo carries the full set: K + D (raw intrinsics), R (rectification
        rotation), and P (rectified projection matrix). A single message serves both
        raw and rectified consumers.
        """
        self._pub_info_left = None
        self._pub_info_right = None
        self._camera_info_left = None
        self._camera_info_right = None

        if not self.calibration_file:
            self.get_logger().info("No calibration_file — CameraInfo will not be published.")
            return

        stereo = StereoCalibration.load(self.calibration_file, strict=False).rectify()

        # Rescale calibration if the capture resolution doesn't match.
        eye_w = self.width // 2
        if eye_w != stereo.cam0.width or self.height != stereo.cam0.height:
            factor = eye_w / stereo.cam0.width
            self.get_logger().info(
                f"Rescaling calibration: {stereo.cam0.width}x{stereo.cam0.height} → {eye_w}x{self.height} "
                f"(factor={factor:.3f})"
            )
            stereo = StereoCalibration(
                stereo.cam0.rescale(factor), stereo.cam1.rescale(factor)
            ).rectify()

        self._camera_info_left = self._build_camera_info(stereo.cam0)
        self._camera_info_right = self._build_camera_info(stereo.cam1)
        self._pub_info_left = self.create_publisher(CameraInfo, "/psilia/stereo/left/camera_info", 10)
        self._pub_info_right = self.create_publisher(CameraInfo, "/psilia/stereo/right/camera_info", 10)

        self.get_logger().info("CameraInfo ready (left + right).")

    def _build_camera_info(self, cal: CameraCalibration) -> CameraInfo:
        info = CameraInfo()
        info.header.frame_id = "camera"
        info.width = cal.width
        info.height = cal.height
        info.distortion_model = "plumb_bob"
        info.d = cal.distortion_coeffs.flatten().tolist()
        info.k = cal.K.flatten().tolist()
        info.r = cal.R_rect.flatten().tolist()
        info.p = cal.P_rect.flatten().tolist()
        return info

    def publish_frame(self):
        if not self._stream.is_open:
            now = time.monotonic()
            if now - self._last_open_attempt >= 1.0:
                self._last_open_attempt = now
                self._stream.open()
            return

        entry = self._stream.get_latest_timed_frame()
        if entry is None:
            return  # no new frame since last publish

        t, frame = entry
        stamp = Time(sec=int(t), nanosec=int((t % 1) * 1e9))

        # np.copyto writes directly into the pre-allocated array.array buffer via
        # a numpy view (_np_buf = np.frombuffer(_buf)) — no intermediate bytes object.
        # rclpy then bulk-copies from the array.array at the C level (~0.17ms).
        # Net: one copy (frame → _buf) instead of two (frame → bytes → array).
        #
        # Previous approach (two allocations, two copies):
        #   msg.data = array.array('B', frame.tobytes())
        #
        # Note on the previous approach: msg.data = frame.tobytes() was ~97ms on Jetson —
        # not tobytes() itself (0.05ms), but the assignment, which triggers slow
        # element-by-element Python iteration in rclpy's uint8[] field (bytes → array.array).
        # Using array.array('B', ...) hits rclpy's fast C-level bulk copy instead (~0.17ms).
        # 'B' is the type code for unsigned char (uint8) — exactly what rclpy expects
        # for a uint8[] field, so no conversion is needed and the assignment is fast.
        #
        # CvBridge alternative (~0.26ms, requires numpy<2 pin due to ABI mismatch
        # with ros-humble-cv-bridge compiled against numpy 1.x):
        #   msg = self._bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        #   msg.header = Header(stamp=stamp, frame_id="camera")
        msg = Image()
        msg.header = Header(stamp=stamp, frame_id="camera")
        msg.height, msg.width = frame.shape[:2]
        msg.encoding = "bgr8"
        msg.step = msg.width * 3
        np.copyto(self._np_buf, frame.ravel())  # writes into _buf via shared memory
        msg.data = self._buf
        self.pub.publish(msg)

        if self._pub_info_left is not None:
            self._camera_info_left.header = msg.header
            self._camera_info_right.header = msg.header
            self._pub_info_left.publish(self._camera_info_left)
            self._pub_info_right.publish(self._camera_info_right)

        self.frame_count += 1
        if self.frame_count % 100 == 0:
            self.get_logger().info(f"Frame {self.frame_count}: {msg.width}x{msg.height} ({msg.encoding})")

    def destroy_node(self):
        self._stream.close()
        super().destroy_node()

    @every_seconds(2.0)
    def _log_fps(self):
        fps = self._stream.estimated_fps
        if fps is not None:
            self.get_logger().info(f"Estimated capture FPS: {fps:.1f}")


def main():
    rclpy.init()
    node = CameraNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
