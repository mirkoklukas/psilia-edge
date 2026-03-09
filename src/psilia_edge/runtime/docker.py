"""Docker container lifecycle for the psilia spatial runtime (ROS layer)."""

from __future__ import annotations

import subprocess

CONTAINER_NAME = "psilia-runtime"


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


def start_container(image: str, ros_workspace: str) -> dict:
    """Start the psilia runtime container. Returns a result dict."""
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

    rc, _, err = _run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            CONTAINER_NAME,
            "--network",
            "host",
            "-v",
            f"{ros_workspace}:/opt/psilia/ros",
            image,
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


def _ros_exec(cmd: str) -> list[str] | None:
    """Run a ROS 2 command inside the running container. Returns lines or None on failure."""
    rc, out, _ = _run(
        [
            "docker",
            "exec",
            CONTAINER_NAME,
            "bash",
            "-l",
            "-c",
            cmd,
        ]
    )
    if rc != 0 or not out:
        return None
    return [line for line in out.splitlines() if line.strip()]


def ros_nodes() -> list[str] | None:
    """Return list of running ROS nodes, or None if unavailable."""
    return _ros_exec("ros2 node list")


def ros_topics() -> list[str] | None:
    """Return list of active ROS topics, or None if unavailable."""
    return _ros_exec("ros2 topic list")
