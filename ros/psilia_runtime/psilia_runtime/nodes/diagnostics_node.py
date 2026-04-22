"""
Diagnostics node — measures publish rates of monitored topics and publishes
diagnostics on /psilia/diagnostics/hz (std_msgs/String, JSON).

For each topic, keeps the last N timestamps and reports:
  hz     — average rate (N-1)/(last-first)
  min_dt — smallest gap between consecutive messages
  max_dt — largest gap between consecutive messages

Parameters:
  hz_topics  — list of "topic, type" strings (e.g. "/psilia/heartbeat, std_msgs/msg/String").
               Configurable via runtime.yaml ros.nodes.diagnostics_node.parameters.hz_topics.
  window     — number of timestamps to keep per topic (default: 10)
  publish_hz — how often to publish diagnostics (default: 5.0 Hz)
"""
import collections
import importlib
import json
import time
from pathlib import Path

import rclpy  # type: ignore
from rclpy.node import Node  # type: ignore
from std_msgs.msg import String  # type: ignore

from psilia_runtime.better_ros import better_node, ROSValue

_HZ_FILE = Path("/psilia/run/hz.json")

_DEFAULT_HZ_TOPICS = [
    "/psilia/heartbeat, std_msgs/msg/String",
    "/psilia/stereo/image_raw, sensor_msgs/msg/Image",
    "/psilia/stereo/image_rect, sensor_msgs/msg/Image",
    "/psilia/stereo/depth, sensor_msgs/msg/Image",
    "/psilia/preview/image/compressed, sensor_msgs/msg/CompressedImage",
    "/psilia/preview/depth/compressed, sensor_msgs/msg/CompressedImage",
    "/psilia/preview/rectified/compressed, sensor_msgs/msg/CompressedImage",
]


def _resolve_msg_type(type_str: str):
    """Resolve a ROS message type string like 'sensor_msgs/msg/Image' to a class."""
    parts = type_str.split("/")
    if len(parts) != 3:
        return None
    package, _, class_name = parts
    try:
        module = importlib.import_module(f"{package}.msg")
        return getattr(module, class_name)
    except (ImportError, AttributeError):
        return None


@better_node
class DiagnosticsNode(Node):
    hz_topics: ROSValue = _DEFAULT_HZ_TOPICS
    window: ROSValue = 10
    publish_hz: ROSValue = 5.0

    def __node_init__(self):
        self._timestamps = {}

        for entry in self.hz_topics:
            if not entry or "," not in entry:
                continue
            topic, type_str = entry.split(",", 1)
            topic, type_str = topic.strip(), type_str.strip()
            msg_type = _resolve_msg_type(type_str)
            if msg_type is None:
                self.get_logger().warn(f"Unknown message type: {type_str} for {topic}")
                continue
            self._timestamps[topic] = collections.deque(maxlen=self.window)
            self.create_subscription(
                msg_type, topic,
                lambda _msg, t=topic: self._on_msg(t),
                1,
            )

        self.pub = self.create_publisher(String, "/psilia/diagnostics/hz", 1)
        self.create_timer(1.0 / self.publish_hz, self._publish)

        self.get_logger().info(
            f"Diagnostics node started: monitoring {len(self._timestamps)} topics, "
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

        payload = json.dumps(result)

        msg = String()
        msg.data = payload
        self.pub.publish(msg)

        try:
            _HZ_FILE.parent.mkdir(parents=True, exist_ok=True)
            _HZ_FILE.write_text(payload)
        except OSError:
            pass


def main():
    rclpy.init()
    node = DiagnosticsNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
