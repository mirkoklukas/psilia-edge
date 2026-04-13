"""
Depth preview node — subscribes to /psilia/stereo/depth (32FC1), applies a colormap,
downsamples, and republishes on
/psilia/preview/depth              (raw, sensor_msgs/Image)
/psilia/preview/depth/compressed   (JPEG, sensor_msgs/CompressedImage)
at a low frame rate for live monitoring (web UI, recording view).

Parameters (set via launch file or command line):
  target_height  — target height in pixels after downsampling (default 50)
  fps            — publish rate in Hz (default 5)
  max_depth      — clamp depth to this value in meters for colormap scaling (default 10.0)

TODO: Higher-resolution previews in the web UI. Currently limited by rosbridge's
  JSON+base64 serialization overhead — large images choke the websocket. Options:
  switch the web UI to foxglove bridge (binary protocol), or serve preview images
  via a direct HTTP endpoint instead of rosbridge.
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
    target_height: ROSValue = 100
    fps: ROSValue = 5
    max_depth: ROSValue = 3.0

    def __node_init__(self):
        self._last_publish = 0.0
        self._last_publish_rect = 0.0
        self.create_subscription(Image, "/psilia/stereo/depth", self._on_depth, 1)
        self.create_subscription(Image, "/psilia/stereo/image_rect", self._on_rectified, 1)
        self.pub = self.create_publisher(Image, "/psilia/preview/depth", 10)
        self.pub_compressed = self.create_publisher(CompressedImage, "/psilia/preview/depth/compressed", 10)
        self.pub_rect_compressed = self.create_publisher(CompressedImage, "/psilia/preview/rectified/compressed", 10)

    def _on_depth(self, msg: Image):
        now = time.monotonic()
        if now - self._last_publish < 1.0 / self.fps:
            return
        self._last_publish = now

        depth = np.frombuffer(msg.data, dtype=np.float32).reshape(msg.height, msg.width)

        # Downsample first (cheaper to colormap fewer pixels).
        d = max(1, msg.height // self.target_height)
        depth_small = depth[::d, ::d]

        # Mask invalid pixels (depth <= 0), normalize valid range to 0–255.
        valid = depth_small > 0
        normalized = np.zeros_like(depth_small, dtype=np.uint8)
        normalized[valid] = (np.clip(depth_small[valid], 0, self.max_depth) * 255.0 / self.max_depth).astype(np.uint8)

        # Apply plasma colormap, set invalid pixels to white.
        preview = cv2.applyColorMap(normalized, cv2.COLORMAP_PLASMA)
        preview[~valid] = (255, 255, 255)

        out = Image()
        out.header = msg.header
        out.height, out.width = preview.shape[:2]
        out.encoding = "bgr8"
        out.step = out.width * 3
        out.data = array.array('B', preview.tobytes())
        self.pub.publish(out)

        self._publish_compressed(preview, msg.header)

    def _on_rectified(self, msg: Image):
        now = time.monotonic()
        if now - self._last_publish_rect < 1.0 / self.fps:
            return
        self._last_publish_rect = now

        frame = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
        d = max(1, msg.height // self.target_height)
        preview = frame[::d, ::d]

        _, buf = cv2.imencode('.jpg', preview)
        out = CompressedImage()
        out.header = msg.header
        out.format = "jpeg"
        out.data = array.array('B', buf.tobytes())
        self.pub_rect_compressed.publish(out)

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
