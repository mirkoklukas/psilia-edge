# Psilia Edge — Cheatsheet

## Network
```bash
# Show all connections
nmcli connection show

# Show all available networks on the jetson
nmcli device wifi list

# All wifi interfaces
nmcli device status | grep wifi

# New connection
nmcli dev wifi connect "SSID" password "yourpassword"
nmcli dev wifi connect "SSID" password "yourpassword" ifname wlan0

# Delete connection
nmcli connection delete "name"

# Activate connection
nmcli connection up "name"
```
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

docker logs psilia-runtime -f
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

## Getting into a headless Jetson (no monitor, no existing SSH)

```bash
# --- Option 1: USB serial console ---
# Connect Mac to Jetson via USB-A to micro-USB (or USB-C).
# Find the device:
ls /dev/tty.usb*
# Connect (115200 baud):
screen /dev/tty.usbmodem... 115200

# --- Option 2: mDNS (if avahi/hostname already configured) ---
# Default JetPack hostname is usually 'nvidia' or 'tegra-ubuntu':
ping nvidia.local
ssh nvidia@nvidia.local
```

## ROS (inside container)

```bash
ros2 node list
ros2 topic list
ros2 topic echo /psilia/pose

# Tail the latest ROS launch log
tail -f ~/.ros/log/latest/launch.log

ros2 topic hz /psilia/image/raw
```
