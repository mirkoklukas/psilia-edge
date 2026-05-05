"""Runtime core — role detection and high-level runtime operations."""

from __future__ import annotations

import logging
import socket
import time

from psilia_edge.runtime.config import RUN_DIR, get_api_port, read_config
from psilia_edge.runtime.requirements import (
    RequirementResult,
    RequirementSpec,
    ResolverResult,
    run_requirements,
)

logger = logging.getLogger(__name__)


class SpatialRequirementsError(Exception):
    """Raised when spatial layer requirements are not met."""

    def __init__(self, result) -> None:
        self.result = result
        super().__init__("Spatial requirements not met")


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Spatial resolvers
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def resolve_container() -> ResolverResult:
    from psilia_edge.runtime.docker import is_container_running

    ok = is_container_running()
    return ResolverResult(
        ok=ok,
        detail="running" if ok else "not running — start base layer first",
    )


def resolve_camera() -> ResolverResult:
    """Pick camera and resolution.

    1. If camera.name is set in runtime.yaml, match it against detected groups
       (by product name, label, or UID). Otherwise take the first group.
    2. If camera.resolution is set ([w, h] per-eye), use it if available.
       Otherwise pick the highest available resolution.
    """
    from psilia_edge.runtime.config import read_runtime_config
    from psilia_edge.runtime.hotplug import scan_cameras
    from psilia_edge.runtime.sensor import build_sensor_id, find_sensor

    import sys

    if sys.platform != "linux":
        return ResolverResult(ok=False, detail="camera detection requires Linux")

    groups = scan_cameras()
    if not groups:
        return ResolverResult(ok=False, detail="no camera detected")

    rt_config = read_runtime_config(missing_ok=True)
    camera_config = rt_config.get("camera", {})
    camera_name = camera_config.get("name")

    # -- pick camera group --
    group = None
    if camera_name:
        sensor = find_sensor(camera_name)
        match_uid = sensor[0] if sensor else None
        for g in groups:
            cam = g[0]
            uid = build_sensor_id(cam)
            product = cam.get("product", cam.get("name", ""))
            if uid == match_uid or product == camera_name:
                group = g
                break
        if group is None:
            return ResolverResult(
                ok=False,
                detail=f"camera '{camera_name}' not found among detected devices",
            )
    else:
        group = groups[0]

    # -- pick device node with formats --
    camera = None
    for cam in group:
        formats = cam.get("formats", {})
        if not formats:
            continue

        if "MJPG" in formats:
            fmt = "MJPG"
        elif "YUYV" in formats:
            fmt = "YUYV"
        else:
            fmt = next(iter(formats))

        sizes = formats[fmt].get("sizes", [])
        if not sizes:
            continue

        camera = {
            "device": cam["device"],
            "pixel_format": fmt,
            "available_sizes": sizes,
            "fps": 30,
        }
        for field in (
            "name",
            "type",
            "vendor_id",
            "product_id",
            "manufacturer",
            "product",
            "serial",
            "bus_id",
        ):
            if field in cam:
                camera[field] = cam[field]
        break

    if camera is None:
        return ResolverResult(ok=False, detail="no usable device node in camera group")

    # -- pick resolution --
    requested_res = camera_config.get("resolution")
    sizes = camera.get("available_sizes", [])

    if requested_res:
        eye_w, eye_h = requested_res[0], requested_res[1]
        stereo_w, stereo_h = eye_w * 2, eye_h
        match = next(
            (s for s in sizes if s["width"] == stereo_w and s["height"] == stereo_h),
            None,
        )
        if match:
            size = match
        else:
            logger.warning(
                "Requested resolution %dx%d not available, using highest",
                eye_w,
                eye_h,
            )
            size = max(sizes, key=lambda s: s["width"] * s["height"])
    else:
        size = max(sizes, key=lambda s: s["width"] * s["height"])

    camera["width"] = size["width"]
    camera["height"] = size["height"]

    sensor_id = build_sensor_id(camera)
    return ResolverResult(
        ok=True,
        detail=f"{camera.get('device')} 2x{size['width'] // 2}x{size['height']}",
        data={"info": camera, "sensor_id": sensor_id},
    )


def resolve_calibration(camera) -> ResolverResult:
    """Find calibration for the resolved camera and resolution.

    1. If camera.calibration is set in runtime.yaml, use that path directly.
    2. Look up available calibrations for the sensor. Try exact resolution match first,
       then rescalable match, then give up.
    """
    from psilia_edge.runtime.config import read_runtime_config
    from psilia_edge.runtime.sensor import (
        find_sensor,
        get_available_calibrations,
        get_calibration_resolution,
        is_calibration_compatible,
    )

    rt_config = read_runtime_config(missing_ok=True)
    camera_config = rt_config.get("camera", {})

    # -- explicit override --
    cal_override = camera_config.get("calibration")
    if cal_override:
        from pathlib import Path

        cal_path = Path(cal_override).expanduser()
        if not cal_path.is_absolute():
            from psilia_edge.runtime.config import CALIBRATIONS_DIR

            cal_path = CALIBRATIONS_DIR / cal_path
        if not cal_path.exists():
            return ResolverResult(ok=False, detail=f"calibration not found: {cal_path}")
        container_path = f"/psilia/calibrations/{cal_path.name}"
        return ResolverResult(
            ok=True,
            detail=f"{cal_path.name} (override)",
            data={"host_path": cal_path, "container_path": container_path},
        )

    # -- look up sensor --
    camera_name = camera_config.get("name")
    sensor_id = camera.data.get("sensor_id") if camera.ok else None
    sensor = find_sensor(camera_name) if camera_name else None
    if sensor is None and sensor_id:
        sensor = find_sensor(sensor_id)

    if sensor is None:
        return ResolverResult(ok=False, detail="no sensor registered for this camera")

    _, entry = sensor
    label = entry.get("label", "")
    uid = entry.get("uid")

    cal_files = get_available_calibrations(label, uid)
    if not cal_files:
        return ResolverResult(ok=False, detail="no calibration files found")

    # -- match against capture resolution --
    camera_info = camera.data.get("info", {})
    frame_w = camera_info.get("width", 0)
    frame_h = camera_info.get("height", 0)
    eye_w = frame_w // 2

    # Exact match.
    for f in cal_files:
        res = get_calibration_resolution(f)
        if res and res[0] == eye_w and res[1] == frame_h:
            container_path = f"/psilia/calibrations/{f.name}"
            return ResolverResult(
                ok=True,
                detail=f"{f.name} (exact)",
                data={"host_path": f, "container_path": container_path},
            )

    # Rescalable match.
    for f in cal_files:
        res = get_calibration_resolution(f)
        if res and is_calibration_compatible(res[0], res[1], frame_w, frame_h):
            container_path = f"/psilia/calibrations/{f.name}"
            return ResolverResult(
                ok=True,
                detail=f"{f.name} (rescaled)",
                data={"host_path": f, "container_path": container_path},
            )

    # No match — use highest resolution calibration, let camera node rescale.
    best = cal_files[0]
    container_path = f"/psilia/calibrations/{best.name}"
    return ResolverResult(
        ok=True,
        detail=f"{best.name} (no resolution match, will rescale)",
        data={"host_path": best, "container_path": container_path},
    )


def resolve_cuda() -> ResolverResult:
    from psilia_edge.runtime.docker import has_cuda

    ok = has_cuda()
    return ResolverResult(
        ok=ok,
        detail="available" if ok else "not available",
    )


def resolve_hotspot() -> ResolverResult:
    from psilia_edge.network.hotspot import get_ap_ssid
    from psilia_edge.network.probe import list_interfaces

    expected_ssid = read_config().get("network", {}).get("ap", {}).get("ssid")
    active_ssid = None
    for iface in list_interfaces():
        if iface.is_wifi:
            ssid = get_ap_ssid(iface.name)
            if ssid and ssid == expected_ssid:
                active_ssid = ssid
                break

    return ResolverResult(
        ok=active_ssid is not None,
        detail=active_ssid if active_ssid else "hotspot not active",
    )


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Spatial requirement spec
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
SPATIAL_REQUIREMENTS = [
    RequirementSpec(
        "container",
        resolve_container,
        (),
        [RequirementSpec("cuda", resolve_cuda)],
    ),
    RequirementSpec(
        "camera",
        resolve_camera,
        (),
        [
            RequirementSpec(
                "calibration",
                resolve_calibration,
                ("camera",),
            ),
        ],
    ),
    RequirementSpec("hotspot", resolve_hotspot),
]


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Entry points
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def start_runtime(
    host: str = "0.0.0.0", port: int | None = None, force: bool = False
) -> dict:
    """Start base and spatial layer. Returns a summary dict for display."""
    base = start_base_layer(host=host, port=port)
    spatial = start_spatial_layer(force=force)
    return {"base": base, "spatial": spatial}


def stop_runtime() -> dict:
    """Stop spatial layer then base layer. Returns a summary dict for display."""
    spatial = stop_spatial_layer()
    base = stop_base_layer()
    return {"base": base, "spatial": spatial}


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Base layer
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


def _clear_run_state():
    """Remove ephemeral status files from a previous session and seed hz.json."""
    import json

    from psilia_edge.runtime.config import read_runtime_config

    for name in ("heartbeat.json", "status.json", "launch_id"):
        (RUN_DIR / name).unlink(missing_ok=True)

    (RUN_DIR / "hz.json").unlink(missing_ok=True)

    rt_config = read_runtime_config(missing_ok=True)
    hz_topics_raw = (
        rt_config.get("ros", {})
        .get("nodes", {})
        .get("diagnostics_node", {})
        .get("parameters", {})
        .get("hz_topics", [])
    )
    if hz_topics_raw:
        topics = [e.split(",", 1)[0].strip() for e in hz_topics_raw if e and "," in e]
        empty_hz = {t: {"hz": 0.0, "min_dt": 0.0, "max_dt": 0.0} for t in topics}
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        (RUN_DIR / "hz.json").write_text(json.dumps(empty_hz))


def start_base_layer(host: str = "0.0.0.0", port: int | None = None) -> dict:
    """Start the FastAPI daemon and the runtime container. Returns a summary dict for display."""
    from psilia_edge.runtime.daemon import LOG_FILE, start_daemon
    from psilia_edge.runtime.docker import (
        is_docker_daemon_running,
        start_runtime_container,
    )

    _clear_run_state()

    if port is None:
        port = get_api_port()

    logger.info("Starting web server…")
    pid = start_daemon(host=host, port=port)
    time.sleep(1.5)  # give uvicorn a moment to bind
    logger.info("Web server started (PID %s)", pid)

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
        logger.info("Docker daemon is not running — skipping container")
        result["container"] = "error: Docker daemon is not running"
        return result

    logger.info("Starting Docker container…")
    rc, _, err = start_runtime_container()
    if rc != 0:
        logger.info("Container failed: %s", err)
        result["container"] = f"error: {err}"
    else:
        logger.info("Container started")
        result["container"] = "started"

    return result


def stop_base_layer() -> dict:
    """Stop the runtime container then the FastAPI daemon. Returns a summary dict for display."""
    from psilia_edge.runtime.daemon import stop_daemon
    from psilia_edge.runtime.docker import is_container_running, stop_runtime_container

    if is_container_running():
        logger.info("Stopping Docker container…")
        rc, _, err = stop_runtime_container()
        container = "stopped" if rc == 0 else f"error: {err}"
        logger.info("Container %s", container)
    else:
        logger.info("Container not running — skipping")
        container = "not_running"

    logger.info("Stopping web server…")
    stopped = stop_daemon()
    logger.info("Web server %s", "stopped" if stopped else "was not running")
    return {
        "status": "stopped" if stopped else "not_running",
        "container": container,
    }


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Spatial layer
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def check_spatial_requirements():
    """Check that all requirements for the spatial layer are met (preflight checks).

    These checks are shown as "Preflight Checks" in the web UI (web/index.html)
    and used by `start_spatial_layer()` to gate launch when `force=False`.

    Returns a RequirementResult root node.

    TODO: This takes ~1-2s due to subprocess calls (docker inspect, CUDA check,
    USB enumeration). Consider caching results with a short TTL, running checks
    in parallel at the top level, or replacing subprocess calls with lighter
    probes (e.g. Docker SDK, cached container state).
    """
    return run_requirements(SPATIAL_REQUIREMENTS)


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Spatial node table — declarative binding of nodes to requirements.
#
#   For each conditional spatial node:
#     requires: list of ctx tree paths that must all be ``ok`` for the
#               node to be added.
#     params:   ros_param_name -> ctx path. Each value is pulled from
#               ctx; if the path traverses a non-ok node (e.g. optional
#               calibration when calibration failed), the param is
#               silently skipped.
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
SPATIAL_NODES: dict[str, dict] = {
    "camera_node": {
        "requires": ["camera"],
        "params": {
            "device": "camera:info:device",
            "pixel_format": "camera:info:pixel_format",
            "width": "camera:info:width",
            "height": "camera:info:height",
            "fps": "camera:info:fps",
            # Optional — included only when calibration also resolves.
            "calibration_file": "camera.calibration:container_path",
        },
    },
    "preview_node": {
        "requires": ["camera"],
        "params": {},
    },
    "rectify_node": {
        "requires": ["camera.calibration"],
        "params": {"calibration_file": "camera.calibration:container_path"},
    },
    "depth_node": {
        "requires": ["camera.calibration"],
        "params": {"calibration_file": "camera.calibration:container_path"},
    },
    "depth_preview_node": {
        "requires": ["camera.calibration"],
        "params": {},
    },
    "pointcloud_preview_node": {
        "requires": ["camera.calibration"],
        "params": {},
    },
    "depth_cuda_node": {
        "requires": ["camera.calibration", "container.cuda"],
        "params": {"calibration_file": "camera.calibration:container_path"},
    },
    "cuda_stereo_bm_node": {
        "requires": ["camera.calibration", "container.cuda"],
        "params": {"calibration_file": "camera.calibration:container_path"},
    },
}


def _resolve_node_params(ctx: RequirementResult, sources: dict[str, str]) -> dict:
    """Pull each value from ctx; silently skip params whose source path failed.

    KeyError covers two cases:
      - a node along the tree path was skipped (failed requirement) and has empty data,
      - the named data key doesn't exist (typo in the table).
    Both result in the param being omitted; a typo'd key surfaces as the
    consuming node's own missing-param error at runtime.
    """
    out = {}
    for ros_param, path in sources.items():
        try:
            out[ros_param] = ctx[path]
        except KeyError:
            continue
    return out


def _build_launch_params(ctx: RequirementResult) -> dict:
    """Build node list and per-node parameters from resolved requirements.

    ``ctx`` is the root ``RequirementResult`` from
    ``check_spatial_requirements()`` (i.e. ``run_requirements(SPATIAL_REQUIREMENTS)``).
    Each child node has ``.ok``, ``.detail``, and ``.data``; index with
    ``ctx["x"]`` for a node and ``ctx["x:key"]`` for a data field. The shape
    expected here, per ``SPATIAL_REQUIREMENTS``:

        ctx["container"]            .ok=is_container_running()
        ctx["container.cuda"]       .ok=has_cuda()
        ctx["camera"]               .ok=camera detected & usable
                                    .data["info"]: {device, pixel_format,
                                        width, height, fps, name?, product?,
                                        serial?, vendor_id?, product_id?, ...}
                                    .data["sensor_id"]: stable id string
        ctx["camera.calibration"]   .ok=calibration file resolved
                                    .data["host_path"]: Path on host
                                    .data["container_path"]: "/psilia/calibrations/<name>"
        ctx["hotspot"]              (not used here)

    Children of a failed parent are auto-skipped (``ok=False, detail="skipped"``),
    so guarding on the parent's ``.ok`` before reading a child is sufficient.

    Returns a dict ready to be written to launch_params.yaml:
        nodes: [list of conditional node names to launch]
        <node_name>: {ros__parameters: {...}}

    Walks ``SPATIAL_NODES`` to derive the eligible node list, then applies
    user overrides from runtime.yaml ``ros.nodes``. Each user entry can be
    a bool (enable/disable) or a dict with ``enable`` and ``parameters``
    keys. ``enable: true`` adds a node from the table if its requirements
    are met; ``enable: false`` removes a node. User parameters are merged
    on top of requirement-derived ones.
    """
    from psilia_edge.runtime.config import read_runtime_config

    nodes: list[str] = []
    params: dict[str, dict] = {}

    def _try_add(name: str) -> bool:
        spec = SPATIAL_NODES[name]
        if not all(ctx[req].ok for req in spec["requires"]):
            return False
        if name not in nodes:
            nodes.append(name)
        node_params = _resolve_node_params(ctx, spec["params"])
        if node_params:
            existing = params.get(name, {}).get("ros__parameters", {})
            params[name] = {"ros__parameters": {**existing, **node_params}}
        return True

    for name in SPATIAL_NODES:
        _try_add(name)

    # Diagnostic logs preserved from the previous implementation.
    if not ctx["camera"].ok:
        logger.info("No camera detected and no camera configured.")
    elif not ctx["camera.calibration"].ok:
        logger.warning(
            "No calibration found for camera (UID: %s). "
            "Rectify/depth nodes will not launch.",
            ctx["camera"].data.get("sensor_id"),
        )

    # Apply user overrides from runtime.yaml ros.nodes.
    # Each entry can be:
    #   bool              — enable/disable
    #   dict              — {enable: bool, parameters: {key: val}}
    rt_config = read_runtime_config(missing_ok=True)
    user_nodes = rt_config.get("ros", {}).get("nodes", {})

    for name, entry in user_nodes.items():
        if isinstance(entry, bool):
            enabled = entry
            user_params = {}
        elif isinstance(entry, dict):
            enabled = entry.get("enable", True)
            user_params = entry.get("parameters", {})
        else:
            continue

        if not enabled:
            if name in nodes:
                logger.info("Disabled node: %s", name)
                nodes.remove(name)
        elif name not in nodes and name in SPATIAL_NODES:
            if _try_add(name):
                logger.info("Enabled node from user override: %s", name)
            else:
                failed = [r for r in SPATIAL_NODES[name]["requires"] if not ctx[r].ok]
                logger.warning(
                    "User enabled %s but requirements not met: %s", name, failed
                )

        if user_params:
            existing = params.get(name, {}).get("ros__parameters", {})
            params[name] = {"ros__parameters": {**existing, **user_params}}

    return {"nodes": nodes, **params}


def start_spatial_layer(force: bool = False) -> dict:
    """Launch ros2 inside the running container.

    Returns a summary dict for display (CLI tree, API JSON). No caller
    depends on specific keys — treat as informational.

    Writes ``RUN_DIR/launch_id`` with format ``{id}:{timestamp}``.
    ``core_node`` includes the same ``launch_id`` in every ``heartbeat.json``
    write, enabling cheap file-only liveness detection from the host:

        stopped     — launch_id missing or ends with ``:stopped``
        running     — launch_id matches heartbeat, heartbeat mtime fresh
        stale       — heartbeat missing or stale, ros2 launch still alive
        crashed     — heartbeat missing or stale, ros2 launch dead

    Only the last two states require a ``docker exec`` call (``pgrep``).
    ``stop_spatial_layer()`` appends ``:stopped`` to the file.
    """
    from psilia_edge.runtime.config import RUN_DIR, get_launch_script
    from psilia_edge.runtime.docker import start_ros_launch
    from psilia_edge.utils import write_yaml

    logger.info("Checking spatial requirements…")
    ctx = check_spatial_requirements()

    if not ctx["container"].ok:
        raise SpatialRequirementsError(ctx)

    if not force and not ctx.ok:
        raise SpatialRequirementsError(ctx)

    import time
    import uuid

    launch_id = uuid.uuid4().hex[:12]
    launch_time = time.time()

    logger.info("Building launch parameters…")
    launch_params = _build_launch_params(ctx)
    launch_params["launch_id"] = launch_id

    RUN_DIR.mkdir(parents=True, exist_ok=True)
    (RUN_DIR / "launch_id").write_text(f"{launch_id}:{launch_time}")
    write_yaml(RUN_DIR / "launch_params.yaml", launch_params)

    launch_script = get_launch_script()
    logger.info("Launching ROS nodes…")
    rc, _, err = start_ros_launch(launch_script)
    if rc != 0:
        logger.info("ROS launch failed: %s", err)
        return {"status": "error", "error": err}

    logger.info("Spatial layer started (%d nodes)", len(launch_params["nodes"]))

    camera = ctx["camera"]
    calibration = ctx["camera.calibration"] if camera.ok else None
    return {
        "status": "started",
        "launch": launch_script,
        "nodes": launch_params["nodes"],
        "camera": camera.data.get("info") if camera.ok else None,
        "calibration": calibration.data.get("container_path")
        if calibration and calibration.ok
        else None,
    }


def stop_spatial_layer() -> dict:
    """Stop ros2 launch inside the container. Returns a summary dict for display."""
    from psilia_edge.runtime.docker import is_ros_launch_running, stop_ros_launch

    if not is_ros_launch_running():
        logger.info("ROS nodes not running — skipping")
        return {"status": "not_running"}

    logger.info("Stopping ROS nodes…")
    rc, _, err = stop_ros_launch()

    from psilia_edge.runtime.config import RUN_DIR

    launch_id_file = RUN_DIR / "launch_id"
    if launch_id_file.exists():
        launch_id_file.write_text(launch_id_file.read_text().strip() + ":stopped")

    if rc != 0:
        logger.info("Failed to stop ROS nodes: %s", err)
        return {"status": "error", "error": err}
    logger.info("ROS nodes stopped")
    return {"status": "stopped"}


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Layer state
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def is_base_layer_running() -> bool:
    from psilia_edge.runtime.daemon import is_running

    return is_running()


def check_spatial_layer_status() -> dict:
    """Determine spatial layer state from launch_id + heartbeat files.

    See ``start_spatial_layer()`` docstring for the ``launch_id`` protocol.

    Returns ``{"state": ..., "detail": ...}`` where state is one of:
        stopped   — launch_id missing or marked stopped
        starting  — launch_id present, within 2s grace period after launch
        running   — launch_id matches heartbeat and heartbeat is fresh
        stale     — heartbeat missing or stale, ros2 launch still alive
        crashed   — heartbeat missing or stale, ros2 launch dead

    Only ``stale`` and ``crashed`` trigger a ``docker exec`` call.
    """
    import json

    from psilia_edge.runtime.config import RUN_DIR

    launch_id_file = RUN_DIR / "launch_id"
    hb_file = RUN_DIR / "heartbeat.json"

    try:
        raw = launch_id_file.read_text().strip()
    except OSError:
        return {"state": "stopped", "detail": "no launch_id file"}

    if raw.endswith(":stopped"):
        return {"state": "stopped", "detail": "cleanly stopped"}

    parts = raw.split(":")
    launch_id = parts[0]
    try:
        launch_time = float(parts[1]) if len(parts) >= 2 else None
    except ValueError:
        launch_time = None

    try:
        hb = json.loads(hb_file.read_text())
    except (OSError, json.JSONDecodeError):
        hb = None

    hb_id = hb.get("launch_id") if hb else None
    now = time.time()

    if hb_id == launch_id:
        try:
            age = now - hb_file.stat().st_mtime
        except OSError:
            age = 999
        if age < 5:
            return {"state": "running", "detail": f"heartbeat {age:.1f}s ago"}

        from psilia_edge.runtime.docker import is_ros_launch_running

        if is_ros_launch_running():
            return {"state": "stale", "detail": f"lost {age:.0f}s ago"}
        return {"state": "crashed", "detail": f"lost {age:.0f}s ago"}

    since = f"{now - launch_time:.0f}s since launch" if launch_time else ""

    if launch_time and (now - launch_time) < 2:
        return {"state": "starting", "detail": since}

    from psilia_edge.runtime.docker import is_ros_launch_running

    if is_ros_launch_running():
        return {"state": "stale", "detail": since}
    return {"state": "crashed", "detail": since}


def is_spatial_layer_running() -> bool:
    """Quick check: is the spatial layer running as expected?"""
    return check_spatial_layer_status()["state"] == "running"


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
