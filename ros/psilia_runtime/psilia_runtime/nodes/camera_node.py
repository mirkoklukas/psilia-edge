"""
Camera node — reads from a UVC camera and publishes on /psilia/image/raw.

Parameters (set via launch_params.yaml):
  device        — /dev/video path (e.g. /dev/video0)
  pixel_format  — capture format: MJPG or YUYV
  width         — capture width in pixels
  height        — capture height in pixels
  fps           — capture frame rate

Frame capture runs in a dedicated thread so that cap.read() blocking never
stalls the ROS timer. The timer only picks up the latest frame and publishes.

If the device cannot be opened, the node logs a warning and retries every second.
"""
import threading

import rclpy
import cv2
from rclpy.node import Node # type: ignore
from sensor_msgs.msg import Image # type: ignore
from std_msgs.msg import Header # type: ignore
from psilia_runtime.better_ros import better_node, ROSValue

_FOURCC = {
    "MJPG": cv2.VideoWriter_fourcc("M", "J", "P", "G"),
    "YUYV": cv2.VideoWriter_fourcc("Y", "U", "Y", "V"),
}


@better_node
class CameraNode(Node):
    device: ROSValue = "/dev/video0"
    pixel_format: ROSValue = "MJPG"
    width: ROSValue = 640
    height: ROSValue = 480
    fps: ROSValue = 30

    def __node_init__(self):
        self.pub = self.create_publisher(Image, "/psilia/image/raw", 10)
        self.cap = None
        self._latest_frame = None
        self._frame_lock = threading.Lock()
        self._stop_capture = threading.Event()
        self._capture_thread = None
        self.frame_count = 0
        self.open_camera()
        self.create_timer(1.0 / self.fps, self.publish_frame)

    def open_camera(self) -> bool:
        # Stop any existing capture thread before (re)opening
        self._stop_capture.set()
        if self._capture_thread is not None:
            self._capture_thread.join(timeout=2.0)

        self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        if not self.cap.isOpened():
            self.get_logger().warn(f"Could not open camera device: {self.device}")
            self.cap = None
            return False

        fourcc = _FOURCC.get(self.pixel_format)
        if fourcc:
            self.cap.set(cv2.CAP_PROP_FOURCC, fourcc)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        self.get_logger().info(
            f"Camera requesting configuration: {self.device} "
            f"({self.pixel_format} {self.width}x{self.height} @ {self.fps}fps)"
        )

        cfg_fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC))
        cfg_fmt    = "".join(chr((cfg_fourcc >> (8 * i)) & 0xFF) for i in range(4)).strip("\x00")
        cfg_width  = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        cfg_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cfg_fps    = self.cap.get(cv2.CAP_PROP_FPS)
        self.get_logger().info(
            f"Camera configured: {cfg_fmt} {cfg_width}x{cfg_height} @ {cfg_fps:.1f}fps"
        )

        self._stop_capture.clear()
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()
        return True

    def _capture_loop(self):
        while not self._stop_capture.is_set():
            ret, frame = self.cap.read()
            if not ret:
                self.get_logger().warn("Capture thread: failed to read frame — reopening camera")
                self.cap.release()
                self.cap = None
                return  # publish_frame will detect cap is None and call open_camera()
            with self._frame_lock:
                self._latest_frame = frame

    def publish_frame(self):
        if self.cap is None:
            self.open_camera()
            return

        with self._frame_lock:
            frame = self._latest_frame
            self._latest_frame = None  # mark consumed — don't republish stale frames

        if frame is None:
            return  # no new frame since last publish

        stamp = self.get_clock().now().to_msg()
        msg = Image()
        msg.header = Header(stamp=stamp, frame_id="camera")
        msg.height, msg.width = frame.shape[:2]
        msg.encoding = "bgr8"
        msg.step = msg.width * 3
        msg.data = frame.tobytes()
        self.pub.publish(msg)
        self.frame_count += 1
        if self.frame_count % 100 == 0:
            self.get_logger().info(f"Frame {self.frame_count}: {msg.width}x{msg.height} ({msg.encoding})")


def main():
    rclpy.init()
    node = CameraNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
