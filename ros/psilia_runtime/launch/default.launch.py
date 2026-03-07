from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    mock_node = Node(
        package="psilia_runtime",
        executable="mock_node",
        name="mock_node",
        output="screen",
    )

    status_node = Node(
        package="psilia_runtime",
        executable="status_node",
        name="status_node",
        output="screen",
    )

    # depth_node = Node(
    #     package="psilia_runtime",
    #     executable="depth_node",
    #     name="depth_node",
    #     output="screen",
    # )

    # pose_node = Node(
    #     package="psilia_runtime",
    #     executable="pose_node",
    #     name="pose_node",
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
        mock_node,
        status_node,
        rosbridge,
    ])
