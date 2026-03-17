"""
Camera node — reads from a UVC camera and publishes on /psilia/image/raw.

Parameters (set via launch_params.yaml):
  device        — /dev/video path (e.g. /dev/video0)
  pixel_format  — capture format: MJPG or YUYV
  width         — capture width in pixels
  height        — capture height in pixels
  fps           — capture frame rate

If the device cannot be opened, the node logs a warning and retries every second.
"""
import rclpy
import cv2
import numpy as np
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Header

_FOURCC = {
    "MJPG": cv2.VideoWriter_fourcc("M", "J", "P", "G"),
    "YUYV": cv2.VideoWriter_fourcc("Y", "U", "Y", "V"),
}


class CameraNode(Node):
    def __init__(self):
        super().__init__("camera_node")

        self.declare_parameter("device", "/dev/video0")
        self.declare_parameter("pixel_format", "MJPG")
        self.declare_parameter("width", 640)
        self.declare_parameter("height", 480)
        self.declare_parameter("fps", 30)

        self._device = self.get_parameter("device").get_parameter_value().string_value
        self._pixel_format = self.get_parameter("pixel_format").get_parameter_value().string_value
        self._width = self.get_parameter("width").get_parameter_value().integer_value
        self._height = self.get_parameter("height").get_parameter_value().integer_value
        self._fps = self.get_parameter("fps").get_parameter_value().integer_value

        self._pub = self.create_publisher(Image, "/psilia/image/raw", 10)
        self._cap = None
        self._open_camera()
        self.create_timer(1.0 / self._fps, self._publish_frame)

    def _open_camera(self) -> bool:
        self._cap = cv2.VideoCapture(self._device, cv2.CAP_V4L2)
        if not self._cap.isOpened():
            self.get_logger().warn(f"Could not open camera device: {self._device}")
            self._cap = None
            return False

        fourcc = _FOURCC.get(self._pixel_format)
        if fourcc:
            self._cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap.set(cv2.CAP_PROP_FPS, self._fps)

        self.get_logger().info(
            f"Camera opened: {self._device} "
            f"({self._pixel_format} {self._width}x{self._height} @ {self._fps}fps)"
        )
        return True

    def _publish_frame(self):
        if self._cap is None:
            self._open_camera()
            return

        ret, frame = self._cap.read()
        if not ret:
            self.get_logger().warn("Failed to read frame — reopening camera")
            self._cap.release()
            self._cap = None
            return

        stamp = self.get_clock().now().to_msg()
        msg = Image()
        msg.header = Header(stamp=stamp, frame_id="camera")
        msg.height, msg.width = frame.shape[:2]
        msg.encoding = "bgr8"
        msg.step = msg.width * 3
        msg.data = frame.tobytes()
        self._pub.publish(msg)


def main():
    rclpy.init()
    node = CameraNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
