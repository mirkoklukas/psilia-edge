"""
Point cloud preview node — subscribes to /psilia/stereo/depth (32FC1) and
/psilia/stereo/depth/camera_info, back-projects valid depth pixels to 3D,
and publishes on /psilia/preview/pointcloud (sensor_msgs/PointCloud2).

Parameters (set via launch file or command line):
  fps         — publish rate in Hz (default 2)
  num_samples — random subsample size (default -1, meaning all points)
"""
import time

import numpy as np

import rclpy  # type: ignore
from rclpy.node import Node  # type: ignore
from geometry_msgs.msg import TransformStamped  # type: ignore
from sensor_msgs.msg import CameraInfo, Image, PointCloud2, PointField  # type: ignore
from std_msgs.msg import Header  # type: ignore
from tf2_ros import StaticTransformBroadcaster  # type: ignore

from psilia_runtime.better_ros import better_node, ROSValue

FRAME_ID = "preview_camera"


@better_node
class PointcloudPreviewNode(Node):
    fps: ROSValue = 2
    num_samples: ROSValue = -1

    def __node_init__(self):
        self._last_publish = 0.0
        self._fx = None
        self._fy = None
        self._cx = None
        self._cy = None

        self._publish_static_tf()

        self.create_subscription(
            CameraInfo, "/psilia/stereo/depth/camera_info", self._on_camera_info, 1
        )
        self.create_subscription(Image, "/psilia/stereo/depth", self._on_depth, 1)
        self.pub = self.create_publisher(PointCloud2, "/psilia/preview/pointcloud", 1)

    def _publish_static_tf(self):
        br = StaticTransformBroadcaster(self)
        t = TransformStamped()
        t.header.stamp = self.get_clock().now().to_msg()
        t.header.frame_id = "world"
        t.child_frame_id = FRAME_ID
        # Optical frame (z-fwd, x-right, y-down) oriented so camera
        # points along world x-axis (x-fwd, y-left, z-up).
        t.transform.rotation.x = -0.5
        t.transform.rotation.y = 0.5
        t.transform.rotation.z = -0.5
        t.transform.rotation.w = 0.5
        br.sendTransform(t)

    def _on_camera_info(self, msg: CameraInfo):
        self._fx = msg.k[0]
        self._fy = msg.k[4]
        self._cx = msg.k[2]
        self._cy = msg.k[5]

    def _on_depth(self, msg: Image):
        if self._fx is None:
            return

        now = time.monotonic()
        if now - self._last_publish < 1.0 / self.fps:
            return
        self._last_publish = now

        depth = np.frombuffer(msg.data, dtype=np.float32).reshape(msg.height, msg.width)

        # Valid pixels: depth > 0.
        vs, us = np.where(depth > 0)
        z = depth[vs, us]

        xs = (us - self._cx) * z / self._fx
        ys = (vs - self._cy) * z / self._fy
        zs = z

        points = np.stack((xs, ys, zs), axis=-1).astype(np.float32)
        # Subsample without replacement.
        if self.num_samples > 0 and len(points) > self.num_samples:
            idx = np.random.choice(len(points), self.num_samples, replace=False)
            points = points[idx]

        cloud = PointCloud2()
        cloud.header = Header(stamp=msg.header.stamp, frame_id=FRAME_ID)
        cloud.height = 1
        cloud.width = len(points)
        cloud.fields = [
            PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
        ]
        cloud.is_bigendian = False
        cloud.point_step = 12
        cloud.row_step = 12 * cloud.width
        cloud.data = points.tobytes()
        cloud.is_dense = True
        self.pub.publish(cloud)


def main():
    rclpy.init()
    node = PointcloudPreviewNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
