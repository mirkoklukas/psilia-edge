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
from psilia.edge.runtime.docker import (
    launch_runtime_container,
    docker_exec,
    list_ros_nodes,
)
from psilia.edge.utils import run, run_streamed

launch_script = "default.launch.py"
SETTLE_TIME = 5  # seconds to wait for nodes to come up after launch



ui.title(f"Lunching runtime docker container")
rc,out,err = launch_runtime_container(launch_script)
ui.info(f"{rc}")
if rc != 0:
    ui.fail(f"Failed to launch runtime docker: {err}")
    raise SystemExit(1)
ui.ok(f"Detached container is running in background")


with ui.status("Ok lets wait and let the the nodes come up hopefully"):
    time.sleep(SETTLE_TIME)


ui.title(f"Let's check the ROS nodes")
# with ui.console.status("Checking ROS nodes..."):
nodes = list_ros_nodes()
if nodes is None:
    ui.fail(f"Failed to list ROS nodes.")
    rc = run_streamed(f"docker stop {CONTAINER_NAME}")
    raise SystemExit(1)
ui.ok(f"ROS nodes:\n{nodes}")


ui.title(f"Docker stop")
# with ui.console.status("Stopping container..."):
rc = run_streamed(f"docker stop {CONTAINER_NAME}")
ui.item(f"rc={rc}")
