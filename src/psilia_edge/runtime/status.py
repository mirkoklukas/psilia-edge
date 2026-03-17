"""Runtime status aggregation."""

from __future__ import annotations

import json
import shutil
import socket
import time

from psilia_edge.network.hotspot import hotspot_is_broadcasting
from psilia_edge.runtime.config import (
    CONTAINER_NAME,
    RUN_DIR,
    get_api_port,
    get_data_dir,
    get_rosbridge_port,
    read_config,
)
from psilia_edge.runtime.daemon import LOG_FILE, get_pid
from psilia_edge.runtime.docker import (
    check_container_status,
    is_docker_daemon_running,
    is_port_open,
    list_ros_nodes,
    list_ros_topics,
)


# def live_status() -> dict:
#     """Snapshot of time-sensitive status for the live view."""
#     return {
#         "runtime": {"base": _base_section(), "spatial": _spatial_section()},
#         # "heartbeat": _read_heartbeat(),
#     }


def runtime_status() -> dict:
    from psilia_edge.runtime.core import is_runtime_host

    status: dict = {
        "runtime": {"base": _base_section()},
        "hotspot": _hotspot_section(),
        "sensors": _sensors_section(),
    }

    if is_runtime_host():
        status["runtime"]["spatial"] = _spatial_section()
        status["storage"] = _storage_section()

    status["health"] = _health_section()

    return status


def _base_section() -> dict:
    port = get_api_port()
    pid = get_pid()
    running = pid is not None
    section: dict = {"running": running}

    if not running:
        return section

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

    section |= {
        "uptime": _process_uptime(pid),
        "pid": pid,
        "url": f"http://{hostname}.local:{port}",
        "lan_ip": f"http://{lan_ip}:{port}" if lan_ip else None,
        "log": str(LOG_FILE),
    }
    return section


def _spatial_section() -> dict:
    status = check_container_status()
    container_running = status == "running"
    section: dict = {
        "container": {
            "name": CONTAINER_NAME,
            "running": container_running,
            "state": status,
        }
    }

    if container_running:
        section["ros"] = {
            "heartbeat": _heartbeat_section(),
            "nodes": list_ros_nodes(),
            "topics": list_ros_topics(),
            "rosbridge": {
                "port": get_rosbridge_port(),
                "open": is_port_open(get_rosbridge_port()),
            },
        }

    return section


def _process_uptime(pid: int) -> str | None:
    try:
        import psutil

        return _format_uptime(time.time() - psutil.Process(pid).create_time())
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def _format_uptime(seconds: float) -> str:
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


# NOTE: hotspot and camera config are read from psilia.yaml, which is written during
# `psilia runtime setup`. Hardware may change between boots (different USB dongle,
# camera unplugged), so these values may be stale. Live detection should be added
# where it matters (e.g. camera connected check, hotspot interface still present).
def _hotspot_section() -> dict:
    cfg = read_config().get("hotspot", {})
    ssid = cfg.get("ssid")
    con_name = f"{ssid}-Hotspot" if ssid else None

    if con_name is None:
        from psilia_edge.network.hotspot import find_active_hotspot
        from psilia_edge.network.probe import list_interfaces

        for iface in list_interfaces():
            if iface.is_wifi:
                con_name = find_active_hotspot(iface.name)
                if con_name:
                    break

    active = hotspot_is_broadcasting(con_name) if con_name else False

    section: dict = {"running": active}
    if ssid:
        section["ssid"] = ssid
    if active and (password := cfg.get("password")):
        section["password"] = password
    return section


def _sensors_section() -> dict:
    cfg = read_config().get("camera", {})
    camera_type = cfg.get("type")
    return {
        "camera": {
            "running": bool(camera_type),
            "model": camera_type or None,
        }
    }


def _storage_section() -> dict:
    from psilia_edge.utils import run

    data_dir = get_data_dir()
    section: dict = {"data_dir": str(data_dir)}
    try:
        # du -s . | cut -f1 returns the total size of the directory in bytes,
        # without counting subdirectories separately.
        rc, stdout, _ = run(f"du -s {data_dir} | cut -f1")
        if rc == 0:
            data_bytes = int(stdout.strip())
            used_gb = round(data_bytes / 1e9, 3)
            section["used_gb"] = used_gb
            section["used_bytes"] = data_bytes
        # disk_usage uses the path only to identify the partition and
        # returns partition-level stats, not the directory size
        partition = shutil.disk_usage(data_dir)
        section["free_gb"] = round(partition.free / 1e9, 3)
    except OSError:
        pass
    try:
        section["num_bag_files"] = len(
            list(data_dir.glob("**/*.mcap"))
            + list(data_dir.glob("**/*.db3"))
            + list(data_dir.glob("**/*.bag"))
        )
    except OSError:
        section["num_bag_files"] = 0
    return section


def _health_section() -> dict:
    return {"docker_daemon": is_docker_daemon_running()}


_HEARTBEAT_MAX_AGE = 5.0  # seconds — core_node publishes at 1Hz


def _heartbeat_section() -> dict:
    """Read heartbeat.json written by core_node at 1Hz.

    Returns a dict with status='ros_not_running' if the file is missing or stale.
    """
    path = RUN_DIR / "heartbeat.json"
    result = {}
    try:
        age = time.time() - path.stat().st_mtime
        result["age"] = f"{age:0.3f} s"
        if age < _HEARTBEAT_MAX_AGE:
            result["status"] = "ok"
        else:
            result["status"] = "stale"
        return result
    except (OSError, json.JSONDecodeError):
        return {"status": "no-signal", "age": None}
