"""
Mock node — publishes synthetic data on /psilia/* topics.
No camera or inference required. Always available for testing.
"""
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CameraInfo
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Header
import numpy as np


class MockNode(Node):
    def __init__(self):
        super().__init__("mock_node")
        self.image_pub = self.create_publisher(Image, "/psilia/image", 10)
        self.depth_pub = self.create_publisher(Image, "/psilia/depth", 10)
        self.pose_pub = self.create_publisher(PoseStamped, "/psilia/pose", 10)
        self.timer = self.create_timer(1.0 / 30.0, self.publish)
        self.get_logger().info("Mock node started — publishing synthetic /psilia/* data")

    def publish(self):
        stamp = self.get_clock().now().to_msg()

        img = Image()
        img.header = Header(stamp=stamp, frame_id="camera")
        img.height = 480
        img.width = 640
        img.encoding = "rgb8"
        img.data = (np.random.randint(0, 256, (480, 640, 3), dtype=np.uint8)).tobytes()
        self.image_pub.publish(img)

        depth = Image()
        depth.header = Header(stamp=stamp, frame_id="camera")
        depth.height = 480
        depth.width = 640
        depth.encoding = "32FC1"
        depth.data = (np.random.rand(480, 640).astype(np.float32)).tobytes()
        self.depth_pub.publish(depth)

        pose = PoseStamped()
        pose.header = Header(stamp=stamp, frame_id="world")
        pose.pose.orientation.w = 1.0
        self.pose_pub.publish(pose)


def main():
    rclpy.init()
    node = MockNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
