"""
Preview node — subscribes to /psilia/stereo/raw/image, downsamples, and republishes on
/psilia/preview/image          (raw, sensor_msgs/Image)
/psilia/preview/image/compressed  (JPEG, sensor_msgs/CompressedImage)
at a low frame rate for live monitoring (web UI, recording view).

Parameters (set via launch_params.yaml):
  target_height  — target height in pixels after downsampling (default 50)
  fps            — publish rate in Hz (default 5)

Downsampling uses stride slicing (frame[::d, ::d]) where d = height // target_height.
Frames arriving faster than fps are dropped; no buffering.

TODO: Generalize into a single preview node that accepts a list of image topics
      and frame rates, and publishes corresponding preview topics. This would
      replace both preview_node and depth_preview_node.
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
class PreviewNode(Node):
    target_height: ROSValue = 50
    fps: ROSValue = 5

    def __node_init__(self):
        self._last_publish = 0.0
        self.create_subscription(Image, "/psilia/stereo/raw/image", self._on_image, 10)
        self.pub = self.create_publisher(Image, "/psilia/preview/image", 10)
        self.pub_compressed = self.create_publisher(CompressedImage, "/psilia/preview/image/compressed", 10)

    def _on_image(self, msg: Image):
        now = time.monotonic()
        if now - self._last_publish < 1.0 / self.fps:
            return
        self._last_publish = now

        d = max(1, msg.height // self.target_height)
        frame = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
        preview = frame[::d, ::d]

        out = Image()
        out.header = msg.header
        out.height, out.width = preview.shape[:2]
        out.encoding = msg.encoding
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
    node = PreviewNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
