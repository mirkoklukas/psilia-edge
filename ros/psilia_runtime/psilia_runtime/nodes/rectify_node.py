"""
Rectify node — subscribes to /psilia/image/raw (side-by-side stereo),
applies stereo rectification, and publishes on /psilia/image/rectified.

Parameters (set via launch file or command line):
  calibration_file  — path to a Kalibr calibration-camchain YAML file
  camera_left       — camera name for the left image (default: cam0)
  camera_right      — camera name for the right image (default: cam1)

TODO: Replace Kalibr camchain format with our own calibration format.
"""
import array

import cv2
import numpy as np

import rclpy  # type: ignore
from rclpy.node import Node  # type: ignore
from sensor_msgs.msg import Image  # type: ignore
from std_msgs.msg import Header  # type: ignore
from builtin_interfaces.msg import Time  # type: ignore

from psilia_runtime.better_ros import better_node, ROSValue
from psilia_runtime.camera_calibration import CameraCalibration


@better_node
class RectifyNode(Node):
    calibration_file: ROSValue = ""
    camera_left: ROSValue = "cam0"
    camera_right: ROSValue = "cam1"

    def __node_init__(self):
        if not self.calibration_file:
            self.get_logger().error("No calibration_file parameter set — cannot rectify.")
            return

        self._cal0 = CameraCalibration.from_kalibr(self.calibration_file, self.camera_left)
        self._cal1 = CameraCalibration.from_kalibr(self.calibration_file, self.camera_right)
        self._ready = False

        self.pub = self.create_publisher(Image, "/psilia/image/rectified", 1)
        self.create_subscription(Image, "/psilia/image/raw", self.on_image, 1)

    def _setup_rectification(self, frame_width: int, frame_height: int):
        """Initialize rectification maps, rescaling calibration if needed."""
        eye_w = frame_width // 2
        cal0, cal1 = self._cal0, self._cal1

        if eye_w != cal0.width or frame_height != cal0.height:
            factor = eye_w / cal0.width
            self.get_logger().info(
                f"Rescaling calibration: {cal0.width}x{cal0.height} → {eye_w}x{frame_height} "
                f"(factor={factor:.3f})"
            )
            cal0 = cal0.rescale(factor)
            cal1 = cal1.rescale(factor)

        rect = CameraCalibration.stereo_rectification(cal0, cal1)

        self._map1_l = rect.map1_l
        self._map2_l = rect.map2_l
        self._map1_r = rect.map1_r
        self._map2_r = rect.map2_r
        self.width = cal0.width
        self.height = cal0.height
        self._ready = True

        self.get_logger().info(
            f"Stereo rectification ready: {self.width}x{self.height} "
            f"({self.camera_left}, {self.camera_right})"
        )

        # Pre-allocated output buffers for cv2.remap (avoids per-frame allocation).
        self._rect_l = np.empty((self.height, self.width, 3), dtype=np.uint8)
        self._rect_r = np.empty((self.height, self.width, 3), dtype=np.uint8)

        # Pre-allocated publish buffer (same trick as camera_node).
        full_width = self.width * 2
        self._buf = array.array('B', bytes(full_width * self.height * 3))
        self._np_buf = np.frombuffer(self._buf, dtype=np.uint8).reshape(
            self.height, full_width, 3
        )

    def on_image(self, msg: Image):
        if not self._ready:
            self._setup_rectification(msg.width, msg.height)
            if not self._ready:
                return

        # Reconstruct frame from msg.data (side-by-side stereo).
        frame = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
        left = frame[:, :self.width]
        right = frame[:, self.width:]

        cv2.remap(left, self._map1_l, self._map2_l, cv2.INTER_LINEAR, dst=self._rect_l)
        cv2.remap(right, self._map1_r, self._map2_r, cv2.INTER_LINEAR, dst=self._rect_r)

        # Write rectified halves into the pre-allocated publish buffer.
        self._np_buf[:, :self.width] = self._rect_l
        self._np_buf[:, self.width:] = self._rect_r

        out = Image()
        out.header = msg.header
        out.height = self.height
        out.width = self.width * 2
        out.encoding = msg.encoding
        out.step = out.width * 3
        out.data = self._buf
        self.pub.publish(out)


def main():
    rclpy.init()
    node = RectifyNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
