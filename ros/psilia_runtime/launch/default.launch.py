from launch import LaunchDescription
from launch_ros.actions import Node
from psilia_runtime.better_ros import better_launch


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

    mock_node = Node(
        package="psilia_runtime",
        executable="mock",
        name="psilia_mock",
        output="screen",
    )

    # depth_node = Node(
    #     package="psilia_runtime",
    #     executable="depth",
    #     name="psilia_depth",
    #     output="screen",
    # )

    # pose_node = Node(
    #     package="psilia_runtime",
    #     executable="pose",
    #     name="psilia_pose",
    #     output="screen",
    # )

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

    # foxglove_bridge = Node(
    #     package="foxglove_bridge",
    #     executable="foxglove_bridge",
    #     name="foxglove_bridge",
    #     output="screen",
    # )

    return LaunchDescription([
        core_node,
        ping_node,
        recording_node,
        camera_node,
        preview_node,
        rosbridge,
        mock_node,
    ])
