# psilia/runtime:latest
# Builds the Spatial Runtime Docker image for Jetson (ROS 2 Humble + CUDA).
#
# TODO: replace base image with JetPack-compatible ROS 2 Humble base
FROM ros:humble

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3-pip \
    ros-humble-rosbridge-server \
    # ros-humble-foxglove-bridge \
    && rm -rf /var/lib/apt/lists/*

# Install psilia inference library (depth + pose algorithms)
# RUN pip install psilia

# psilia_runtime is mounted from the Jetson host at runtime:
#   docker run -v /ssd/psilia/ros:/opt/psilia/ros ...
# Expected layout: /ssd/psilia/ros/src/psilia_runtime/
# The entrypoint runs colcon build on startup (incremental after first build).

# Entrypoint: build workspace, source, and launch
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["ros2", "launch", "psilia_runtime", "default.launch.py"]
