"""
Depth node — wraps psilia.depth and publishes on /psilia/depth.
Requires psilia installed inside the Docker image.
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import Header


class DepthNode(Node):
    def __init__(self):
        super().__init__("depth_node")
        # TODO: initialise psilia.depth estimator
        # TODO: subscribe to camera topic
        self.depth_pub = self.create_publisher(Image, "/psilia/depth", 10)
        self.get_logger().info("Depth node started")

    def on_image(self, msg: Image):
        # TODO: run psilia.depth on msg, publish result
        pass


def main():
    rclpy.init()
    node = DepthNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
