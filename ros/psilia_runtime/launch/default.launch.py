import yaml
from launch import LaunchDescription
from launch_ros.actions import Node # type: ignore
from psilia_runtime.better_ros import better_launch

_PSILIA_CONFIG = "/psilia/psilia.yaml"
_RUNTIME_CONFIG = "/psilia/runtime.yaml"

def _load_yaml(path):
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


@better_launch
def generate_launch_description():
    core_node = Node(
        package="psilia_runtime",
        executable="core",
        name="psilia_core",
        output="screen",
        parameters=[{
            "psilia_version": "0.1.0",
            "interface_topics": ["/psilia/heartbeat"],
        }],
    )

    ping_node = Node(
        package="psilia_runtime",
        executable="ping",
        name="psilia_ping",
        output="screen",
    )

    # enables recording through the web UI
    recording_node = Node(
            package='psilia_runtime',
            executable='recording',
            name='psilia_recording',
            output='screen',
    )


    # launch_params.yaml is written by start_spatial_layer() on the host before container launch.
    # It contains camera parameters detected at startup (device, format, resolution, fps).
    # If the file doesn't exist the node falls back to its declared defaults.
    _LAUNCH_PARAMS = "/psilia/run/launch_params.yaml"
    camera_node = Node(
        package="psilia_runtime",
        executable="camera",
        name="camera_node",
        output="screen",
        parameters=[_LAUNCH_PARAMS],
    )

    preview_node = Node(
        package="psilia_runtime",
        executable="preview",
        name="preview_node",
        output="screen",
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

    nodes = [
        core_node,
        ping_node,
        recording_node,
        camera_node,
        preview_node,
        rosbridge,
        rosapi,
    ]

    psilia_cfg = _load_yaml(_PSILIA_CONFIG)
    runtime_cfg = _load_yaml(_RUNTIME_CONFIG)
    foxglove_cfg = runtime_cfg.get("ros", {}).get("foxglove", {})

    if foxglove_cfg.get("enabled", False):
        port = psilia_cfg.get("runtime", {}).get("foxglove_port", 8765)
        topics = foxglove_cfg.get("topics", [".*"])
        foxglove_bridge = Node(
            package="foxglove_bridge",
            executable="foxglove_bridge",
            name="foxglove_bridge",
            output="screen",
            parameters=[{"port": port, "topic_whitelist": topics}],
        )
        nodes.append(foxglove_bridge)

    return LaunchDescription(nodes)
