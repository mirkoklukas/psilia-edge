#!/bin/bash
#
#   Sources the ROS workspace and launches the given launch file.
#   Intended to be called via `docker exec -d` after the container is running.
#   Output is redirected to /psilia/log/ros.log (mounted from the host).
#
#   Usage: launch_ros.sh <launch_file>
#
set -e

for f in /etc/profile.d/*.sh; do
    [ -r "$f" ] && source "$f"
done
source /psilia/ros/install/setup.bash

# Truncate log on each launch so it only contains output from the current session.
mkdir -p /psilia/log
: > /psilia/log/ros.log

exec ros2 launch psilia_runtime "$1" >> /psilia/log/ros.log 2>&1
