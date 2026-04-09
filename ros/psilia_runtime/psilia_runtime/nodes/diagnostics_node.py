"""
Diagnostics node — measures publish rates of monitored topics and publishes
diagnostics on /psilia/diagnostics/hz (std_msgs/String, JSON).

For each topic, keeps the last N timestamps and reports:
  hz     — average rate (N-1)/(last-first)
  min_dt — smallest gap between consecutive messages
  max_dt — largest gap between consecutive messages

Parameters:
  window     — number of timestamps to keep per topic (default: 10)
  publish_hz — how often to publish diagnostics (default: 5.0 Hz)
"""
import collections
import json
import time

import rclpy  # type: ignore
from rclpy.node import Node  # type: ignore
from sensor_msgs.msg import CompressedImage, Image, PointCloud2  # type: ignore
from std_msgs.msg import String  # type: ignore

from psilia_runtime.better_ros import better_node, ROSValue


MONITORED_TOPICS = [
    ("/psilia/stereo/image_raw",                Image),
    ("/psilia/stereo/image_rect",               Image),
    ("/psilia/stereo/depth",                    Image),
    ("/psilia/preview/image/compressed",        CompressedImage),
    ("/psilia/preview/depth/compressed",        CompressedImage),
    ("/psilia/preview/rectified/compressed",    CompressedImage),
    ("/psilia/preview/pointcloud",              PointCloud2),
]


@better_node
class DiagnosticsNode(Node):
    window: ROSValue = 10
    publish_hz: ROSValue = 5.0

    def __node_init__(self):
        self._timestamps = {}

        for topic, msg_type in MONITORED_TOPICS:
            self._timestamps[topic] = collections.deque(maxlen=self.window)
            self.create_subscription(
                msg_type, topic,
                lambda _msg, t=topic: self._on_msg(t),
                1,
            )

        self.pub = self.create_publisher(String, "/psilia/diagnostics/hz", 1)
        self.create_timer(1.0 / self.publish_hz, self._publish)

        self.get_logger().info(
            f"Diagnostics node started: monitoring {len(MONITORED_TOPICS)} topics, "
            f"window={self.window}, publish_hz={self.publish_hz}"
        )

    def _on_msg(self, topic):
        self._timestamps[topic].append(time.monotonic())

    def _publish(self):
        result = {}
        for topic, times in self._timestamps.items():
            ts = list(times)
            if len(ts) < 2:
                result[topic] = {"hz": 0.0, "min_dt": 0.0, "max_dt": 0.0}
                continue

            deltas = [ts[i] - ts[i - 1] for i in range(1, len(ts))]
            hz = (len(ts) - 1) / (ts[-1] - ts[0])
            result[topic] = {
                "hz": round(hz, 1),
                "min_dt": round(min(deltas), 3),
                "max_dt": round(max(deltas), 3),
            }

        msg = String()
        msg.data = json.dumps(result)
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = DiagnosticsNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
