#!/bin/bash
#
#   Container entrypoint: build the ROS workspace, source it, then idle.
#   The spatial layer (ros2 launch) is started separately via `docker exec launch_ros.sh`.
#
set -e

/build_ros_ws.sh "$@"

# Idle — wait for spatial layer to be started via docker exec
exec sleep infinity
