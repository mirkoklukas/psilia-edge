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
    get_data_dir,
    read_config,
)
from psilia_edge.runtime.daemon import LOG_FILE, get_pid
from psilia_edge.runtime.docker import (
    container_status,
    is_docker_running,
    request_ros_status,
)


def live_status() -> dict:
    """Snapshot of time-sensitive status for the live view."""
    return {
        "runtime": {"base": _base_section(), "spatial": _spatial_section()},
        "heartbeat": _read_heartbeat(),
    }


def runtime_status(debug: bool = False) -> dict:
    from psilia_edge.runtime.core import is_runtime_host

    def _timed(name, fn):
        t = time.time()
        result = fn()
        if debug:
            print(f"  {name}: {time.time() - t:.3f}s")
        return result

    t0 = time.time()
    status: dict = {
        "runtime": {"base": _timed("base", _base_section)},
        "hotspot": _timed("hotspot", _hotspot_section),
        "sensors": _timed("sensors", _sensors_section),
    }

    if is_runtime_host():
        status["runtime"]["spatial"] = _timed(
            "spatial", lambda: _spatial_section(debug=debug)
        )
        status["storage"] = _timed("storage", _storage_section)

    if debug:
        print(f"  total: {time.time() - t0:.3f}s")

    return status


def _base_section() -> dict:
    # TODO: port is hardcoded here, should it be read from a config or something?
    port = 8080
    pid = get_pid()
    running = pid is not None
    section: dict = {"running": running}

    if not running:
        return section

    hostname = socket.gethostname().split(".")[0]
    try:
        # UDP trick: connect to Google's public DNS (8.8.8.8) — no packet is sent,
        # but the OS picks the outbound interface, so getsockname() returns our LAN IP.
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _s.connect(("8.8.8.8", 80))
        lan_ip = _s.getsockname()[0]
        _s.close()
    except OSError:
        lan_ip = None

    section |= {
        "uptime": _process_uptime(pid),
        "pid": pid,
        "url": f"http://{hostname}.local:{port}",
        "lan_ip": f"http://{lan_ip}:{port}" if lan_ip else None,
        "log": str(LOG_FILE),
    }
    return section


def _spatial_section(debug: bool = False) -> dict:
    def _timed(name, fn):
        t = time.time()
        result = fn()
        if debug:
            print(f"    spatial/{name}: {time.time() - t:.3f}s")
        return result

    docker_running = _timed("is_docker_running", is_docker_running)
    section: dict = {"docker": {"running": docker_running}}

    if not docker_running:
        return section

    status = _timed("container_status", container_status)
    container_running = status == "running"
    section["docker"]["container"] = {
        "name": CONTAINER_NAME,
        "running": container_running,
        "state": status,
    }

    if container_running:
        section["ros"] = _timed("ros_status", _read_ros_status)

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
    data_dir = get_data_dir()
    section: dict = {"data_dir": str(data_dir)}
    try:
        usage = shutil.disk_usage(data_dir)
        section["free_gb"] = round(usage.free / 1e9, 1)
        section["total_gb"] = round(usage.total / 1e9, 1)
    except OSError:
        pass
    try:
        section["num_mcap_files"] = len(list(data_dir.glob("*.mcap")))
    except OSError:
        section["num_mcap_files"] = 0
    return section


def _read_heartbeat() -> dict | None:
    """Read heartbeat.json written by core_node on every heartbeat tick."""
    try:
        return json.loads((RUN_DIR / "heartbeat.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _read_ros_status() -> dict | None:
    """Trigger core_node to write status.json via /psilia/status_request, then read it."""
    try:
        request_ros_status()
    except Exception:
        return None
    time.sleep(0.2)
    try:
        return json.loads((RUN_DIR / "status.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
