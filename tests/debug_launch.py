"""Minimal debug script: start container, run launch script, list ROS nodes."""

import time
import psilia.edge.ui as ui
from psilia.edge.ui import console
from psilia.edge.runtime.config import (
    DEFAULT_DOCKER_IMAGE,
    CONTAINER_NAME,
    get_ros_dir,
    get_log_dir,
    get_data_dir,
)
from psilia.edge.utils import run, run_streamed

LAUNCH_SCRIPT = "default.launch.py"
SETTLE_TIME = 5  # seconds to wait for nodes to come up after launch


def run_container(cmd="pwd && ls") -> None:
    cmd = (
        f"docker run -i --rm "
            f"-v {str(get_ros_dir())}:/psilia/ros "
            f"-v {str(get_log_dir())}:/psilia/log "
            f"--entrypoint /init.sh"
            f"--name {CONTAINER_NAME} "
                f"{DEFAULT_DOCKER_IMAGE} {cmd}"
    )
    return run_streamed(cmd)

def launch_ros(launch_script: str) -> dict:

    cmd = (
        f"docker run -i -d --rm "
            f"-v {str(get_ros_dir())}:/psilia/ros "
            f"-v {str(get_log_dir())}:/psilia/log "
            f"--name {CONTAINER_NAME} "
                f"{DEFAULT_DOCKER_IMAGE} {launch_script}"
    )
    # rc, out, err = run(cmd)
    # return rc, out, err
    return run_streamed(cmd)

def ros_node_list() -> dict:

    cmd = (
        f"docker exec -i {CONTAINER_NAME} bash -lc \"ros2 node list\""
        # f"docker exec -i {CONTAINER_NAME} /init.sh ros2 node list"
    )
    # rc, out, err = run(cmd)
    return run_streamed(cmd)




# ui.title(f"run container example")
# # rc = run_container("bash 'cat /etc/profile.d/psilia_setup.sh'")
# rc = run_container("cat /etc/profile.d/psilia_setup.sh")
# ui.info(f"{rc}")


ui.title(f"Starting container and launching ROS with {LAUNCH_SCRIPT}")
# with ui.console.status("Starting container and launching ROS..."):
rc = launch_ros(LAUNCH_SCRIPT)
ui.info(f"{rc}")
if rc != 0:
    ui.fail(f"Failed to launch ROS with {LAUNCH_SCRIPT}.")
    raise SystemExit(1)

ui.ok(f"Detached container is running in background")

with ui.status("Ok lets wait and let the the nodes come up hopefully"):
    time.sleep(SETTLE_TIME)

ui.title(f"Let's check the ROS nodes")
# with ui.console.status("Checking ROS nodes..."):
rc = ros_node_list()
if rc != 0:
    ui.fail(f"Failed to list ROS nodes.")
    rc = run_streamed(f"docker stop {CONTAINER_NAME}")
    raise SystemExit(1)
# ui.ok(f"{out.strip().splitlines()}")


ui.title(f"Docker stop")
# with ui.console.status("Stopping container..."):
rc = run_streamed(f"docker stop {CONTAINER_NAME}")
ui.item(f"rc={rc}")
