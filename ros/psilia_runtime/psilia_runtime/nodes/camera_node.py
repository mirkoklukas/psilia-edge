"""
Camera node — reads from a UVC camera and publishes on /psilia/stereo/raw/image.

Optionally publishes CameraInfo on /psilia/stereo/raw/left/camera_info and
/psilia/stereo/raw/right/camera_info if a calibration file is provided.

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
        self.pub = self.create_publisher(Image, "/psilia/stereo/raw/image", 10)
        self._setup_camera_info()
        self._stream = CameraStream(
            self.device, self.pixel_format, self.width, self.height, self.fps,
            logger=self.get_logger(),
        )
        self._stream.open()
        self._last_open_attempt = 0.0
        self.frame_count = 0
        self._buf = None
        self._np_buf = None
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

        stereo = StereoCalibration.load(self.calibration_file, strict=False).rectify(force=True)

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
            ).rectify(force=True)

        self._camera_info_left = self._build_camera_info(stereo.cam0)
        self._camera_info_right = self._build_camera_info(stereo.cam1)
        self._pub_info_left = self.create_publisher(CameraInfo, "/psilia/stereo/raw/left/camera_info", 10)
        self._pub_info_right = self.create_publisher(CameraInfo, "/psilia/stereo/raw/right/camera_info", 10)

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

        if self._buf is None:
            n = frame.shape[0] * frame.shape[1] * 3
            self._buf = array.array('B', bytes(n))
            self._np_buf = np.frombuffer(self._buf, dtype=np.uint8)

        msg = Image()
        msg.header = Header(stamp=stamp, frame_id="camera")
        msg.height, msg.width = frame.shape[:2]
        msg.encoding = "bgr8"
        msg.step = msg.width * 3
        np.copyto(self._np_buf, frame.ravel())
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
