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

# Copy and build the psilia_runtime ROS package
COPY psilia_runtime/ /opt/psilia/ros/psilia_runtime/
RUN . /opt/ros/humble/setup.sh && \
    cd /opt/psilia/ros && \
    colcon build --packages-select psilia_runtime

# Entrypoint: source workspaces and launch
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["ros2", "launch", "psilia_runtime", "default.launch.py"]
