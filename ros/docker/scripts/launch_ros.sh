#!/bin/bash
#
#   Builds the ROS workspace and then launches the specified launch file.
#   Intended to be used as the entrypoint for the psilia-runtime ROS container.
#
#   Usage: launch_ros <launch_file>
#
set -e

# Source all scripts in /etc/profile.d/ to set up the environment
# See Dockerfile for how these are generated.
for f in /etc/profile.d/*.sh; do
    [ -r "$f" ] && source "$f"
done

# Build the workspace and (re-)source it so launch files can find the packages.
cd /psilia/ros
rm -f /psilia/log/ros-build.log
colcon build --packages-select psilia_runtime --base-paths src > /psilia/log/ros-build.log 2>&1
source /psilia/ros/install/setup.bash

# Usage: ros2_launch <launch_file>
launch_ros() {
    launch_script="$1"
    ros2 launch psilia_runtime "$launch_script"
}

launch_ros "$@"
