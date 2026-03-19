"""Runtime core — role detection and high-level runtime operations."""

from __future__ import annotations

import socket
import sys
import time

from psilia_edge.runtime.config import get_api_port, read_config


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
    from psilia_edge.runtime.docker import stop_runtime_container

    rc, _, err = stop_runtime_container()
    container = "stopped" if rc == 0 else f"error: {err}"

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
    """Check that all requirements for the spatial layer are met.

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

    if sys.platform == "linux":
        # Camera
        from psilia_edge.runtime.hotplug import pick_camera_device

        camera = pick_camera_device()
        checks["camera"] = {
            "ok": bool(camera),
            "detail": camera.get("device", "detected")
            if camera
            else "no camera detected",
        }

        # Hotspot
        from psilia_edge.network.hotspot import hotspot_is_broadcasting
        from psilia_edge.runtime.config import read_config

        cfg = read_config().get("hotspot", {})
        ssid = cfg.get("ssid")
        con_name = f"{ssid}-Hotspot" if ssid else None
        hotspot_ok = hotspot_is_broadcasting(con_name) if con_name else False
        checks["hotspot"] = {
            "ok": hotspot_ok,
            "detail": ssid if hotspot_ok else "hotspot not active",
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

    # Detect camera and write launch_params.yaml for ROS nodes.
    camera = None
    if sys.platform == "linux":
        from psilia_edge.runtime.hotplug import pick_camera_device

        camera = pick_camera_device()

    if camera:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        write_yaml(
            RUN_DIR / "launch_params.yaml", {"camera_node": {"ros__parameters": camera}}
        )

    launch_script = get_launch_script()
    rc, _, err = start_ros_launch(launch_script)
    if rc != 0:
        return {"status": "error", "error": err}

    return {"status": "started", "launch": launch_script, "camera": camera}


def stop_spatial_layer() -> dict:
    """Stop ros2 launch inside the container. Returns a result dict."""
    from psilia_edge.runtime.docker import stop_ros_launch

    rc, _, err = stop_ros_launch()
    if rc != 0:
        return {"status": "error", "error": err}
    return {"status": "stopped"}


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
