"""
Depth node — subscribes to /psilia/stereo/rect/image (side-by-side stereo),
computes disparity via StereoSGBM, converts to depth, and publishes on
/psilia/stereo/depth/image (32FC1) and /psilia/stereo/depth/camera_info (rectified left camera).

Parameters (set via launch file or command line):
  calibration_file  — path to a stereo calibration YAML file (psilia or Kalibr format)
  camera_left       — camera name for the left image (default: cam0)
  camera_right      — camera name for the right image (default: cam1)
  num_disparities   — max disparity range, must be divisible by 16 (default: 128)
  block_size        — matched block size, must be odd (default: 5)
  p1                — StereoSGBM penalty for small disparity changes (default: 200)
  p2                — StereoSGBM penalty for large disparity changes (default: 800)
  uniqueness_ratio  — margin (%) for best match uniqueness, 0 to disable (default: 10)
  disp12_max_diff   — max left-right disparity difference, -1 to disable (default: 1)
  speckle_window_size — max size of smooth disparity regions for speckle filter, 0 to disable (default: 100)
  speckle_range     — max disparity variation within a speckle region (default: 32)

TODO: Compute and publish a confidence map alongside depth.
TODO: Optionally publish the raw disparity map (e.g. on /psilia/disparity).
"""
import array

import cv2
import numpy as np

import rclpy  # type: ignore
from rclpy.node import Node  # type: ignore
from sensor_msgs.msg import CameraInfo, Image  # type: ignore

from psilia_runtime.better_ros import better_node, ROSValue
from psilia_runtime.camera import StereoCalibration


@better_node
class DepthNode(Node):
    calibration_file: ROSValue = ""
    camera_left: ROSValue = "cam0"
    camera_right: ROSValue = "cam1"
    num_disparities: ROSValue = 128
    block_size: ROSValue = 5
    p1: ROSValue = 200
    p2: ROSValue = 800
    uniqueness_ratio: ROSValue = 10
    disp12_max_diff: ROSValue = 1
    speckle_window_size: ROSValue = 100
    speckle_range: ROSValue = 32

    def __node_init__(self):
        if not self.calibration_file:
            self.get_logger().error("No calibration_file parameter set.")
            return

        self._stereo_cal = StereoCalibration.load(self.calibration_file, strict=False).rectify()
        self._ready = False

        self.pub = self.create_publisher(Image, "/psilia/stereo/depth/image", 1)
        self.pub_info = self.create_publisher(CameraInfo, "/psilia/stereo/depth/camera_info", 1)
        self._camera_info = None
        self.create_subscription(Image, "/psilia/stereo/rect/image", self.on_image, 1)

    def _setup_depth(self, frame_width: int, frame_height: int):
        """Initialize depth computation, rescaling calibration if needed."""
        eye_w = frame_width // 2
        stereo = self._stereo_cal

        if eye_w != stereo.cam0.width or frame_height != stereo.cam0.height:
            factor = eye_w / stereo.cam0.width
            self.get_logger().info(
                f"Rescaling calibration: {stereo.cam0.width}x{stereo.cam0.height} → {eye_w}x{frame_height} "
                f"(factor={factor:.3f})"
            )
            stereo = StereoCalibration(
                stereo.cam0.rescale(factor), stereo.cam1.rescale(factor)
            ).rectify()

        Q = stereo.disparity_to_3d
        self.focal_length = Q[2, 3]
        self.baseline = abs(1.0 / Q[3, 2])
        self.width = stereo.cam0.width
        self.height = stereo.cam0.height
        self._ready = True

        # Build CameraInfo for the rectified left camera (depth viewpoint).
        cal0 = stereo.cam0
        info = CameraInfo()
        info.header.frame_id = "camera"
        info.width = cal0.width
        info.height = cal0.height
        info.distortion_model = "plumb_bob"
        info.d = [0.0, 0.0, 0.0, 0.0, 0.0]
        info.k = cal0.P_rect[:3, :3].flatten().tolist()
        info.r = cal0.R_rect.flatten().tolist()
        info.p = cal0.P_rect.flatten().tolist()
        self._camera_info = info

        self._stereo = cv2.StereoSGBM_create(
            minDisparity=0,
            numDisparities=self.num_disparities,
            blockSize=self.block_size,
            P1=self.p1,
            P2=self.p2,
            disp12MaxDiff=self.disp12_max_diff,
            uniquenessRatio=self.uniqueness_ratio,
            speckleWindowSize=self.speckle_window_size,
            speckleRange=self.speckle_range,
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

    def on_image(self, msg: Image):
        if not self._ready:
            self._setup_depth(msg.width, msg.height)
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

        self._camera_info.header = msg.header
        self.pub_info.publish(self._camera_info)


def main():
    rclpy.init()
    node = DepthNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
