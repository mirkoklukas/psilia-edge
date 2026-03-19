#!/bin/bash
#
#   Sources the ROS workspace and launches the given launch file.
#   Intended to be called via `docker exec -d` after the container is running.
#
#   Usage: launch_ros.sh <launch_file>
#
set -e

for f in /etc/profile.d/*.sh; do
    [ -r "$f" ] && source "$f"
done
source /psilia/ros/install/setup.bash

exec ros2 launch psilia_runtime "$1"
