"""
Core node — the always-on runtime node.

/psilia/heartbeat       (1 Hz, latched)  — heartbeat with timestamp; late subscribers
                                            still receive the latest message.
/psilia/interface       (latched)        — interface description broadcast on startup:
                                            version, exposed topics.
/psilia/status_request  (subscribed)     — any message triggers a full status write
                                            to /psilia/run/status.json.

Files written to /psilia/run/ (mounted from host):
  heartbeat.json  — written every tick: status, stamp, ros_domain_id
  status.json     — written on request: heartbeat fields + nodes, topics

TODO: extend heartbeat payload with system metrics:
  - cpu_percent     (psutil.cpu_percent())
  - memory_percent  (psutil.virtual_memory().percent)
  - disk_free_gb    (shutil.disk_usage("/ssd").free / 1e9)
  - temperature_c   (read from /sys/class/thermal/thermal_zone*/temp on Jetson)
"""
import json
import os
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String

_LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)

_HEARTBEAT_FILE = Path("/psilia/run/heartbeat.json")
_STATUS_FILE = Path("/psilia/run/status.json")


class CoreNode(Node):
    def __init__(self):
        super().__init__("psilia_core")

        self.declare_parameter("psilia_version", "0.1.0")
        self.declare_parameter("interface_topics", [""])

        self.psilia_version = self.get_parameter("psilia_version").get_parameter_value().string_value
        self.interface_topics = [
            t for t in self.get_parameter("interface_topics").get_parameter_value().string_array_value
            if t
        ]

        self.heartbeat_pub = self.create_publisher(String, "/psilia/heartbeat", _LATCHED)
        self.interface_pub = self.create_publisher(String, "/psilia/interface", _LATCHED)
        self.create_subscription(String, "/psilia/status_request", self._on_status_request, 10)

        self._publish_interface()
        # TODO: can publish at a slower rate as well, or make it configurable.
        self.timer = self.create_timer(2.0, self._publish_heartbeat)
        self.get_logger().info("Core node started — publishing heartbeat on /psilia/heartbeat")

    def _publish_interface(self):
        """Publish interface description once on startup (latched — late subscribers still receive it)."""
        msg = String()
        msg.data = json.dumps({
            "version": self.psilia_version,
            "topics": self.interface_topics,
        })
        self.interface_pub.publish(msg)
        self.get_logger().info("Published interface description on /psilia/interface")

    def _heartbeat_payload(self) -> dict:
        return {
            "status": "ok",
            "stamp": self.get_clock().now().nanoseconds,
            "ros_domain_id": int(os.environ.get("ROS_DOMAIN_ID", 0)),
        }

    def _publish_heartbeat(self):
        payload = self._heartbeat_payload()
        msg = String()
        msg.data = json.dumps(payload)
        self.heartbeat_pub.publish(msg)
        self._write_file(_HEARTBEAT_FILE, payload)

    def _on_status_request(self, _msg: String):
        status = {
            **self._heartbeat_payload(),
            "ros_domain_id": int(os.environ.get("ROS_DOMAIN_ID", 0)),
            "nodes": self.get_node_names(),
            "topics": [name for name, _ in self.get_topic_names_and_types()],
        }
        self._write_file(_STATUS_FILE, status)

    def _write_file(self, path: Path, payload: dict) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload))
        except OSError as e:
            self.get_logger().warn(f"Could not write {path.name}: {e}")


def main():
    rclpy.init()
    node = CoreNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
