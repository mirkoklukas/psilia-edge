"""Runtime core — role detection and high-level runtime operations."""

from __future__ import annotations

import socket
import time

from psilia_edge.runtime.config import read_config


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Entry points
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# TODO: Should port be read from somewhere?
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


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Utils and Helper
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def is_runtime_host() -> bool:
    """Return True if a local runtime has been provisioned on this machine.

    Heuristic: runtime.home_path is set in ~/.psilia/psilia.yaml after `psilia runtime setup` has run.
    """
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


def start_base_layer(host: str = "0.0.0.0", port: int = 8080) -> dict:
    """Start the base layer daemon. Returns a result dict."""
    from psilia_edge.runtime.daemon import LOG_FILE, start_daemon

    pid = start_daemon(host=host, port=port)
    time.sleep(1.5)  # give uvicorn a moment to bind

    hostname = socket.gethostname().split(".")[0]
    # UDP trick: connect to Google's public DNS (8.8.8.8) — no packet is sent,
    # but the OS picks the outbound interface, so getsockname() returns our LAN IP.
    _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        _s.connect(("8.8.8.8", 80))
        lan_ip = _s.getsockname()[0]
    except OSError:
        lan_ip = None
    finally:
        _s.close()

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
    """Start the ROS Docker container and launch the ROS stack. Returns a result dict."""
    from psilia_edge.runtime.docker import (
        is_docker_daemon_running,
        launch_runtime_container,
    )
    from psilia_edge.runtime.config import get_launch_script

    if not is_docker_daemon_running():
        return {"status": "error", "error": "Docker daemon is not running."}

    launch_script = get_launch_script()
    rc, _, err = launch_runtime_container(launch_script)
    if rc != 0:
        return {"status": "error", "error": err}

    return {"status": "started", "launch": launch_script}


def stop_spatial_layer() -> dict:
    """Stop the ROS Docker container. Returns a result dict."""
    from psilia_edge.runtime.docker import stop_runtime_container

    rc, _, err = stop_runtime_container()
    if rc != 0:
        return {"status": "error", "error": err}
    return {"status": "stopped"}
