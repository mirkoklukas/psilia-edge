"""Runtime status aggregation.

IMPORTANT: All sections must reflect live state — process checks, device scans,
port probes, etc. Do not read from config files to infer what is running.
Config is user intent; status is ground truth.

All sections are opt-in via flags passed to `runtime_status(**flags)`.
Sections run in parallel. Available flags:
    uptime, spatial_running, base, spatial, server, docker, ros,
    spatial_requirements, storage, hotspot
"""

from __future__ import annotations

import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from psilia.edge.runtime.config import (
    CONTAINER_NAME,
    RUN_DIR,
    get_api_port,
    get_rosbridge_port,
)
from psilia.edge.runtime.daemon import LOG_FILE, get_pid


_SECTIONS: dict[str, Callable[[], dict]] = {}


def _register(name: str):
    def decorator(fn):
        _SECTIONS[name] = fn
        return fn

    return decorator


def runtime_status(**flags: bool) -> dict:
    """Collect runtime status sections in parallel.

    All sections are opt-in via flags:
        base, spatial, server, docker, ros, spatial_requirements, storage, hotspot
    """
    requested = {k: _SECTIONS[k] for k, v in flags.items() if v and k in _SECTIONS}
    if not requested:
        return {}
    with ThreadPoolExecutor() as ex:
        futures = {ex.submit(fn): key for key, fn in requested.items()}
        return {futures[f]: f.result() for f in as_completed(futures)}


# ── Sections (all registered) ─────────────────────────────────────────────────
@_register("uptime")
def _uptime_section() -> dict:
    pid = get_pid()
    running = pid is not None
    section: dict = {"running": running}
    if running:
        section["uptime"] = _compute_uptime(pid)
    return section


@_register("base")
def _base_section() -> dict:
    pid = get_pid()
    running = pid is not None
    section: dict = {"running": running}
    if running:
        section["uptime"] = _compute_uptime(pid)
        section["server"] = _SECTIONS["server"]()
        section["docker"] = _SECTIONS["docker"]()
    return section


@_register("spatial_running")
def _spatial_running_section() -> dict:
    from psilia.edge.runtime.core import is_spatial_layer_running

    return {"running": is_spatial_layer_running()}


@_register("spatial")
def _spatial_section() -> dict:
    from psilia.edge.runtime.core import check_spatial_layer_status

    status = check_spatial_layer_status()
    state = status["state"]
    running = state == "running"
    section: dict = {"running": running, "state": state, "detail": status["detail"]}
    if running:
        section["heartbeat"] = _heartbeat_section()
        section["ros"] = _SECTIONS["ros"]()

        # Show calibration and foxglove status from launch_params / config.
        from psilia.edge.utils import read_yaml
        from psilia.edge.runtime.config import read_runtime_config

        launch_params = read_yaml(RUN_DIR / "launch_params.yaml") or {}
        rectify_params = launch_params.get("rectify_node", {}).get(
            "ros__parameters", {}
        )
        cal_file = rectify_params.get("calibration_file")
        section["calibration"] = cal_file or "none"

        rt_config = read_runtime_config()
        foxglove_cfg = rt_config.get("ros", {}).get("foxglove", {})
        if foxglove_cfg.get("enabled", False):
            from psilia.edge.runtime.config import read_config

            port = read_config().get("runtime", {}).get("foxglove_port", 8765)
            hostname = socket.gethostname().split(".")[0]
            section["foxglove"] = {
                "ws": f"ws://{hostname}.local:{port}",
                "app": "https://app.foxglove.dev",
            }
    return section


@_register("server")
def _server_section() -> dict:
    pid = get_pid()
    port = get_api_port()
    hostname = socket.gethostname().split(".")[0]
    _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        _s.connect(("8.8.8.8", 80))
        lan_ip = _s.getsockname()[0]
    except OSError:
        lan_ip = None
    finally:
        _s.close()
    return {
        "pid": pid,
        "url": f"http://{hostname}.local:{port}",
        "lan_ip": f"http://{lan_ip}:{port}" if lan_ip else None,
        "log": str(LOG_FILE),
    }


@_register("docker")
def _docker_section() -> dict:
    from psilia.edge.runtime.docker import (
        check_container_status,
        is_docker_daemon_running,
    )

    return {
        "daemon": is_docker_daemon_running(),
        "container": {
            "name": CONTAINER_NAME,
            "state": check_container_status(),
        },
    }


@_register("ros")
def _ros_section() -> dict:
    from psilia.edge.runtime.docker import is_port_open, list_ros_nodes, list_ros_topics

    rosbridge_port = get_rosbridge_port()
    return {
        "nodes": list_ros_nodes(),
        "topics": list_ros_topics(),
        "rosbridge": {
            "port": rosbridge_port,
            "open": is_port_open(rosbridge_port),
        },
    }


@_register("recording")
def _recording_section() -> dict:
    from psilia.edge.runtime.docker import get_recording_process

    cmdline = get_recording_process()
    if cmdline is None:
        return {"recording": False}

    # Extract output path from cmdline, e.g.:
    # "ros2 bag record -o /psilia/data/my_session /topic1 /topic2"
    file = None
    parts = cmdline.split()
    for i, part in enumerate(parts):
        if part == "-o" and i + 1 < len(parts):
            file = parts[i + 1]
            break

    return {"recording": True, "file": file}


@_register("spatial_requirements")
def _spatial_requirements_section() -> dict:
    from psilia.edge.runtime.core import check_spatial_requirements

    ctx = check_spatial_requirements()
    return ctx.to_dict()


@_register("storage")
def _storage_section() -> dict:
    import shutil

    from psilia.edge.runtime.config import get_data_dir
    from psilia.edge.utils import run

    data_dir = get_data_dir()
    section: dict = {"data_dir": str(data_dir)}
    try:
        rc, stdout, _ = run(f"du -s {data_dir} | cut -f1")
        if rc == 0:
            data_bytes = int(stdout.strip())
            section["used_gb"] = round(data_bytes / 1e9, 3)
            section["used_bytes"] = data_bytes
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


@_register("hotspot")
def _hotspot_section() -> dict:
    from psilia.edge.network.hotspot import get_ap_ssid
    from psilia.edge.network.probe import list_interfaces
    from psilia.edge.runtime.config import read_config

    expected_ssid = read_config().get("network", {}).get("ap", {}).get("ssid")
    active_ssid = None
    for iface in list_interfaces():
        if iface.is_wifi:
            ssid = get_ap_ssid(iface.name)
            if ssid and ssid == expected_ssid:
                active_ssid = ssid
                break

    active = active_ssid is not None
    section: dict = {"running": active}
    if active:
        section["ssid"] = active_ssid
        if password := read_config().get("network", {}).get("ap", {}).get("password"):
            section["password"] = password
    return section


_HEARTBEAT_MAX_AGE = 5.0  # seconds — core_node publishes at 1Hz


def _heartbeat_section() -> dict:
    """Read heartbeat.json written by core_node at 1Hz."""
    import json

    path = RUN_DIR / "heartbeat.json"
    try:
        age = time.time() - path.stat().st_mtime
        result = {"age": f"{age:0.3f} s"}
        result["status"] = "ok" if age < _HEARTBEAT_MAX_AGE else "stale"
        return result
    except (OSError, json.JSONDecodeError):
        return {"status": "no-signal", "age": None}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _compute_uptime(pid: int) -> str | None:
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
