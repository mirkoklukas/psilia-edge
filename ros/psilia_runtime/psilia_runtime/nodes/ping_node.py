"""
Ping node — dev tool for testing ROS connectivity.

/psilia/ping  (subscribed)  — listens for ping messages
/psilia/pong  (published)   — echoes back with message "pong" when a ping is received
"""
import json

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class PingNode(Node):
    def __init__(self):
        super().__init__("psilia_ping")

        self.pong_pub = self.create_publisher(String, "/psilia/pong", 10)
        self.create_subscription(String, "/psilia/ping", self._on_ping, 10)

        self.get_logger().info("Ping node started — listening on /psilia/ping")

    def _on_ping(self, msg: String):
        reply = String()
        reply.data = json.dumps({
            "message": "pong",
            "timestamp": self.get_clock().now().nanoseconds,
        })
        self.pong_pub.publish(reply)


def main():
    rclpy.init()
    node = PingNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
