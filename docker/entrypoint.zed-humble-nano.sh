#!/bin/bash
set -e

# Source base ROS2 first
source /opt/ros/humble/setup.bash

if [ -f /ros_ws/install/local_setup.bash ]; then
    echo "Found '/ros_ws/install/local_setup.bash', running it..."
    source /ros_ws/install/local_setup.bash
else
    echo "No local setup script found at '/ros_ws/install/local_setup.bash'."
    echo "You might want to run: 'colcon build'"
    echo "and then: 'source install/local_setup.bash'"
fi

# Ensure the ROS environment is sourced in any new shell
SNIPPET='
source /opt/ros/humble/setup.bash
source /ros_ws/install/local_setup.bash
if [ -f /ros_ws/install/local_setup.bash ]; then
    source /ros_ws/install/local_setup.bash
fi
cd /ros_ws
'
echo "$SNIPPET" >> ~/.bashrc

# Start in the ROS workspace
cd /ros_ws

exec "$@"
