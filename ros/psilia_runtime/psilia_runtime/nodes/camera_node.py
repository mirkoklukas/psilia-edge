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
import array
import time

import numpy as np

import rclpy # type: ignore
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
            f"{self.width}x{self.height} fps={self.fps}"
        )
        self.pub = self.create_publisher(Image, "/psilia/image/raw", 10)
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
