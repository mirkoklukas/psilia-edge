#!/bin/bash
set -e

source /opt/ros/humble/setup.bash

# Build the mounted workspace (incremental — fast after first build)
cd /opt/psilia/ros
colcon build --packages-select psilia_runtime --base-paths src

source /opt/psilia/ros/install/setup.bash

exec "$@"
