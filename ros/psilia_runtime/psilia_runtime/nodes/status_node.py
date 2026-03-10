"""
Status node — publishes a system heartbeat and a static info message.

/psilia/status  (1 Hz)        — heartbeat with timestamp
/psilia/info    (latched)      — static info broadcast on startup;
                                 any node subscribing later still receives it.

TODO: extend /psilia/status payload with system metrics:
  - cpu_percent     (psutil.cpu_percent())
  - memory_percent  (psutil.virtual_memory().percent)
  - disk_free_gb    (shutil.disk_usage("/ssd").free / 1e9)
  - temperature_c   (read from /sys/class/thermal/thermal_zone*/temp on Jetson)
"""
import json
import os

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, DurabilityPolicy
from std_msgs.msg import String

_LATCHED = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)


class StatusNode(Node):
    def __init__(self):
        super().__init__("status_node")

        self.pub = self.create_publisher(String, "/psilia/status", 10)
        self.info_pub = self.create_publisher(String, "/psilia/info", _LATCHED)

        self._publish_info()
        self.timer = self.create_timer(1.0, self.publish)
        self.get_logger().info("Status node started — publishing heartbeat on /psilia/status")

    def _publish_info(self):
        """Publish static info once on startup (latched — late subscribers still receive it)."""
        # Read runtime config if available
        config: dict = {}
        config_path = "/etc/psilia/device_config.yaml"
        if os.path.exists(config_path):
            try:
                import yaml
                with open(config_path) as f:
                    config = yaml.safe_load(f) or {}
            except Exception:
                pass

        msg = String()
        msg.data = json.dumps({
            "version": "0.1.1",
            "camera": config.get("camera", {}),
            "topics": ["/psilia/image", "/psilia/depth", "/psilia/pose", "/psilia/status"],
            "ros_workspace": config.get("runtime", {}).get("ros_workspace"),
        })
        self.info_pub.publish(msg)
        self.get_logger().info("Published static info on /psilia/info")

    def publish(self):
        msg = String()
        msg.data = json.dumps({
            "status": "ok",
            "stamp": self.get_clock().now().nanoseconds,
        })
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = StatusNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
