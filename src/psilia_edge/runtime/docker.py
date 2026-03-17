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


def launch_runtime_container(launch_script: str) -> tuple[int, str, str]:
    """Starts a new docker container and launches the given ROS launch script.
    Returns a result dict."""

    # TODO: we should check all that before.
    # Ensure RUN_DIR exists for container volume mount
    RUN_DIR.mkdir(parents=True, exist_ok=True)

    cmd = (
        f"docker run -i -d --rm "
        # --privileged gives access to host USB devices (cameras, serial ports).
        # TODO: --privileged has no effect on macOS (Docker Desktop runs in a VM,
        #   USB devices are not forwarded). Figure out a dev workflow for USB on Mac.
        f"--privileged "
        # Depends on the platform, we may need to
        # expose ROS ports instead of using --network host
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
        f"{get_docker_image()} {launch_script}"
    )
    rc, out, err = run(cmd)
    return rc, out, err


def stop_runtime_container() -> tuple[int, str, str]:
    return run(f"docker stop {CONTAINER_NAME}")


def docker_exec(cmd: str) -> tuple[int, str, str]:
    """Executes a bash command inside the running ROS container."""
    full_cmd = (
        f"docker exec -i "
        f"{CONTAINER_NAME} "
        f"/init.sh "
        # Using bash -lc to ensure we get the full environment,
        # init should do that, but just in case
        f'bash -lc "{cmd}"'
    )
    rc, out, err = run(full_cmd)
    return rc, out, err


def is_container_running() -> bool:
    rc, out, _ = run(f"docker inspect -f {{{{.State.Running}}}} {CONTAINER_NAME}")
    return rc == 0 and out.strip() == "true"


def is_docker_daemon_running() -> bool:
    # TODO: `docker info` is slow (~1-2s). Consider `docker ps -q` or checking
    #   the Docker socket directly. Also evaluate if this check is needed at all.
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
    Port mappings are ignored (and unnecessary) in host network mode.

    On macOS (Docker Desktop), --network host goes through a VM and ports are NOT
    forwarded to the Mac host. We fall back to explicit -p mappings instead.
    """
    if sys.platform == "linux":
        return ["--network", "host"]
    # macOS / other: map each port explicitly
    args = []
    for port in ports:
        args += ["-p", f"{port}:{port}"]
    return args


def is_port_open(port: int) -> bool:
    """Return True if the WebSocket port is reachable."""
    import socket

    try:
        with socket.create_connection(("localhost", port), timeout=1.0):
            return True
    except OSError:
        return False


# async def _ws_publish(topic: str, msg: dict) -> None:
#     import websockets

#     async with websockets.connect(_ROSBRIDGE_URL) as ws:
#         await ws.send(json.dumps({"op": "publish", "topic": topic, "msg": msg}))


# def rosbridge_publish(topic: str, msg: dict) -> Exception | None:
#     """Publish a single message to a ROS topic via the rosbridge WebSocket.

#     Runs in a thread so it works both inside and outside an async event loop.
#     Returns the exception if publishing failed, None on success.
#     """
#     import threading

#     exc: list[Exception] = []

#     def _run():
#         try:
#             asyncio.run(_ws_publish(topic, msg))
#         except Exception as e:
#             logger.warning("rosbridge_publish failed: %s", e)
#             exc.append(e)

#     t = threading.Thread(target=_run)
#     t.start()
#     t.join(timeout=2.0)
#     return exc[0] if exc else None


# def request_ros_status() -> Exception | None:
#     """Ask core_node to write status.json by publishing to /psilia/status_request.

#     Returns the exception if publishing failed, None on success.
#     """
#     return rosbridge_publish("/psilia/status_request", {"data": ""})
