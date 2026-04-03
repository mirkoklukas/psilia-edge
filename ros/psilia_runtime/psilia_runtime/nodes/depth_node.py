"""
Depth node — subscribes to /psilia/image/rectified (side-by-side stereo),
computes disparity via StereoSGBM, converts to depth, and publishes on /psilia/depth.

Parameters (set via launch file or command line):
  calibration_file  — path to a Kalibr calibration-camchain YAML file
  camera_left       — camera name for the left image (default: cam0)
  camera_right      — camera name for the right image (default: cam1)
  num_disparities   — max disparity range, must be divisible by 16 (default: 128)
  block_size        — matched block size, must be odd (default: 5)

TODO: Replace Kalibr camchain format with our own calibration format.
TODO: Compute and publish a confidence map alongside depth.
TODO: Optionally publish the raw disparity map (e.g. on /psilia/disparity).
"""
import array

import cv2
import numpy as np

import rclpy  # type: ignore
from rclpy.node import Node  # type: ignore
from sensor_msgs.msg import Image  # type: ignore

from psilia_runtime.better_ros import better_node, ROSValue
from psilia_runtime.camera_calibration import CameraCalibration


@better_node
class DepthNode(Node):
    calibration_file: ROSValue = ""
    camera_left: ROSValue = "cam0"
    camera_right: ROSValue = "cam1"
    num_disparities: ROSValue = 128
    block_size: ROSValue = 5

    def __node_init__(self):
        if not self.calibration_file:
            self.get_logger().error("No calibration_file parameter set.")
            return

        cal0 = CameraCalibration.from_kalibr(self.calibration_file, self.camera_left)
        cal1 = CameraCalibration.from_kalibr(self.calibration_file, self.camera_right)
        rect = CameraCalibration.stereo_rectification(cal0, cal1)

        # Extract focal length and baseline from the Q matrix.
        # Q[2,3] = focal length, Q[3,2] = -1/baseline
        self.focal_length = rect.Q[2, 3]
        self.baseline = abs(1.0 / rect.Q[3, 2])
        self.width = cal0.width
        self.height = cal0.height
        self._ready = True

        self._stereo = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=self.num_disparities,
            blockSize=self.block_size,
            P1=8 * 3 * self.block_size ** 2,
            P2=32 * 3 * self.block_size ** 2,
            disp12MaxDiff=1,
            uniquenessRatio=10,
            speckleWindowSize=100,
            speckleRange=32,
        )

        # Pre-allocated publish buffer for depth (32FC1 = 4 bytes per pixel).
        # _np_buf is a float32 view into the uint8 _buf (shared memory).
        buf_size = self.width * self.height * 4
        self._buf = array.array('B', bytes(buf_size))
        self._np_buf = np.frombuffer(self._buf, dtype=np.float32).reshape(
            self.height, self.width
        )

        self.get_logger().info(
            f"Depth node ready: f={self.focal_length:.1f} baseline={self.baseline:.4f}m "
            f"num_disparities={self.num_disparities} block_size={self.block_size}"
        )

        self.pub = self.create_publisher(Image, "/psilia/depth", 10)
        self.create_subscription(Image, "/psilia/image/rectified", self.on_image, 10)

    def on_image(self, msg: Image):
        if not self._ready:
            return

        frame = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
        left = frame[:, :self.width]
        right = frame[:, self.width:]

        gray_l = cv2.cvtColor(left, cv2.COLOR_BGR2GRAY)
        gray_r = cv2.cvtColor(right, cv2.COLOR_BGR2GRAY)

        # compute() returns fixed-point disparity scaled by 16.
        disparity = self._stereo.compute(gray_l, gray_r).astype(np.float32) / 16.0

        # depth = f * baseline / disparity (invalid where disparity <= 0).
        valid = disparity > 0
        self._np_buf[:] = 0.0
        self._np_buf[valid] = (self.focal_length * self.baseline) / disparity[valid]

        out = Image()
        out.header = msg.header
        out.height = self.height
        out.width = self.width
        out.encoding = "32FC1"
        out.step = self.width * 4
        out.data = self._buf
        self.pub.publish(out)


def main():
    rclpy.init()
    node = DepthNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
