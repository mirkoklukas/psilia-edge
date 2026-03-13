# Psilia Edge — Cheatsheet

## Docker

```bash
# Enter the running container (with ROS sourced)
docker exec -it psilia-runtime bash -l

# Check container state
docker ps -a

# View container logs
docker logs psilia-runtime

# Stream container logs live
docker logs -f psilia-runtime

# Build the image manually
docker build --network=host -t psilia/runtime:latest /ssd/psilia/psilia-edge/ros/
```

## Runtime (Jetson)

```bash
# Start base layer + spatial layer
psilia start

# Stop everything
psilia stop

# Show runtime status
psilia status

# Attach to the running daemon log (Ctrl-C to detach)
psilia attach

# Pull latest repo, sync ROS package, rebuild Docker image
psilia update
```

## Runtime (Laptop)

```bash
# Same commands, targeting a registered device
psilia start borne
psilia stop borne
psilia status borne
psilia attach borne
psilia update borne
```

## ROS (inside container)

```bash
ros2 node list
ros2 topic list
ros2 topic echo /psilia/pose

# Tail the latest ROS launch log
tail -f ~/.ros/log/latest/launch.log
```
