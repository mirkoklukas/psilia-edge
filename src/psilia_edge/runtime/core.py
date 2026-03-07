"""Runtime core — role detection and high-level runtime operations."""

from __future__ import annotations

import socket
import time
from pathlib import Path

RUNTIME_CONFIG_PATH = Path("/opt/psilia/runtime_config.yaml")


def is_runtime_host() -> bool:
    """Return True if this machine is a runtime host (Jetson).

    Heuristic: runtime_config.yaml only exists after `psilia setup` has run.
    """
    return RUNTIME_CONFIG_PATH.exists()


def require_runtime_host(device_hint: str) -> None:
    """Exit with a clear message if not running on a runtime host (Jetson)."""
    import typer
    from psilia_edge.ui import console

    if not is_runtime_host():
        console.print(
            f"[red]This command only runs on a Jetson.[/red]\n"
            f"  To target a registered device: [bold]psilia {device_hint}[/bold]"
        )
        raise typer.Exit(1)


def start_base_layer(host: str = "0.0.0.0", port: int = 8080) -> dict:
    """Start the base layer daemon. Returns a result dict."""
    from psilia_edge.runtime.daemon import LOG_FILE, start_daemon

    pid = start_daemon(host=host, port=port)
    time.sleep(1.5)  # give uvicorn a moment to bind

    hostname = socket.gethostname().split(".")[0]
    try:
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _s.connect(("8.8.8.8", 80))
        lan_ip = _s.getsockname()[0]
        _s.close()
    except OSError:
        lan_ip = None

    return {
        "status": "started",
        "pid": pid,
        "url": f"http://{hostname}.local:{port}",
        "lan_ip": f"http://{lan_ip}:{port}" if lan_ip else None,
        "log": str(LOG_FILE),
    }


def stop_base_layer() -> dict:
    """Stop the base layer daemon. Returns a result dict."""
    from psilia_edge.runtime.daemon import stop_daemon

    stopped = stop_daemon()
    return {"status": "stopped" if stopped else "not_running"}


def start_spatial_layer() -> dict:
    """Start the ROS Docker container. Returns a result dict."""
    from psilia_edge.runtime.docker import is_docker_running, start_container
    from psilia_edge.runtime.status import _read_runtime_config

    if not is_docker_running():
        return {"status": "error", "error": "Docker daemon is not running."}

    cfg = _read_runtime_config()
    image = cfg.get("runtime", {}).get("image", "psilia/runtime:latest")
    ros_workspace = cfg.get("runtime", {}).get("ros_workspace", "/ssd/psilia/ros")

    return start_container(image=image, ros_workspace=ros_workspace)


def stop_spatial_layer() -> dict:
    """Stop the ROS Docker container. Returns a result dict."""
    from psilia_edge.runtime.docker import stop_container

    return stop_container()


def start_runtime(host: str = "0.0.0.0", port: int = 8080) -> dict:
    """Start base layer then spatial layer. Returns a combined result dict."""
    base = start_base_layer(host=host, port=port)
    if base.get("status") == "error":
        return {"base": base, "spatial": {"status": "skipped"}}
    spatial = start_spatial_layer()
    return {"base": base, "spatial": spatial}


def stop_runtime() -> dict:
    """Stop spatial layer then base layer. Returns a combined result dict."""
    spatial = stop_spatial_layer()
    base = stop_base_layer()
    return {"base": base, "spatial": spatial}
