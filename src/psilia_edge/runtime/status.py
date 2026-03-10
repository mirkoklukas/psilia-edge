"""Runtime status aggregation."""

from __future__ import annotations

import shutil
import socket
import time

from psilia_edge.runtime.config import read_device_config


def live_status() -> dict:
    """Snapshot of time-sensitive status for the live view."""
    return {
        "runtime": {"base": _base_section(), "spatial": _spatial_section()},
        "ros": ros_latest_status(),
    }


def runtime_status() -> dict:
    return {
        "runtime": {"base": _base_section(), "spatial": _spatial_section()},
        "hotspot": _hotspot_section(),
        "sensors": _sensors_section(),
        "storage": _storage_section(),
    }


def _base_section() -> dict:
    from psilia_edge.runtime.daemon import LOG_FILE, get_pid

    section = {}
    pid = get_pid()
    running = pid is not None
    section |= {"running": running}
    if not running:
        return section

    hostname = socket.gethostname().split(".")[0]
    # TODO: port is hardcoded here, should it be read from a config or something?
    port = 8080
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


def _spatial_section() -> dict:
    from psilia_edge.runtime.docker import (
        container_status,
        is_docker_running,
        ros_nodes,
        ros_topics,
    )

    if not is_docker_running():
        return {"docker": "[red]offline[/red]"}

    status = container_status()
    color = (
        "green" if status == "running" else "yellow" if status == "exited" else "dim"
    )
    section: dict = {
        "docker": "[green]running[/green]",
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

    data_dir = get_data_dir()
    section: dict = {
        "data_dir": str(data_dir),
    }
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
