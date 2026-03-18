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
from rclpy.node import Node # type: ignore
from sensor_msgs.msg import Image # type: ignore
from std_msgs.msg import Header # type: ignore
from psilia_runtime.better_ros import better_node, ROSValue

_FOURCC = {
    "MJPG": cv2.VideoWriter_fourcc("M", "J", "P", "G"),
    "YUYV": cv2.VideoWriter_fourcc("Y", "U", "Y", "V"),
}


@better_node
class CameraNode(Node):
    device: ROSValue = "/dev/video0"
    pixel_format: ROSValue = "MJPG"
    width: ROSValue = 640
    height: ROSValue = 480
    fps: ROSValue = 30

    def __node_init__(self):
        self.pub = self.create_publisher(Image, "/psilia/image/raw", 10)
        self.cap = None
        self.open_camera()
        self.create_timer(1.0 / self.fps, self.publish_frame)

    def open_camera(self) -> bool:
        self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            self.get_logger().warn(f"Could not open camera device: {self.device}")
            self.cap = None
            return False

        fourcc = _FOURCC.get(self.pixel_format)
        if fourcc:
            self.cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        self.get_logger().info(
            f"Camera opened: {self.device} "
            f"({self.pixel_format} {self.width}x{self.height} @ {self.fps}fps)"
        )
        return True

    def publish_frame(self):
        if self.cap is None:
            self.open_camera()
            return

        ret, frame = self.cap.read()
        if not ret:
            self.get_logger().warn("Failed to read frame — reopening camera")
            self.cap.release()
            self.cap = None
            return

        stamp = self.get_clock().now().to_msg()
        msg = Image()
        msg.header = Header(stamp=stamp, frame_id="camera")
        msg.height, msg.width = frame.shape[:2]
        msg.encoding = "bgr8"
        msg.step = msg.width * 3
        msg.data = frame.tobytes()
        self.pub.publish(msg)
        self.frame_count = getattr(self, "frame_count", 0) + 1
        if self.frame_count % 100 == 0:
            self.get_logger().info(f"Frame {self.frame_count}: {msg.width}x{msg.height} ({msg.encoding})")


def main():
    rclpy.init()
    node = CameraNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
