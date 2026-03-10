"""Runtime status aggregation."""

from __future__ import annotations

import os
import shutil
import socket
import time

from psilia_edge.runtime.config import read_device_config


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


def _runtime_section() -> dict:
    from psilia_edge.runtime.daemon import LOG_FILE, get_pid

    pid = get_pid()
    running = pid is not None
    section: dict = {
        "status": "[green]running[/green]" if running else "[red]offline[/red]"
    }
    if running:
        section["uptime"] = _process_uptime(pid)
        section["url"] = f"http://{socket.gethostname().split('.')[0]}.local:8080"
        section["log"] = str(LOG_FILE)
    return section


def _hotspot_section() -> dict:
    from psilia_edge.network.hotspot import hotspot_is_broadcasting

    cfg = read_device_config().get("hotspot", {})
    ssid = cfg.get("ssid")
    con_name = f"{ssid}-Hotspot" if ssid else None
    active = hotspot_is_broadcasting(con_name) if con_name else False

    section: dict = {"active": "[green]yes[/green]" if active else "[dim]no[/dim]"}
    if active:
        if ssid:
            section["ssid"] = ssid
        if password := cfg.get("password"):
            section["password"] = password
    return section


def _sensors_section() -> dict:
    cfg = read_device_config().get("camera", {})
    camera_type = cfg.get("type")
    return {
        "camera": {
            "status": "[green]connected[/green]"
            if camera_type
            else "[dim]not detected[/dim]",
            "model": camera_type or "[dim]—[/dim]",
        }
    }


def _storage_section() -> dict:
    from psilia_edge.runtime.config import get_data_dir

    cfg = read_device_config()
    mount = cfg.get("runtime", {}).get("mount", "/ssd")
    recordings_path = get_data_dir() / "recordings"

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


def _spatial_section() -> dict:
    from psilia_edge.runtime.docker import (
        container_status,
        is_docker_running,
        ros_nodes,
        ros_topics,
    )

    if not is_docker_running():
        return {"daemon": "[red]offline[/red]"}

    status = container_status()
    color = (
        "green" if status == "running" else "yellow" if status == "exited" else "dim"
    )
    section: dict = {
        "daemon": "[green]running[/green]",
        "container": f"[{color}]{status}[/{color}]",
    }

    if status == "running":
        nodes = ros_nodes()
        topics = ros_topics()
        if nodes is not None:
            section["nodes"] = nodes
        if topics is not None:
            section["topics"] = topics

    return section


def ros_latest_status() -> dict | None:
    """Return the latest /psilia/status ROS message as a dict, or None if unavailable.

    Blocks until a message arrives (up to ~1s for a 1 Hz topic).
    """
    import json
    from psilia_edge.runtime.docker import _ros_exec

    lines = _ros_exec("ros2 topic echo /psilia/status --once 2>/dev/null")
    if not lines:
        return None
    # ros2 topic echo outputs:  data: '{"status": "ok", ...}'
    for line in lines:
        if line.startswith("data:"):
            raw = line[len("data:") :].strip().strip("'\"")
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None
    return None


def live_status() -> dict:
    """Snapshot of time-sensitive status for the live view."""
    return {
        "runtime": _runtime_section(),
        "spatial": _spatial_section(),
        "ros": ros_latest_status(),
    }


def runtime_status() -> dict:
    return {
        "runtime": _runtime_section(),
        "spatial": _spatial_section(),
        "hotspot": _hotspot_section(),
        "sensors": _sensors_section(),
        "storage": _storage_section(),
    }
