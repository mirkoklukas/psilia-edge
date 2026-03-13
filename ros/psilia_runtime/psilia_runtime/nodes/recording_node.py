import json
import socket
import subprocess
from datetime import datetime
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String


class RecordingNode(Node):
    """Manages rosbag recording triggered by the web UI.

    Subscribes to start/stop topics and spawns `ros2 bag record`
    as a subprocess.
    """

    def __init__(self):
        super().__init__('recording_node')

        self.device = socket.gethostname().split('.')[0]
        self.recordings_dir = Path('/psilia/data/')
        self.process = None
        self._storage = 'mcap' if self._mcap_available() else 'sqlite3'

        self.status_pub = self.create_publisher(
            Bool, '/psilia/recording/status', 10)

        self.create_subscription(
            String, '/psilia/web/recording/start',
            self.start_callback, 10)

        self.create_subscription(
            String, '/psilia/web/recording/stop',
            self.stop_callback, 10)

        self.timer = self.create_timer(1.0, self.publish_status)

        self.get_logger().info('Recording node started')

    def start_callback(self, msg):
        """Start a recording. msg.data is expected to be a JSON string:

            {
                "session": "crimson-falcon",   # session name
                "topics":  ["/psilia/image"]   # list of topics to record (required)
            }
        """
        if self.process is not None:
            self.get_logger().warn('Recording already in progress, ignoring start')
            return

        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError as e:
            self.get_logger().error(f'Invalid JSON: {e}')
            return

        topics = data.get('topics', [])
        if not topics:
            self.get_logger().warn('No topics specified, ignoring start')
            return

        fname = data.get('fname', None) or self._make_fname(data)
        output_path = self.recordings_dir / fname

        cmd = ['ros2', 'bag', 'record', '-s', self._storage, '-o', str(output_path)] + topics

        self.get_logger().info(f'Starting recording: {output_path}')
        self.get_logger().info(f'Topics: {topics}')
        self.process = subprocess.Popen(cmd)

    @staticmethod
    def _mcap_available() -> bool:
        result = subprocess.run(
            ['ros2', 'pkg', 'prefix', 'rosbag2_storage_mcap'],
            capture_output=True,
        )
        return result.returncode == 0

    def _make_fname(self, data: dict) -> str:
        """Build a recording name: {device}_{session}_{counter}_{time}."""
        session = data.get('session', 'session')
        counter = self._next_counter(self.device, session)
        time    = datetime.now().strftime('%Y-%m-%d_%H-%M')
        return f'{self.device}_{session}_{counter}_{time}'

    def _next_counter(self, device: str, session: str) -> int:
        """Scan recordings_dir for {device}_{session}_N_* directories and return N+1."""
        matches = self.recordings_dir.glob(f'{device}_{session}_[0-9]*_*')
        counters = []
        for p in matches:
            try:
                counters.append(int(p.name.split('_')[2]))
            except (IndexError, ValueError):
                pass
        return max(counters, default=-1) + 1

    def publish_status(self):
        # poll() returns None if the process is still running, or an exit code
        # if it has terminated. Clean up if the recording process exited unexpectedly.
        if self.process is not None and self.process.poll() is not None:
            self.get_logger().warn('Recording process exited unexpectedly')
            self.process = None

        msg = Bool()
        msg.data = self.process is not None
        self.status_pub.publish(msg)

    def stop_callback(self, msg):
        if self.process is None:
            self.get_logger().warn('No recording in progress, ignoring stop')
            return

        self.get_logger().info('Stopping recording')
        self.process.terminate()
        self.process.wait()
        self.process = None
        self.get_logger().info('Recording stopped')


def main(args=None):
    rclpy.init(args=args)
    node = RecordingNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node.process is not None:
            node.process.terminate()
            node.process.wait()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
