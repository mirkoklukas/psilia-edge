# Notes

## Establishing a network connection to your Jetson

The simplest way to connect your MacBook and Jetson is to put both on the same network — either on the same Wi-Fi, or connected via an ethernet cable. Once on the same network, set up mDNS on the Jetson so you can reach it by name instead of IP.

> **mDNS** = Multicast DNS. Regular DNS uses a central server to resolve names to IPs. mDNS has no server — devices multicast directly on the LAN, announcing their own name and answering queries from others. On Linux this is handled by avahi-daemon, which reads the hostname from /etc/hostname and advertises it as hostname.local on all active interfaces, keeping it updated if IPs change.

Setup on Jetson:
```bash
# 1. set the hostname
sudo hostnamectl set-hostname jetson

#2. install and enable avahi
sudo apt update
sudo apt install avahi-daemon
sudo systemctl enable --now avahi-daemon

# 3. verify
avahi-resolve -n jetson.local
```

Then from your MacBook:
```bash
# verify connection
ping jetson.local

# SSH into the Jetson
ssh user@jetson.local
```

This works without knowing or setting any IP addresses. If the Jetson's IP changes, jetson.local still resolves correctly.

## USB Camera Detection on Linux

On Linux, camera devices are exposed as `/dev/videoX` nodes. When a USB camera is plugged in, the kernel's USB subsystem:

1. Enumerates the device and its interfaces
2. Binds the `uvcvideo` driver to the video interfaces
3. Creates `/dev/videoX` nodes
4. Creates the corresponding sysfs tree under `/sys/devices/...`
5. Creates symlinks in `/sys/class/video4linux/videoX/device` pointing into that sysfs tree

`/sys/class/` is a view organized by device class (video4linux, input, net, etc.), with symlinks back to the actual device entries under `/sys/devices/`.

To list all video nodes:
```bash
ls /dev/video*
```

To get the sysfs path for a node:
```bash
readlink -f /sys/class/video4linux/video0/device
# e.g. /sys/devices/pci0000:00/0000:00:14.0/usb1/1-2/1-2.1/1-2.1:1.0/video4linux/video0
```

The path breaks down as:
```
platform/bus@0/3610000.usb   — USB controller (SoC-integrated on Jetson; pci0000:00/... on PC)
usb1        — USB controller root
1-2         — USB hub
1-2.2       — the physical USB device (bus_id) — shared by all nodes from the same camera
1-2.2:1.0   — USB interface (config 1, interface 0)
video4linux/
  video0    — the V4L2 device node
```

A stereo camera typically exposes two `/dev/videoX` nodes. They share the same `bus_id` and USB serial number, which is how you can tell they belong to the same physical device. Some cameras expose one interface per sensor (`1-2.2:1.0`, `1-2.2:1.1`); others expose both nodes from the same interface (`1-2.2:1.0` for both). In the latter case the interface number cannot be used to distinguish left from right — the kernel's enumeration order (video0=left, video1=right) is the de facto convention.

Device metadata (vendor ID, product ID, manufacturer, serial) lives at the `bus_id` level in sysfs:
```bash
cat /sys/bus/usb/devices/1-2.1/idVendor
cat /sys/bus/usb/devices/1-2.1/manufacturer
cat /sys/bus/usb/devices/1-2.1/serial
```

### v4l2-ctl (`v4l-utils`)

`v4l2-ctl` is a userspace tool for querying and controlling V4L2 devices. It's part of the `v4l-utils` package (`sudo apt install v4l-utils` on Jetson).

List devices with their grouping (same output as our sysfs-based scan, but human-readable):
```bash
v4l2-ctl --list-devices
# Some Stereo Cam (usb-3610000.usb-2.2):
#     /dev/video0
#     /dev/video1
```

List supported formats and resolutions for a device:
```bash
v4l2-ctl --device=/dev/video0 --list-formats-ext
```

This is the main thing our sysfs approach doesn't cover — knowing what resolutions and pixel formats a camera supports. Useful for validating a camera during `psilia runtime setup` and for configuring the ROS camera node. We may want to call this in `scan_cameras()` if `v4l2-ctl` is available, and include the results in the scan output.

## Development

### Local environment variables (direnv)

The runtime uses environment variables to override Jetson-specific default paths. When
developing or testing on a laptop, override them to local paths using
[direnv](https://direnv.net/).

**Install:**
```bash
brew install direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc
```

**Add to `.gitignore`**
```bash
# Local env vars, e.g. for development
# and testing directory for the runtime host
.envrc
_dev/
```

```bash
# From the root of the psilia-edge repo
mkdir -p ./_dev
python scripts/bootstrap.py _dev --system-dir _dev/system --no-setup
```
**Create `.envrc` in the project root:**
```bash
export PSILIA_CONFIG_DIR=$PWD/_dev/system/config
export PSILIA_RUN_DIR=$PWD/_dev/system/run
export PSILIA_LOG_DIR=$PWD/_dev/system/log
export PSILIA_BASE_DIR=$PWD/_dev/psilia
```

Then allow it once: `direnv allow`

The vars are loaded automatically when you `cd` into the project and unloaded when you leave.
`.envrc` is gitignored.


# Cheatsheet

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

## Everything else

Call from `/docs`:
```bash
pandoc psilia-vision.md -o psilia-vision.pdf --pdf-engine=xelatex -V geometry:margin=1.75in
```
