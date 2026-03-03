"""
Pose node — wraps psilia.pose and publishes on /psilia/pose.
Requires psilia installed inside the Docker image.
"""
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from sensor_msgs.msg import Image


class PoseNode(Node):
    def __init__(self):
        super().__init__("pose_node")
        # TODO: initialise psilia.pose estimator
        # TODO: subscribe to camera topic
        self.pose_pub = self.create_publisher(PoseStamped, "/psilia/pose", 10)
        self.get_logger().info("Pose node started")

    def on_image(self, msg: Image):
        # TODO: run psilia.pose on msg, publish result
        pass


def main():
    rclpy.init()
    node = PoseNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
