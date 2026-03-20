import logging
import platform
import sys

logger = logging.getLogger(__name__)

from psilia_edge.runtime.config import (  # noqa: E402
    CONFIG_PATH,
    CONTAINER_NAME,
    RUN_DIR,
    get_ros_dir,
    get_log_dir,
    get_data_dir,
    get_docker_image,
    get_rosbridge_port,
    get_runtime_config_path,
)
from psilia_edge.utils import run  # noqa: E402


def start_runtime_container() -> tuple[int, str, str]:
    """Start the runtime container with prep_ros.sh (build + idle).

    The spatial layer (ros2 launch) is started separately via start_ros_launch().
    """
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    cmd = (
        f"docker run -i -d --rm "
        f"--privileged "
        f"{' '.join(_network_args([get_rosbridge_port()]))} "
        f"-v {str(get_ros_dir())}:/psilia/ros "
        f"-v {str(get_log_dir())}:/psilia/log "
        f"-v {str(get_data_dir())}:/psilia/data "
        f"-v {str(get_runtime_config_path())}:/psilia/runtime.yaml:ro "
        f"-v {str(CONFIG_PATH)}:/psilia/psilia.yaml:ro "
        f"-v {RUN_DIR}:/psilia/run "
        f"-e ROS_LOG_DIR=/psilia/log "
        f"-e RCUTILS_LOGGING_USE_STDOUT=1 "
        f"--hostname {platform.node().split('.')[0]} "
        f"--name {CONTAINER_NAME} "
        f"{get_docker_image()}"
    )
    return run(cmd)


def stop_runtime_container() -> tuple[int, str, str]:
    """Stop the runtime container."""
    return run(f"docker stop {CONTAINER_NAME}")


def start_ros_launch(launch_script: str) -> tuple[int, str, str]:
    """Launch ros2 inside the running container via docker exec.

    Runs detached so the call returns immediately.
    """
    return run(f"docker exec -d {CONTAINER_NAME} /launch_ros.sh {launch_script}")


def stop_ros_launch() -> tuple[int, str, str]:
    """Send SIGINT to the ros2 launch process inside the container."""
    return run(f"docker exec {CONTAINER_NAME} pkill -SIGINT -f 'ros2 launch'")


def is_ros_launch_running() -> bool:
    """Return True if ros2 launch is running inside the container."""
    rc, out, _ = run(f"docker exec {CONTAINER_NAME} pgrep -f 'ros2 launch'")
    return rc == 0 and bool(out.strip())


def docker_exec(cmd: str) -> tuple[int, str, str]:
    """Executes a bash command inside the running ROS container."""
    full_cmd = f'docker exec -i {CONTAINER_NAME} /init.sh bash -lc "{cmd}"'
    rc, out, err = run(full_cmd)
    return rc, out, err


def is_container_running() -> bool:
    rc, out, _ = run(f"docker inspect -f {{{{.State.Running}}}} {CONTAINER_NAME}")
    return rc == 0 and out.strip() == "true"


def is_docker_daemon_running() -> bool:
    rc, _, _ = run("docker info")
    return rc == 0


def check_container_status() -> str:
    """Return container state: 'running', 'exited', or 'absent'."""
    rc, out, _ = run(f"docker inspect -f {{{{.State.Status}}}} {CONTAINER_NAME}")
    if rc != 0:
        return "absent"
    return out.strip() or "absent"


def list_ros_nodes() -> list[str] | None:
    """Return list of running ROS nodes, or None if unavailable."""
    rc, out, _ = docker_exec("ros2 node list")
    if rc != 0:
        return None
    return [line for line in out.splitlines() if line.strip()]


def list_ros_topics() -> list[str] | None:
    """Return list of active ROS topics, or None if unavailable."""
    rc, out, _ = docker_exec("ros2 topic list")
    if rc != 0:
        return None
    return [line for line in out.splitlines() if line.strip()]


def get_ros_domain_id() -> int:
    """Return the ROS_DOMAIN_ID used inside the container (default 0)."""
    rc, out, _ = docker_exec("printenv ROS_DOMAIN_ID")
    if rc == 0:
        try:
            return int(out.strip())
        except ValueError:
            pass
    return 0


def _network_args(ports: list[int]) -> list[str]:
    """Return docker network arguments for the current platform.

    On Linux (Jetson) we use --network host so ROS nodes share the host network
    stack and can communicate with other nodes on the same ROS domain.

    On macOS (Docker Desktop), --network host goes through a VM and ports are NOT
    forwarded to the Mac host. We fall back to explicit -p mappings instead.
    """
    if sys.platform == "linux":
        return ["--network", "host"]
    args = []
    for port in ports:
        args += ["-p", f"{port}:{port}"]
    return args


def get_ros_log_path():
    """Return the path to the ROS launch log file on the host."""
    return get_log_dir() / "ros.log"


def is_port_open(port: int) -> bool:
    """Return True if the given port is reachable on localhost."""
    import socket

    try:
        with socket.create_connection(("localhost", port), timeout=1.0):
            return True
    except OSError:
        return False
