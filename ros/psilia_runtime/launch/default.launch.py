import yaml
from launch import LaunchDescription
from launch_ros.actions import Node # type: ignore
from psilia_runtime.better_ros import better_launch

_PSILIA_CONFIG = "/psilia/psilia.yaml"
_RUNTIME_CONFIG = "/psilia/runtime.yaml"
# launch_params.yaml is written by start_spatial_layer() on the host before container launch.
# It contains camera parameters detected at startup (device, format, resolution, fps).
# If the file doesn't exist the node falls back to its declared defaults.
_LAUNCH_PARAMS = "/psilia/run/launch_params.yaml"

def _load_yaml(path):
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


@better_launch
def generate_launch_description():
    launch_params = _load_yaml(_LAUNCH_PARAMS)

    # --- Infrastructure (always launched) ---
    core_node = Node(
        package="psilia_runtime",
        executable="core_node",
        name="core_node",
        output="screen",
        parameters=[{
            "psilia_version": "0.1.0",
            "interface_topics": ["/psilia/heartbeat"],
        }],
    )

    ping_node = Node(
        package="psilia_runtime",
        executable="ping_node",
        name="ping_node",
        output="screen",
    )

    recording_node = Node(
        package='psilia_runtime',
        executable='recording_node',
        name='recording_node',
        output='screen',
    )

    rosbridge = Node(
        package="rosbridge_server",
        executable="rosbridge_websocket",
        name="rosbridge_websocket",
        output="screen",
        parameters=[{"port": 9090}],
    )

    rosapi = Node(
        package="rosapi",
        executable="rosapi_node",
        name="rosapi",
        output="screen",
    )

    diagnostics_node = Node(
        package="psilia_runtime",
        executable="diagnostics_node",
        name="diagnostics_node",
        output="screen",
    )

    nodes = [core_node, ping_node, recording_node, diagnostics_node, rosbridge, rosapi]

    # --- Spatial nodes (only if listed in launch_params.nodes) ---
    spatial_nodes = []
    for name in launch_params.get("nodes", []):
        node_params = launch_params.get(name, {}).get("ros__parameters", {})
        spatial_nodes.append(Node(
            package="psilia_runtime",
            executable=name,
            name=name,
            output="screen",
            parameters=[node_params] if node_params else [],
        ))

    # --- Foxglove (config-driven) ---
    psilia_cfg = _load_yaml(_PSILIA_CONFIG)
    runtime_cfg = _load_yaml(_RUNTIME_CONFIG)
    foxglove_cfg = runtime_cfg.get("ros", {}).get("foxglove", {})

    if foxglove_cfg.get("enabled", False):
        port = psilia_cfg.get("runtime", {}).get("foxglove_port", 8765)
        topics = foxglove_cfg.get("topics", [".*"])
        nodes.append(Node(
            package="foxglove_bridge",
            executable="foxglove_bridge",
            name="foxglove_bridge",
            output="screen",
            parameters=[{"port": port, "topic_whitelist": topics}],
        ))
        print(f"\n[psilia] Foxglove bridge on ws://localhost:{port}")
        print(f"[psilia] Open https://app.foxglove.dev and connect to ws://<device-ip>:{port}\n")
        print(f"[psilia] TOPICS: {topics}\n")

    return LaunchDescription(nodes + spatial_nodes)
