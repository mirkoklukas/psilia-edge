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
