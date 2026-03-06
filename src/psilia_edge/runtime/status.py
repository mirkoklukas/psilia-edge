"""Runtime status aggregation."""

from __future__ import annotations

import os
import shutil
import socket
import time
from pathlib import Path

import yaml


def _format_uptime(seconds: float) -> str:
    seconds = int(seconds)
    h, remainder = divmod(seconds, 3600)
    m, s = divmod(remainder, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _process_uptime(pid: int) -> str | None:
    try:
        ctime = os.stat(f"/proc/{pid}").st_mtime
        return _format_uptime(time.time() - ctime)
    except OSError:
        return None


def _read_runtime_config() -> dict:
    path = Path("/opt/psilia/runtime_config.yaml")
    if not path.exists():
        return {}
    try:
        return yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError:
        return {}


def _runtime_section() -> dict:
    from psilia_edge.runtime.daemon import LOG_FILE, get_pid, is_running

    pid = get_pid()
    running = pid is not None
    section: dict = {"status": "running" if running else "offline"}
    if running:
        section["uptime"] = _process_uptime(pid)
        section["url"] = f"http://{socket.gethostname().split('.')[0]}.local:8080"
        section["log"] = str(LOG_FILE)
    return section


def _hotspot_section() -> dict:
    from psilia_edge.network.hotspot import HOTSPOT_CON_NAME, hotspot_is_active

    active = hotspot_is_active(HOTSPOT_CON_NAME)
    cfg = _read_runtime_config().get("hotspot", {})
    section: dict = {"active": active}
    if active:
        if ssid := cfg.get("ssid"):
            section["ssid"] = ssid
        if password := cfg.get("password"):
            section["password"] = password
    return section


def _sensors_section() -> dict:
    cfg = _read_runtime_config().get("camera", {})
    camera_type = cfg.get("type")
    return {
        "camera": {
            "status": "connected" if camera_type else "not_detected",
            "model": camera_type,
        }
    }


def _storage_section() -> dict:
    cfg = _read_runtime_config().get("storage", {})
    mount = cfg.get("mount", "/ssd")
    data_path = cfg.get("data_path", "/ssd/psilia/data")
    recordings_path = Path(data_path) / "recordings"

    section: dict = {
        "mount": mount,
        "data_path": str(recordings_path),
    }
    try:
        usage = shutil.disk_usage(mount)
        section["free_gb"] = round(usage.free / 1e9, 1)
        section["total_gb"] = round(usage.total / 1e9, 1)
    except OSError:
        pass
    try:
        section["recordings"] = len(list(recordings_path.glob("*.mcap")))
    except OSError:
        section["recordings"] = 0
    return section


def _runtime_status() -> dict:
    return {
        "runtime": _runtime_section(),
        "hotspot": _hotspot_section(),
        "sensors": _sensors_section(),
        "storage": _storage_section(),
    }
