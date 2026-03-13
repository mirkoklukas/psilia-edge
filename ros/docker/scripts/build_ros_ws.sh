#!/bin/bash
#
#   Builds the ROS workspace, and optionally clears the build cache
#   first if --clear-cache is passed as an argument.
#   Intended to be used as the entrypoint for the psilia-runtime ROS container.
#
#   Usage: build_ros_ws [--clear-cache]
#
set -e

# Optionally clear colcon build cache so any setup.py changes are picked up.
if [[ "$1" == "--clear-cache" || "$1" == "--clear_cache" ]]; then
    /clear_build_cache.sh
    shift
fi

# Build the workspace and source it so launch files can find the packages.
source /etc/profile.d/ros_setup.sh
cd /psilia/ros
colcon build --packages-select psilia_runtime --base-paths src
source /psilia/ros/install/setup.bash
