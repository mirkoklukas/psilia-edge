"""Runtime core — role detection and high-level runtime operations."""

from __future__ import annotations

import logging
import socket
import time

from psilia.edge.runtime.config import get_api_port, read_config
from psilia.edge.runtime.requirements import (
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
    from psilia.edge.runtime.docker import is_container_running

    ok = is_container_running()
    return ResolverResult(
        ok=ok,
        detail="running" if ok else "not running — start base layer first",
    )


def resolve_camera() -> ResolverResult:
    from psilia.edge.runtime.hotplug import pick_camera_device

    camera = pick_camera_device()
    if not camera:
        return ResolverResult(ok=False, detail="no camera detected")

    from psilia.edge.runtime.sensor import build_sensor_id

    sensor_id = build_sensor_id(camera)
    return ResolverResult(
        ok=True,
        detail=camera.get("device", "detected"),
        data={"info": camera, "sensor_id": sensor_id},
    )


def resolve_calibration(camera) -> ResolverResult:
    from psilia.edge.runtime.config import read_runtime_config
    from psilia.edge.runtime.sensor import get_calibration_file

    rt_config = read_runtime_config()
    camera_config = rt_config.get("camera", {})
    sensor_id = camera.data.get("sensor_id") if camera.ok else None

    cal_path = get_calibration_file(camera_config.get("name"), sensor_id)
    if not cal_path:
        return ResolverResult(ok=False, detail="no calibration found")

    container_path = f"/psilia/calibrations/{cal_path.name}"
    return ResolverResult(
        ok=True,
        detail=cal_path.name,
        data={"host_path": cal_path, "container_path": container_path},
    )


def resolve_resolution(camera, calibration) -> ResolverResult:
    from psilia.edge.runtime.sensor import (
        get_calibration_resolution,
        is_calibration_compatible,
    )

    cal_path = calibration.data["host_path"]
    camera_info = camera.data["info"]

    cal_res = get_calibration_resolution(cal_path)
    if not cal_res:
        return ResolverResult(ok=False, detail="cannot read calibration resolution")

    cal_w, cal_h = cal_res

    # Try smallest compatible resolution.
    sizes = camera_info.get("available_sizes", [])
    for size in sorted(sizes, key=lambda s: s["width"] * s["height"]):
        if is_calibration_compatible(cal_w, cal_h, size["width"], size["height"]):
            return ResolverResult(
                ok=True,
                detail=f"{size['width']}x{size['height']}",
                data={"width": size["width"], "height": size["height"]},
            )

    # Fallback: exact calibration resolution (stereo: 2*cal_w x cal_h).
    width = cal_w * 2
    height = cal_h
    return ResolverResult(
        ok=True,
        detail=f"{width}x{height} (calibration match)",
        data={"width": width, "height": height},
    )


def resolve_cuda() -> ResolverResult:
    from psilia.edge.runtime.docker import has_cuda

    ok = has_cuda()
    return ResolverResult(
        ok=ok,
        detail="available" if ok else "not available",
    )


def resolve_hotspot() -> ResolverResult:
    from psilia.edge.network.hotspot import get_ap_ssid
    from psilia.edge.network.probe import list_interfaces

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
                [
                    RequirementSpec(
                        "resolution",
                        resolve_resolution,
                        ("camera", "camera.calibration"),
                    ),
                ],
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
def start_base_layer(host: str = "0.0.0.0", port: int | None = None) -> dict:
    """Start the FastAPI daemon and the runtime container. Returns a summary dict for display."""
    from psilia.edge.runtime.daemon import LOG_FILE, start_daemon
    from psilia.edge.runtime.docker import (
        is_docker_daemon_running,
        start_runtime_container,
    )

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
    from psilia.edge.runtime.daemon import stop_daemon
    from psilia.edge.runtime.docker import is_container_running, stop_runtime_container

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


def _build_launch_params(ctx) -> dict:
    """Build node list and per-node parameters from resolved requirements.

    Returns a dict ready to be written to launch_params.yaml:
        nodes: [list of conditional node names to launch]
        <node_name>: {ros__parameters: {...}}

    After building the requirement-derived node list, applies user overrides
    from runtime.yaml ``ros.nodes``. Each entry can be a bool (enable/disable)
    or a dict with ``enable`` and ``parameters`` keys. Nodes set to disabled
    are removed. User parameters are merged on top of requirement-derived ones.
    """
    from psilia.edge.runtime.config import read_runtime_config

    nodes = []
    params = {}

    camera = ctx["camera"]
    if camera.ok:
        camera_info = camera.data["info"]
        camera_params = {
            k: camera_info[k]
            for k in ("device", "pixel_format", "width", "height", "fps")
            if k in camera_info
        }
        resolution = ctx["camera.calibration.resolution"]
        if resolution and resolution.ok:
            camera_params["width"] = resolution.data["width"]
            camera_params["height"] = resolution.data["height"]

        params["camera_node"] = {"ros__parameters": camera_params}
        nodes.extend(["camera_node", "preview_node"])

    calibration = ctx["camera.calibration"] if camera.ok else None
    if calibration and calibration.ok:
        container_path = calibration.data["container_path"]
        logger.info("Calibration resolved: %s", container_path)
        cal_params = {"ros__parameters": {"calibration_file": container_path}}
        # Pass calibration to camera node for CameraInfo publishing.
        if "camera_node" in params:
            params["camera_node"]["ros__parameters"]["calibration_file"] = (
                container_path
            )
        params["rectify_node"] = cal_params
        params["depth_node"] = cal_params
        nodes.extend(
            [
                "rectify_node",
                "depth_node",
                "depth_preview_node",
                "pointcloud_preview_node",
            ]
        )

        cuda = ctx["container.cuda"]
        if cuda.ok:
            params["depth_cuda_node"] = cal_params
            nodes.append("depth_cuda_node")
    elif camera.ok:
        logger.warning(
            "No calibration found for camera (UID: %s). "
            "Rectify/depth nodes will not launch.",
            camera.data.get("sensor_id"),
        )
    else:
        logger.info("No camera detected and no camera configured.")

    # Apply node config: defaults, then user overrides from runtime.yaml ros.nodes.
    # Each entry can be:
    #   bool              — enable/disable (backward compat)
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

        if not enabled and name in nodes:
            logger.info("Disabled node: %s", name)
            nodes.remove(name)
        elif user_params and name in nodes:
            existing = params.get(name, {}).get("ros__parameters", {})
            params[name] = {"ros__parameters": {**existing, **user_params}}

    return {"nodes": nodes, **params}


def start_spatial_layer(force: bool = False) -> dict:
    """Launch ros2 inside the running container.

    Returns a summary dict for display (CLI tree, API JSON). No caller
    depends on specific keys — treat as informational.
    """
    from psilia.edge.runtime.config import RUN_DIR, get_launch_script
    from psilia.edge.runtime.docker import start_ros_launch
    from psilia.edge.utils import write_yaml

    logger.info("Checking spatial requirements…")
    ctx = check_spatial_requirements()

    if not ctx["container"].ok:
        raise SpatialRequirementsError(ctx)

    if not force and not ctx.ok:
        raise SpatialRequirementsError(ctx)

    logger.info("Building launch parameters…")
    launch_params = _build_launch_params(ctx)

    RUN_DIR.mkdir(parents=True, exist_ok=True)
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
    from psilia.edge.runtime.docker import is_ros_launch_running, stop_ros_launch

    if not is_ros_launch_running():
        logger.info("ROS nodes not running — skipping")
        return {"status": "not_running"}

    logger.info("Stopping ROS nodes…")
    rc, _, err = stop_ros_launch()
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
    from psilia.edge.runtime.daemon import is_running

    return is_running()


def is_spatial_layer_running() -> bool:
    from psilia.edge.runtime.docker import is_ros_launch_running

    return is_ros_launch_running()


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
    from psilia.edge.ui import error

    if not is_runtime_host():
        error(
            f"[red]No local runtime found. Run `psilia runtime setup` first.[/red]\n"
            f"To target a registered device: [bold]psilia {device_hint}[/bold]"
        )
        raise typer.Exit(1)
