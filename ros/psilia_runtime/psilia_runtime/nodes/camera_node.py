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
import time

import rclpy
import cv2
from builtin_interfaces.msg import Time # type: ignore
from rclpy.node import Node # type: ignore
from sensor_msgs.msg import Image # type: ignore
from std_msgs.msg import Header # type: ignore
from psilia_runtime.better_ros import better_node, ROSValue, every_seconds
from psilia_runtime.camera_stream import CameraStream


@better_node
class CameraNode(Node):
    device: ROSValue = "/dev/video0"
    pixel_format: ROSValue = "MJPG"
    width: ROSValue = 640
    height: ROSValue = 480
    fps: ROSValue = 30

    def __node_init__(self):
        self.get_logger().info(
            f"CameraNode init: device={self.device} format={self.pixel_format} "
            f"{self.width}x{self.height} fps={self.fps} timer_period={1.0/self.fps:.4f}s"
        )
        self.pub = self.create_publisher(Image, "/psilia/image/raw", 10)
        self._stream = CameraStream(
            self.device, self.pixel_format, self.width, self.height, self.fps,
            logger=self.get_logger(),
        )
        self._stream.open()
        self.frame_count = 0
        self.create_timer(1.0 / self.fps, self.publish_frame)

    def publish_frame(self):
        if not self._stream.is_open:
            self._stream.open()
            return

        # frame = self._stream.pop_latest_frame()
        entry = self._stream.get_latest_timed_frame()
        if entry is None:
            return  # no new frame since last publish

        t, frame = entry
        stamp = Time(sec=int(t), nanosec=int((t % 1) * 1e9))
        msg = Image()
        msg.header = Header(stamp=stamp, frame_id="camera")
        msg.height, msg.width = frame.shape[:2]
        msg.encoding = "bgr8"
        msg.step = msg.width * 3
        self.get_logger().info(f"contiguous: {frame.flags['C_CONTIGUOUS']}")
        t0 = time.monotonic()
        msg.data = frame.tobytes()
        self.get_logger().info(f"tobytes: {(time.monotonic() - t0)*1000:.2f}ms")
        t0 = time.monotonic()
        _ = bytes(frame.data)
        self.get_logger().info(f"bytes(frame.data): {(time.monotonic() - t0)*1000:.2f}ms")
        self.pub.publish(msg)
        self.frame_count += 1
        if self.frame_count % 100 == 0:
            self.get_logger().info(f"Frame {self.frame_count}: {msg.width}x{msg.height} ({msg.encoding})")


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
