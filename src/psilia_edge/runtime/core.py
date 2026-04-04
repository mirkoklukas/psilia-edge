"""Runtime core — role detection and high-level runtime operations."""

from __future__ import annotations

import logging
import socket
import sys
import time

from psilia_edge.runtime.config import get_api_port, read_config

logger = logging.getLogger(__name__)


class SpatialRequirementsError(Exception):
    """Raised when spatial layer requirements are not met."""

    def __init__(self, checks: dict) -> None:
        self.checks = checks
        failed = [k for k, v in checks.items() if not v["ok"]]
        super().__init__(f"Spatial requirements not met: {', '.join(failed)}")


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Entry points
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def start_runtime(
    host: str = "0.0.0.0", port: int | None = None, force: bool = False
) -> dict:
    """Start base and spatial layer. Returns a combined result dict."""
    base = start_base_layer(host=host, port=port)
    spatial = start_spatial_layer(force=force)
    return {"base": base, "spatial": spatial}


def stop_runtime() -> dict:
    """Stop spatial layer then base layer. Returns a combined result dict."""
    spatial = stop_spatial_layer()
    base = stop_base_layer()
    return {"base": base, "spatial": spatial}


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Base layer
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def start_base_layer(host: str = "0.0.0.0", port: int | None = None) -> dict:
    """Start the FastAPI daemon and the runtime container. Returns a result dict."""
    from psilia_edge.runtime.daemon import LOG_FILE, start_daemon
    from psilia_edge.runtime.docker import (
        is_docker_daemon_running,
        start_runtime_container,
    )

    if port is None:
        port = get_api_port()
    pid = start_daemon(host=host, port=port)
    time.sleep(1.5)  # give uvicorn a moment to bind

    hostname = socket.gethostname().split(".")[0]
    _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        _s.connect(("8.8.8.8", 80))
        lan_ip = _s.getsockname()[0]
    except OSError:
        lan_ip = None
    finally:
        _s.close()

    result = {
        "status": "started",
        "pid": pid,
        "url": f"http://{hostname}.local:{port}",
        "lan_ip": f"http://{lan_ip}:{port}" if lan_ip else None,
        "log": str(LOG_FILE),
    }

    if not is_docker_daemon_running():
        result["container"] = "error: Docker daemon is not running"
        return result

    rc, _, err = start_runtime_container()
    if rc != 0:
        result["container"] = f"error: {err}"
    else:
        result["container"] = "started"

    return result


def stop_base_layer() -> dict:
    """Stop the runtime container then the FastAPI daemon. Returns a result dict."""
    from psilia_edge.runtime.daemon import stop_daemon
    from psilia_edge.runtime.docker import is_container_running, stop_runtime_container

    if is_container_running():
        rc, _, err = stop_runtime_container()
        container = "stopped" if rc == 0 else f"error: {err}"
    else:
        container = "not_running"

    stopped = stop_daemon()
    return {
        "status": "stopped" if stopped else "not_running",
        "container": container,
    }


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Spatial layer
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def check_spatial_requirements() -> dict:
    """Check that all requirements for the spatial layer are met (preflight checks).

    These checks are shown as "Preflight Checks" in the web UI (web/index.html)
    and used by `start_spatial_layer()` to gate launch when `force=False`.

    Returns a dict of check name → {ok, detail}.
    On non-Linux platforms, camera and hotspot checks are skipped.
    """
    from psilia_edge.runtime.docker import is_container_running

    checks: dict = {}

    # Container
    container_ok = is_container_running()
    checks["container"] = {
        "ok": container_ok,
        "detail": "running" if container_ok else "not running — start base layer first",
    }

    # Camera
    from psilia_edge.runtime.hotplug import pick_camera_device

    camera = pick_camera_device()
    checks["camera"] = {
        "ok": bool(camera),
        "detail": camera.get("device", "detected") if camera else "no camera detected",
    }

    # Calibration
    from psilia_edge.runtime.config import read_runtime_config
    from psilia_edge.runtime.sensor import build_sensor_id, get_calibration_file

    rt_config = read_runtime_config()
    camera_config = rt_config.get("camera", {})
    sensor_id = build_sensor_id(camera) if camera else None

    cal_path = get_calibration_file(
        camera_config.get("name"),
        sensor_id,
    )
    checks["calibration"] = {
        "ok": cal_path is not None,
        "detail": cal_path.name if cal_path else "no calibration found",
    }

    # Hotspot
    from psilia_edge.network.hotspot import get_ap_ssid
    from psilia_edge.network.probe import list_interfaces
    from psilia_edge.runtime.config import read_config

    expected_ssid = read_config().get("network", {}).get("ap", {}).get("ssid")
    active_ssid = None
    for iface in list_interfaces():
        if iface.is_wifi:
            ssid = get_ap_ssid(iface.name)
            if ssid and ssid == expected_ssid:
                active_ssid = ssid
                break
    checks["hotspot"] = {
        "ok": active_ssid is not None,
        "detail": active_ssid if active_ssid else "hotspot not active",
    }

    return checks


def start_spatial_layer(force: bool = False) -> dict:
    """Launch ros2 inside the running container. Returns a result dict."""
    from psilia_edge.runtime.docker import start_ros_launch
    from psilia_edge.runtime.config import get_launch_script, RUN_DIR
    from psilia_edge.utils import write_yaml

    if not force:
        checks = check_spatial_requirements()
        if not all(v["ok"] for v in checks.values()):
            raise SpatialRequirementsError(checks)

    # Detect camera and resolve calibration.
    from psilia_edge.runtime.config import read_runtime_config
    from psilia_edge.runtime.sensor import build_sensor_id, get_calibration_file

    camera = None
    if sys.platform == "linux":
        from psilia_edge.runtime.hotplug import pick_camera_device

        camera = pick_camera_device()

    # Resolve calibration file via sensor registry lookup.
    # Tries runtime.yaml camera.name first, then auto-detected camera UID.
    # TODO: Support explicit file path (runtime.yaml camera.calibration) as bypass.
    rt_config = read_runtime_config()
    camera_config = rt_config.get("camera", {})
    sensor_id = build_sensor_id(camera) if camera else None

    cal_path = get_calibration_file(camera_config.get("name"), sensor_id)
    calibration_container_path = (
        f"/psilia/calibrations/{cal_path.name}" if cal_path else None
    )

    if calibration_container_path:
        logger.info("Calibration resolved: %s", calibration_container_path)
    elif camera:
        logger.warning(
            "No calibration found for camera (UID: %s). "
            "Rectify/depth nodes will not launch.",
            sensor_id,
        )
    else:
        logger.info("No camera detected and no camera configured.")

    # Write launch_params.yaml for ROS nodes.
    launch_params = {}
    if camera:
        # Only pass launch-relevant params to camera_node (not identity fields).
        camera_params = {
            k: camera[k]
            for k in ("device", "pixel_format", "width", "height", "fps")
            if k in camera
        }
        launch_params["camera_node"] = {"ros__parameters": camera_params}

    if calibration_container_path:
        launch_params["rectify_node"] = {
            "ros__parameters": {"calibration_file": calibration_container_path}
        }
        launch_params["depth_node"] = {
            "ros__parameters": {"calibration_file": calibration_container_path}
        }

    if launch_params:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        write_yaml(RUN_DIR / "launch_params.yaml", launch_params)

    launch_script = get_launch_script()
    rc, _, err = start_ros_launch(launch_script)
    if rc != 0:
        return {"status": "error", "error": err}

    return {
        "status": "started",
        "launch": launch_script,
        "camera": camera,
        "calibration": calibration_container_path,
    }


def stop_spatial_layer() -> dict:
    """Stop ros2 launch inside the container. Returns a result dict."""
    from psilia_edge.runtime.docker import is_ros_launch_running, stop_ros_launch

    if not is_ros_launch_running():
        return {"status": "not_running"}

    rc, _, err = stop_ros_launch()
    if rc != 0:
        return {"status": "error", "error": err}
    return {"status": "stopped"}


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Layer state
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def is_base_layer_running() -> bool:
    from psilia_edge.runtime.daemon import is_running

    return is_running()


def is_spatial_layer_running() -> bool:
    from psilia_edge.runtime.docker import is_ros_launch_running

    return is_ros_launch_running()


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Role detection
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def is_runtime_host() -> bool:
    """Return True if a local runtime has been provisioned on this machine."""
    return bool(read_config().get("runtime", {}).get("home_path"))


def require_runtime_host(device_hint: str) -> None:
    """Exit with a clear message if not running on a runtime host (Jetson)."""
    import typer
    from psilia_edge.ui import error

    if not is_runtime_host():
        error(
            f"[red]No local runtime found. Run `psilia runtime setup` first.[/red]\n"
            f"To target a registered device: [bold]psilia {device_hint}[/bold]"
        )
        raise typer.Exit(1)
