from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    core_node = Node(
        package="psilia_runtime",
        executable="core",
        name="psilia_core",
        output="screen",
    )

    ping_node = Node(
        package="psilia_runtime",
        executable="ping",
        name="psilia_ping",
        output="screen",
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
        mock_node,
        rosbridge,
    ])
