"""Docker container lifecycle for the psilia spatial runtime (ROS layer).

# TODO: Currently psilia-specific (hardcoded container name, image, workspace from config).
#   Consider splitting into two layers:
#     - docker.py  → generic Docker utils (take container_name, image, etc. as args)
#     - core.py    → wires psilia config into those utils
#   That would make docker.py reusable and keep all psilia-specific wiring in one place.
#
# TODO: Image and ros_workspace are read from psilia.yaml. May want a dedicated
#   runtime_config once the config structure matures.
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

from psilia.edge.runtime.config import (  # noqa: E402
    CONTAINER_NAME,
    RUN_DIR,
    get_docker_image,
    get_ros_dir,
    get_log_dir,
    get_data_dir,
    get_runtime_config_path,
)
from psilia.edge.utils import run  # noqa: E402


def start_container() -> dict:
    """Start the psilia runtime container. Returns a result dict."""
    image = get_docker_image()

    status = container_status()

    if status == "running":
        return {
            "status": "already_running",
            "container": CONTAINER_NAME,
            "image": image,
        }

    if status == "exited":
        rc, _, err = _run(["docker", "rm", CONTAINER_NAME])
        if rc != 0:
            return {
                "status": "error",
                "error": f"Failed to remove stale container: {err}",
            }

    # Bind mounts:
    #   {runtime_home}/ros/        → /psilia/ros           colcon workspace
    #   {runtime_home}/log/        → /psilia/log           runtime logs
    #   {runtime_home}/data/       → /psilia/data          MCAP recordings
    #   {runtime_home}/runtime.yaml → /psilia/runtime.yaml runtime config (read-only)
    #   {RUN_DIR}/                 → /psilia/run           status files written by core_node
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    runtime_config_path = get_runtime_config_path()
    rc, _, err = _run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER_NAME,
            *_network_args(_ROS_PORTS),
            "-v",
            f"{str(get_ros_dir())}:/psilia/ros",
            "-v",
            f"{str(get_log_dir())}:/psilia/log",
            "-v",
            f"{str(get_data_dir())}:/psilia/data",
            "-v",
            f"{str(runtime_config_path)}:/psilia/runtime.yaml:ro",
            "-v",
            f"{RUN_DIR}:/psilia/run",
            image,
            "tail",
            "-f",
            "/dev/null",  # keep container alive; ROS launched via docker exec
        ]
    )
    if rc != 0:
        return {"status": "error", "error": err}

    return {"status": "started", "container": CONTAINER_NAME, "image": image}


def stop_container() -> dict:
    """Stop and remove the psilia runtime container. Returns a result dict."""
    status = container_status()

    if status == "absent":
        return {"status": "not_running"}

    rc, _, err = _run(["docker", "stop", CONTAINER_NAME])
    if rc != 0:
        return {"status": "error", "error": err}

    _run(["docker", "rm", CONTAINER_NAME])
    return {"status": "stopped"}


_WORKSPACE_READY_FILE = RUN_DIR / "workspace_ready"
_WORKSPACE_READY_TIMEOUT = 60  # seconds


def launch_ros(launch_script: str) -> dict:
    launch_cmd = (
        f"docker exec -d {CONTAINER_NAME} bash -c "
        f"'source /opt/ros/humble/setup.bash && source /psilia/ros/install/setup.bash"
        f" && ros2 launch psilia_runtime {launch_script} > /psilia/log/ros-launch.log 2>&1'"
    )
    rc, out, err = run(launch_cmd)
    if rc != 0:
        raise SystemExit(1)

    return {"status": "error", "error": err}


# def launch_ros(launch_script: str) -> dict:
#     """Launch a ROS launch file inside the running container (detached).

#     Waits for the entrypoint to finish building the workspace before launching.
#     """
#     import time as _time

#     console.print(f"Launching ROS with {launch_script}...")
#     deadline = _time.time() + _WORKSPACE_READY_TIMEOUT
#     while not _WORKSPACE_READY_FILE.exists():
#         if _time.time() > deadline:
#             return {"status": "error", "error": "timed out waiting for workspace build"}
#         _time.sleep(0.5)

#     cmd = (
#         f"docker exec -d {CONTAINER_NAME} bash -c "
#         f"'source /opt/ros/humble/setup.bash && source /psilia/ros/install/setup.bash"
#         f" && ros2 launch psilia_runtime {launch_script} > /psilia/log/ros-launch.log 2>&1'"
#     )
#     rc, _, err = run(cmd)
#     if rc != 0:

#         return {"status": "error", "error": err}


#     return {"status": "launched", "launch_script": launch_script}


def launch_ros_2(launch_script: str) -> dict:
    """Launch a ROS launch file inside the running container (detached).

    Waits for the entrypoint to finish building the workspace before launching.
    """
    import time as _time

    deadline = _time.time() + _WORKSPACE_READY_TIMEOUT
    while not _WORKSPACE_READY_FILE.exists():
        if _time.time() > deadline:
            return {"status": "error", "error": "timed out waiting for workspace build"}
        _time.sleep(0.5)

    cmd = (
        f"docker exec -d {CONTAINER_NAME} bash -c "
        f"'source /opt/ros/humble/setup.bash && source /psilia/ros/install/setup.bash"
        f" && ros2 launch psilia_runtime {launch_script} > /psilia/log/ros-launch.log 2>&1'"
    )
    rc, _, err = run(cmd)
    if rc != 0:
        return {"status": "error", "error": err}

    return {"status": "launched", "launch_script": launch_script}


def _kill_ros2_process() -> bool:
    """Find and kill the ros2 launch process inside the container.

    Returns True if a process was found and killed, False otherwise.
    """
    rc, out, _ = _run(
        [
            "docker",
            "exec",
            CONTAINER_NAME,
            "bash",
            "-c",
            "pgrep -f 'ros2 launch' | head -1",
        ]
    )
    if rc != 0 or not out.strip():
        return False
    pid = out.strip()
    rc, _, _ = _run(["docker", "exec", CONTAINER_NAME, "kill", pid])
    return rc == 0


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


# Ports the ROS layer exposes (used for macOS dev).
_ROS_PORTS = [9090]  # rosbridge WebSocket


def _run(cmd: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def is_docker_running() -> bool:
    rc, _, _ = _run(["docker", "info"])
    return rc == 0


def container_status() -> str:
    """Return container state: 'running', 'exited', or 'absent'."""
    rc, out, _ = _run(["docker", "inspect", "-f", "{{.State.Status}}", CONTAINER_NAME])
    if rc != 0:
        return "absent"
    return out or "absent"


def _ros_exec(cmd: str) -> list[str] | None:
    """Run a ROS 2 command inside the running container. Returns lines or None on failure."""
    full_cmd = f"source /opt/ros/humble/setup.bash && source /psilia/ros/install/setup.bash && {cmd}"
    rc, out, _ = _run(["docker", "exec", CONTAINER_NAME, "bash", "-c", full_cmd])
    if rc != 0 or not out:
        return None
    return [line for line in out.splitlines() if line.strip()]


def ros_nodes() -> list[str] | None:
    """Return list of running ROS nodes, or None if unavailable."""
    return _ros_exec("ros2 node list")


def ros_topics() -> list[str] | None:
    """Return list of active ROS topics, or None if unavailable."""
    return _ros_exec("ros2 topic list")


def ros_domain_id() -> int:
    """Return the ROS_DOMAIN_ID used inside the container (default 0)."""
    lines = _ros_exec("printenv ROS_DOMAIN_ID")
    if lines:
        try:
            return int(lines[0])
        except ValueError:
            pass
    return 0


# TODO: make port configurable (currently hardcoded to match rosbridge default in launch file)
_ROSBRIDGE_URL = "ws://localhost:9090"


async def _ws_publish(topic: str, msg: dict) -> None:
    import websockets

    async with websockets.connect(_ROSBRIDGE_URL) as ws:
        await ws.send(json.dumps({"op": "publish", "topic": topic, "msg": msg}))


def rosbridge_publish(topic: str, msg: dict) -> Exception | None:
    """Publish a single message to a ROS topic via the rosbridge WebSocket.

    Runs in a thread so it works both inside and outside an async event loop.
    Returns the exception if publishing failed, None on success.
    """
    import threading

    exc: list[Exception] = []

    def _run():
        try:
            asyncio.run(_ws_publish(topic, msg))
        except Exception as e:
            logger.warning("rosbridge_publish failed: %s", e)
            exc.append(e)

    t = threading.Thread(target=_run)
    t.start()
    t.join(timeout=2.0)
    return exc[0] if exc else None


def request_ros_status() -> Exception | None:
    """Ask core_node to write status.json by publishing to /psilia/status_request.

    Returns the exception if publishing failed, None on success.
    """
    return rosbridge_publish("/psilia/status_request", {"data": ""})
