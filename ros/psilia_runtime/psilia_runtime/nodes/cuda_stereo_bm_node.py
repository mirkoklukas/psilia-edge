"""
CUDA stereo BM node — same role as depth_cuda_node, but uses
cv::cuda::StereoBM (block matching) instead of StereoSGM.

Subscribes to /psilia/stereo/raw/image (side-by-side stereo), rectifies
and computes depth entirely on GPU, and publishes on
/psilia/stereo/depth/image (32FC1) and /psilia/stereo/depth/camera_info
(rectified left camera). Same topics as depth_cuda_node — only one of
the two should be enabled at a time via runtime.yaml's ros.nodes.

Parameters (set via launch file or command line):
  calibration_file  — path to a stereo calibration YAML file (psilia or Kalibr format)
  camera_left       — camera name for the left image (default: cam0)
  camera_right      — camera name for the right image (default: cam1)
  num_disparities   — max disparity range, multiple of 8 (default: 128)
  block_size        — matching block size, odd, 5-51 (default: 19)
  publish_rectified — publish rectified side-by-side image for debugging (default: false)
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
class CudaStereoBmNode(Node):
    calibration_file: ROSValue = ""
    camera_left: ROSValue = "cam0"
    camera_right: ROSValue = "cam1"
    num_disparities: ROSValue = 128
    block_size: ROSValue = 19
    publish_rectified: ROSValue = False

    def __node_init__(self):
        if not self.calibration_file:
            self.get_logger().error("No calibration_file parameter set.")
            return

        if not cv2.cuda.getCudaEnabledDeviceCount():
            self.get_logger().error("No CUDA device found — cannot run cuda_stereo_bm_node.")
            return

        self._stereo_cal = StereoCalibration.load(self.calibration_file, strict=False).rectify(force=True)
        self._ready = False

        self.pub = self.create_publisher(Image, "/psilia/stereo/depth/image", 1)
        self.pub_info = self.create_publisher(CameraInfo, "/psilia/stereo/depth/camera_info", 1)
        self._camera_info = None
        self.pub_rect = None
        self._pub_rect_info_left = None
        self._pub_rect_info_right = None
        if self.publish_rectified:
            self.pub_rect = self.create_publisher(Image, "/psilia/stereo/rect/image", 1)
            self._pub_rect_info_left = self.create_publisher(CameraInfo, "/psilia/stereo/rect/left/camera_info", 1)
            self._pub_rect_info_right = self.create_publisher(CameraInfo, "/psilia/stereo/rect/right/camera_info", 1)
        self.create_subscription(Image, "/psilia/stereo/raw/image", self.on_image, 1)

    def _setup_depth(self, frame_width: int, frame_height: int):
        """Initialize GPU rectification maps, stereo matcher, and buffers."""
        eye_w = frame_width // 2
        stereo = self._stereo_cal

        if eye_w != stereo.cam0.width or frame_height != stereo.cam0.height:
            factor = eye_w / stereo.cam0.width
            self.get_logger().info(
                f"Rescaling calibration: {stereo.cam0.width}x{stereo.cam0.height} -> {eye_w}x{frame_height} "
                f"(factor={factor:.3f})"
            )
            stereo = StereoCalibration(
                stereo.cam0.rescale(factor), stereo.cam1.rescale(factor)
            ).rectify(force=True)

        Q = stereo.disparity_to_3d
        self.focal_length = Q[2, 3]
        self.baseline = abs(1.0 / Q[3, 2])
        self.width = stereo.cam0.width
        self.height = stereo.cam0.height

        # Build GPU remap tables as separate x,y float maps (CV_32FC1).
        cal0, cal1 = stereo.cam0, stereo.cam1
        map1_l, map2_l = cv2.initUndistortRectifyMap(
            cal0.K, np.array(cal0.d), cal0.R_rect, cal0.P_rect, cal0.res, cv2.CV_32FC1
        )
        map1_r, map2_r = cv2.initUndistortRectifyMap(
            cal1.K, np.array(cal1.d), cal1.R_rect, cal1.P_rect, cal1.res, cv2.CV_32FC1
        )

        self._gpu_map1_l = cv2.cuda.GpuMat(map1_l)
        self._gpu_map2_l = cv2.cuda.GpuMat(map2_l)
        self._gpu_map1_r = cv2.cuda.GpuMat(map1_r)
        self._gpu_map2_r = cv2.cuda.GpuMat(map2_r)

        # CUDA stereo matcher (block matching).
        self._stereo = cv2.cuda.createStereoBM(
            numDisparities=self.num_disparities,
            blockSize=self.block_size,
        )
        # cv::cuda::StereoBM::compute requires an explicit Stream in this
        # OpenCV build (StereoSGM accepts the 2-arg form; BM does not).
        self._stream = cv2.cuda.Stream()

        # Pre-allocated GPU mat for frame upload.
        self._gpu_frame = cv2.cuda.GpuMat()

        # Build CameraInfo for the rectified left camera (depth viewpoint).
        self._camera_info = self._build_rect_camera_info(cal0)

        # Build CameraInfo for rectified stereo pair (published when publish_rectified=true).
        if self.publish_rectified:
            self._rect_info_left = self._build_rect_camera_info(cal0)
            self._rect_info_right = self._build_rect_camera_info(cal1)

        # Pre-allocated publish buffer for depth (32FC1 = 4 bytes per pixel).
        buf_size = self.width * self.height * 4
        self._buf = array.array('B', bytes(buf_size))
        self._np_buf = np.frombuffer(self._buf, dtype=np.float32).reshape(
            self.height, self.width
        )

        self._ready = True
        self.get_logger().info(
            f"CUDA stereo BM node ready: f={self.focal_length:.1f} baseline={self.baseline:.4f}m "
            f"num_disparities={self.num_disparities} block_size={self.block_size}"
        )

    def _build_rect_camera_info(self, cal) -> CameraInfo:
        # CameraInfo for an already-rectified image: K, D describe the
        # rectified (virtual) camera, R is identity (no further rotation
        # needed), P carries the projection (with baseline term for the
        # right camera in stereo).
        info = CameraInfo()
        info.header.frame_id = "camera"
        info.width = cal.width
        info.height = cal.height
        info.distortion_model = "plumb_bob"
        info.d = [0.0, 0.0, 0.0, 0.0, 0.0]
        info.k = cal.P_rect[:3, :3].flatten().tolist()
        info.r = np.eye(3).flatten().tolist()
        info.p = cal.P_rect.flatten().tolist()
        return info

    def on_image(self, msg: Image):
        if not self._ready:
            self._setup_depth(msg.width, msg.height)
            if not self._ready:
                return

        # Upload raw side-by-side frame to GPU.
        frame = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, 3)
        self._gpu_frame.upload(frame)

        # Split left/right on GPU.
        gpu_left = cv2.cuda.GpuMat(self._gpu_frame, (0, 0, self.width, self.height))
        gpu_right = cv2.cuda.GpuMat(self._gpu_frame, (self.width, 0, self.width, self.height))

        # Rectify on GPU in color (separate xmap/ymap, both CV_32FC1).
        self._gpu_rect_l = cv2.cuda.remap(
            gpu_left, self._gpu_map1_l, self._gpu_map2_l,
            cv2.INTER_LINEAR,
        )
        self._gpu_rect_r = cv2.cuda.remap(
            gpu_right, self._gpu_map1_r, self._gpu_map2_r,
            cv2.INTER_LINEAR,
        )

        # Convert to grayscale for stereo matching (StereoBM requires CV_8UC1).
        gpu_gray_l = cv2.cuda.cvtColor(self._gpu_rect_l, cv2.COLOR_BGR2GRAY)
        gpu_gray_r = cv2.cuda.cvtColor(self._gpu_rect_r, cv2.COLOR_BGR2GRAY)

        # Stereo matching on GPU. cv::cuda::StereoBM requires explicit stream.
        gpu_disparity = self._stereo.compute(gpu_gray_l, gpu_gray_r, self._stream)
        self._stream.waitForCompletion()

        # Download disparity and compute depth on CPU.
        # cv::cuda::StereoBM returns CV_8U (0..numDisparities), unlike SGM which
        # returns CV_16S in fixed-point (Q4) and needs /16.
        disparity = gpu_disparity.download().astype(np.float32)
        self.get_logger().info(
            f"disp min={disparity.min():.2f} "
            f"max={disparity.max():.2f} "
            f"valid={np.count_nonzero(disparity > 0)}/{disparity.size}")

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

        if self.pub_rect is not None:
            rect_l = self._gpu_rect_l.download()
            rect_r = self._gpu_rect_r.download()
            rect_sbs = np.hstack((rect_l, rect_r))
            rect_msg = Image()
            rect_msg.header = msg.header
            rect_msg.height = rect_sbs.shape[0]
            rect_msg.width = rect_sbs.shape[1]
            rect_msg.encoding = "bgr8"
            rect_msg.step = rect_sbs.shape[1] * 3
            rect_msg.data = rect_sbs.tobytes()
            self.pub_rect.publish(rect_msg)

            self._rect_info_left.header = msg.header
            self._rect_info_right.header = msg.header
            self._pub_rect_info_left.publish(self._rect_info_left)
            self._pub_rect_info_right.publish(self._rect_info_right)


def main():
    rclpy.init()
    node = CudaStereoBmNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
