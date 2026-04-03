"""
Depth preview node — subscribes to /psilia/depth (32FC1), applies a colormap,
downsamples, and republishes on
/psilia/depth/preview              (raw, sensor_msgs/Image)
/psilia/depth/preview/compressed   (JPEG, sensor_msgs/CompressedImage)
at a low frame rate for live monitoring (web UI, recording view).

Parameters (set via launch file or command line):
  target_height  — target height in pixels after downsampling (default 50)
  fps            — publish rate in Hz (default 5)
  max_depth      — clamp depth to this value in meters for colormap scaling (default 10.0)
"""
import array
import time

import cv2
import numpy as np
import rclpy  # type: ignore
from rclpy.node import Node  # type: ignore
from sensor_msgs.msg import CompressedImage, Image  # type: ignore
from psilia_runtime.better_ros import better_node, ROSValue


@better_node
class DepthPreviewNode(Node):
    target_height: ROSValue = 200
    fps: ROSValue = 5
    max_depth: ROSValue = 10.0

    def __node_init__(self):
        self._last_publish = 0.0
        self.create_subscription(Image, "/psilia/depth", self._on_depth, 10)
        self.pub = self.create_publisher(Image, "/psilia/depth/preview", 10)
        self.pub_compressed = self.create_publisher(CompressedImage, "/psilia/depth/preview/compressed", 10)

    def _on_depth(self, msg: Image):
        now = time.monotonic()
        if now - self._last_publish < 1.0 / self.fps:
            return
        self._last_publish = now

        depth = np.frombuffer(msg.data, dtype=np.float32).reshape(msg.height, msg.width)

        # Normalize to 0–255 and apply colormap.
        clamped = np.clip(depth, 0, self.max_depth)
        normalized = (clamped * 255.0 / self.max_depth).astype(np.uint8)
        colored = cv2.applyColorMap(normalized, cv2.COLORMAP_TURBO)

        # Downsample.
        d = max(1, msg.height // self.target_height)
        preview = colored[::d, ::d]

        out = Image()
        out.header = msg.header
        out.height, out.width = preview.shape[:2]
        out.encoding = "bgr8"
        out.step = out.width * 3
        out.data = array.array('B', preview.tobytes())
        self.pub.publish(out)

        self._publish_compressed(preview, msg.header)

    def _publish_compressed(self, preview, header):
        _, buf = cv2.imencode('.jpg', preview)
        out = CompressedImage()
        out.header = header
        out.format = "jpeg"
        out.data = array.array('B', buf.tobytes())
        self.pub_compressed.publish(out)


def main():
    rclpy.init()
    node = DepthPreviewNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
