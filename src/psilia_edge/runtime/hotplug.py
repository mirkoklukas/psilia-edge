"""Hotplug — USB camera detection.

Currently uses an active scan. Future: replace with a pyudev MonitorObserver
for event-driven detection without polling.

Usage:
    groups = scan_cameras()
    # [[{"device": "/dev/video0", ...}, {"device": "/dev/video1", ...}], ...]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


# Known USB vendor IDs → camera family
_VENDOR_TYPES: dict[str, str] = {
    "2b03": "stereolabs",  # ZED cameras
    "03e7": "luxonis",  # OAK-D cameras
}

# Known (vendor_id, product_id) pairs for Intel RealSense
_REALSENSE_PRODUCTS = {
    "0ad3",
    "0ad4",
    "0ad5",
    "0ad6",  # D415
    "0b07",
    "0b3a",  # D435 / D435i
    "0b4b",  # D455
    "0b64",  # L515
}


def _identify_type(vendor_id: str, product_id: str) -> str:
    if vendor_id in _VENDOR_TYPES:
        return _VENDOR_TYPES[vendor_id]
    if vendor_id == "8086" and product_id in _REALSENSE_PRODUCTS:
        return "intel-realsense"
    return "uvc"


def _read_usb_info(dev_name: str) -> dict:
    """Walk sysfs from the video4linux device up to the USB device node."""
    device_link = Path(f"/sys/class/video4linux/{dev_name}/device")
    if not device_link.exists():
        return {}

    path = device_link.resolve()
    while path != path.parent:
        if (path / "idVendor").exists():
            info: dict = {"bus_id": path.name}
            for field in ("idVendor", "idProduct", "manufacturer", "product", "serial"):
                f = path / field
                if f.exists():
                    info[field] = f.read_text().strip()
            return info
        path = path.parent
    return {}


def _group_cameras(cameras: list[dict]) -> list[list[dict]]:
    """Group cameras by serial (preferred) or bus_id — same physical device."""
    groups: dict[str, list[dict]] = {}
    ungrouped: list[dict] = []
    for cam in cameras:
        key = cam.get("serial") or cam.get("bus_id")
        if key:
            groups.setdefault(key, []).append(cam)
        else:
            ungrouped.append([cam])
    return list(groups.values()) + ungrouped


# =============================================================================
# v4l2-ctl utils
# =============================================================================


def v4l2_list_formats(dev: str) -> dict[str, str]:
    """Return available pixel formats for a device.

    Calls: v4l2-ctl -d <dev> --list-formats

    Returns {pixel_format: description}, e.g.:
        {"YUYV": "YUYV 4:2:2", "MJPG": "Motion-JPEG, compressed"}
    """
    import re

    result = subprocess.run(
        ["v4l2-ctl", "-d", dev, "--list-formats"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    formats = {}
    for m in re.finditer(r"'(\w+)'\s+\((.+)\)", result.stdout):
        formats[m.group(1)] = m.group(2)
    return formats


def v4l2_list_framesizes(dev: str, pixel_format: str) -> list[dict]:
    """Return available frame sizes for a device and pixel format.

    Calls: v4l2-ctl -d <dev> --list-framesize <pixel_format>

    Returns [{"width": W, "height": H}, ...], e.g.:
        [{"width": 1280, "height": 480}, {"width": 640, "height": 480}]
    """
    import re

    result = subprocess.run(
        ["v4l2-ctl", "-d", dev, "--list-framesize", pixel_format],
        capture_output=True,
        text=True,
        timeout=5,
    )
    sizes = []
    for m in re.finditer(r"Size: Discrete (\d+)x(\d+)", result.stdout):
        sizes.append({"width": int(m.group(1)), "height": int(m.group(2))})
    return sizes


# =============================================================================
# Linux scan
# =============================================================================


def _scan_linux_2() -> list[dict]:
    """Like _scan_linux but adds format/resolution info via v4l2-ctl."""
    cameras = _scan_linux()
    for cam in cameras:
        formats = v4l2_list_formats(cam["device"])
        if formats:
            cam["formats"] = {
                fmt: {
                    "description": desc,
                    "sizes": v4l2_list_framesizes(cam["device"], fmt),
                }
                for fmt, desc in formats.items()
            }
    return cameras


def scan_cameras() -> list[list[dict]]:
    """Return cameras grouped by physical device (serial or bus_id).

    On Linux: scans /dev/video* and reads the device name from sysfs,
              enriched with format/resolution info via v4l2-ctl.
    On macOS: uses system_profiler SPUSBDataType, enriched with
              format/resolution info via ffmpeg (AVFoundation).
    """
    if sys.platform == "linux":
        return _group_cameras(_scan_linux_2())
    if sys.platform == "darwin":
        return _group_cameras(_scan_macos_2())
    return []


def _scan_linux() -> list[dict]:
    cameras = []
    for dev in sorted(Path("/dev").glob("video*")):
        index = int(dev.name.replace("video", ""))
        entry: dict = {"device": str(dev), "index": index}

        name_file = Path(f"/sys/class/video4linux/{dev.name}/name")
        if name_file.exists():
            entry["name"] = name_file.read_text().strip()

        usb = _read_usb_info(dev.name)
        if usb:
            vendor_id = usb.pop("idVendor", "")
            product_id = usb.pop("idProduct", "")
            entry["type"] = _identify_type(vendor_id, product_id)
            entry["vendor_id"] = vendor_id
            entry["product_id"] = product_id
            entry.update(usb)  # bus_id, manufacturer, product, serial

        cameras.append(entry)
    return cameras


# =============================================================================
# USB bus topology
#
# /sys/bus/usb/devices/ contains one entry per USB device AND per USB interface.
# The naming convention encodes position in the physical tree:
#
#   usbN          — root hub for bus N (one per USB controller)
#   N-P           — device on bus N, directly on port P of the root hub
#   N-P.Q         — device on bus N, through a hub on port P, sub-port Q
#   N-P.Q.R       — device through two hubs, and so on
#   N-P.Q:C.I     — interface I of config C on device N-P.Q  ← we skip these
#
# Example from a real Jetson listing:
#   usb1, usb2          — two USB controllers
#   1-2                 — a hub plugged into port 2 of bus 1
#   1-2.1               — a sub-hub plugged into port 1 of that hub
#   1-2.1.2             — HID device on sub-hub port 2
#   1-2.2               — 3D USB Camera on hub port 2
#   1-2.3               — WiFi dongle on hub port 3
#   1-3                 — Bluetooth on port 3 of the root hub
#   2-1                 — a hub on bus 2, port 1
#   2-1.1               — ZED 2i on that hub, port 1
#
# A device with a `maxchild` file is a hub — it has downstream ports of its own.
# We recurse into hubs to build the full tree. Empty ports are represented as None.
# =============================================================================


def _usb_device_info(dev_path: Path) -> dict:
    """Read identity and classify a USB device from its sysfs path.

    Classification is done by checking which kernel subsystems the device
    registered under: video4linux → camera, net → wifi/ethernet, else other.
    """
    info: dict = {}
    for field, key in [
        ("idVendor", "vendor_id"),
        ("idProduct", "product_id"),
        ("manufacturer", "manufacturer"),
        ("product", "product"),
        ("serial", "serial"),
    ]:
        f = dev_path / field
        if f.exists():
            info[key] = f.read_text().strip()

    # Classification: look only at direct interface subdirs (name contains ':',
    # e.g. "1-2.2:1.0"). These are the kernel interface nodes that register with
    # subsystems like video4linux or net. We intentionally avoid rglob here so
    # that hub nodes don't pick up devices from their downstream subtree.
    video_nodes = []
    net_ifaces = []
    for subdir in dev_path.iterdir():
        if ":" not in subdir.name:
            continue  # skip non-interface dirs
        vl = subdir / "video4linux"
        if vl.exists():
            video_nodes += sorted(
                f"/dev/{n.name}" for n in vl.iterdir() if n.name.startswith("video")
            )
        net = subdir / "net"
        if net.exists():
            net_ifaces += [iface.name for iface in net.iterdir()]

    if video_nodes:
        info["class"] = "camera"
        info["nodes"] = sorted(video_nodes)
        return info

    if net_ifaces:
        # Check /sys/class/net/<iface>/wireless to distinguish wifi from ethernet.
        is_wireless = any(
            (Path("/sys/class/net") / iface / "wireless").exists()
            for iface in net_ifaces
        )
        info["class"] = "wifi" if is_wireless else "ethernet"
        info["interfaces"] = net_ifaces
        return info

    info["class"] = "other"
    return info


def _usb_subtree(dev_path: Path, usb_devices: Path, addr: str) -> dict:
    """Recursively build a subtree for a USB device, descending into hubs.

    If the device is a hub (maxchild > 0), its children in sysfs are named
    {addr}.1, {addr}.2, ... up to maxchild. We recurse into each.
    Note: maxchild exists on all USB devices; leaf devices have maxchild=0.
    """
    info = _usb_device_info(dev_path)

    num_ports_file = dev_path / "maxchild"
    if num_ports_file.exists():
        num_ports = int(num_ports_file.read_text().strip())
        # maxchild exists on all USB devices; only recurse if it has downstream ports.
        if num_ports > 0:
            info["class"] = "hub"
            ports: dict[int, dict | None] = {}
            for port in range(1, num_ports + 1):
                child_addr = f"{addr}.{port}"  # e.g. "1-2.1" → "1-2.1.1"
                child_path = usb_devices / child_addr
                ports[port] = (
                    _usb_subtree(child_path, usb_devices, child_addr)
                    if child_path.exists()
                    else None  # empty port
                )
            info["ports"] = ports

    return info


def usb_list_devices() -> list[dict]:
    """Return a flat list of connected USB devices (excluding hubs and root hubs).

    Walks /sys/bus/usb/devices/, skips:
      - root hubs (usbN)
      - interface nodes (name contains ':')
      - hubs (maxchild > 0)

    Returns one entry per physical device with class, identity, and nodes/interfaces.
    """
    import re

    usb_devices = Path("/sys/bus/usb/devices")
    if not usb_devices.exists():
        return []

    devices = []
    for entry in sorted(usb_devices.iterdir()):
        # Skip root hubs (usb1, usb2)
        if re.match(r"^usb\d+$", entry.name):
            continue
        # Skip interface nodes (1-2.2:1.0)
        if ":" in entry.name:
            continue
        # Skip hubs (maxchild > 0)
        maxchild_file = entry / "maxchild"
        if maxchild_file.exists() and int(maxchild_file.read_text().strip()) > 0:
            continue

        info = _usb_device_info(entry)
        info["addr"] = entry.name
        devices.append(info)

    return devices


def usb_bus_tree() -> dict:
    """Return USB bus topology as a nested dict.

    Walks /sys/bus/usb/devices/ recursively, descending into hubs.
    Empty ports are represented as None.

    Example:
        {
            "usb2": {
                "name": "xHCI Host Controller",
                "ports": {
                    1: {
                        "class": "hub",
                        "ports": {
                            1: {"product": "ZED 2i", "class": "camera", "nodes": [...]},
                            2: None,  # empty port
                        }
                    }
                }
            }
        }
    """
    import re

    usb_devices = Path("/sys/bus/usb/devices")
    if not usb_devices.exists():
        return {}

    tree = {}
    for entry in sorted(usb_devices.iterdir()):
        # Only process root hubs (usbN) — skip device and interface nodes.
        if not re.match(r"^usb\d+$", entry.name):
            continue

        # Bus number: "usb1" → "1", used to construct child addresses like "1-2".
        bus_num = entry.name.replace("usb", "")
        num_ports_file = entry / "maxchild"
        num_ports = (
            int(num_ports_file.read_text().strip()) if num_ports_file.exists() else 0
        )

        # Top-level devices are addressed as "{bus_num}-{port}", e.g. "1-2".
        ports: dict[int, dict | None] = {}
        for port in range(1, num_ports + 1):
            child_addr = f"{bus_num}-{port}"
            child_path = usb_devices / child_addr
            ports[port] = (
                _usb_subtree(child_path, usb_devices, child_addr)
                if child_path.exists()
                else None
            )

        name = (
            (entry / "product").read_text().strip()
            if (entry / "product").exists()
            else ""
        )
        tree[entry.name] = {"name": name, "ports": ports}

    return tree


def pick_camera_device(fps: int = 30) -> dict | None:
    """Detect the first connected camera and pick the best device node, format, and resolution.

    Scans for connected cameras, takes the first physical device, and picks:
    - The device node with actual image formats (skipping metadata-only nodes)
    - Preferred format: MJPG > YUYV > first available
    - Preferred resolution: largest available

    Returns a dict with device, pixel_format, width, height, fps — or None if no camera found.
    Only works on Linux; returns None on other platforms.
    """
    if sys.platform != "linux":
        return None

    groups = scan_cameras()
    if not groups:
        return None

    for cam in groups[0]:
        formats = cam.get("formats", {})
        if not formats:
            continue

        if "MJPG" in formats:
            fmt = "MJPG"
        elif "YUYV" in formats:
            fmt = "YUYV"
        else:
            fmt = next(iter(formats))

        sizes = formats[fmt].get("sizes", [])
        if not sizes:
            continue

        size = max(sizes, key=lambda s: s["width"] * s["height"])

        result = {
            "device": cam["device"],
            "pixel_format": fmt,
            "width": size["width"],
            "height": size["height"],
            "fps": fps,
            "available_sizes": sizes,
        }
        # Include all identity fields from the camera entry.
        for field in (
            "name",
            "type",
            "vendor_id",
            "product_id",
            "manufacturer",
            "product",
            "serial",
            "bus_id",
        ):
            if field in cam:
                result[field] = cam[field]
        return result

    return None


# =============================================================================
# AVFoundation utils (macOS) — equivalent of v4l2-ctl, requires ffmpeg/ffprobe
# =============================================================================


def _avf_list_devices() -> list[dict]:
    """List AVFoundation video devices via ffmpeg.

    Returns [{"index": 0, "name": "ZED 2i"}, ...].
    Requires ffmpeg; returns [] if not installed.
    """
    import re

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-f",
                "avfoundation",
                "-list_devices",
                "true",
                "-i",
                "",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        return []

    devices = []
    in_video = False
    for line in result.stderr.splitlines():
        if "AVFoundation video devices:" in line:
            in_video = True
            continue
        if "AVFoundation audio devices:" in line:
            break
        if in_video:
            m = re.search(r"\[(\d+)\]\s+(.+)", line)
            if m:
                devices.append({"index": int(m.group(1)), "name": m.group(2).strip()})
    return devices


def _avf_device_formats(device_index: int) -> dict[str, dict]:
    """Query available resolutions for an AVFoundation device via ffprobe.

    ffprobe prints "Supported modes:" with lines like "2560x720@[30.0 30.0]fps"
    when it fails to open the device at the default framerate. We parse those
    to extract unique resolutions.

    Returns same structure as v4l2 format data. Since AVFoundation doesn't
    expose per-format resolution lists, sizes are grouped under a single
    "unknown" key.

    Requires ffprobe; returns {} if not installed.
    """
    import re

    try:
        result = subprocess.run(
            ["ffprobe", "-hide_banner", "-f", "avfoundation", "-i", str(device_index)],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return {}

    seen: set[tuple[int, int]] = set()
    sizes: list[dict] = []
    for line in result.stderr.splitlines():
        m = re.search(r"(\d{3,5})x(\d{3,5})@", line)
        if not m:
            continue
        w, h = int(m.group(1)), int(m.group(2))
        if (w, h) not in seen:
            seen.add((w, h))
            sizes.append({"width": w, "height": h})

    if not sizes:
        return {}
    return {"unknown": {"description": "unknown", "sizes": sizes}}


def _scan_macos_2() -> list[dict]:
    """Like _scan_macos but adds format/resolution info via ffmpeg (AVFoundation)."""
    cameras = _scan_macos()
    avf_devices = _avf_list_devices()
    if not avf_devices:
        return cameras

    for cam in cameras:
        cam_name = cam.get("product", cam.get("name", ""))
        for avf in avf_devices:
            if avf["name"] == cam_name or cam_name in avf["name"]:
                formats = _avf_device_formats(avf["index"])
                if formats:
                    cam["formats"] = formats
                break
    return cameras


def _scan_macos() -> list[dict]:
    """Scan USB devices on macOS via system_profiler SPUSBDataType.

    Uses the USB bus listing (not SPCameraDataType) so that we get the
    real USB serial descriptor, matching what Linux reads from sysfs.
    """
    try:
        result = subprocess.run(
            ["system_profiler", "SPUSBDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        data = json.loads(result.stdout)
    except Exception:
        return []

    # Walk the bus tree and collect all USB devices.
    usb_devices: list[dict] = []

    def _collect(items: list[dict]) -> None:
        for item in items:
            if "vendor_id" in item:
                usb_devices.append(item)
            if "_items" in item:
                _collect(item["_items"])

    _collect(data.get("SPUSBDataType", []))

    # Filter to cameras and build entries.
    cameras = []
    for dev in usb_devices:
        vendor_id = dev.get("vendor_id", "").removeprefix("0x").lower()
        product_id = dev.get("product_id", "").removeprefix("0x").lower()
        cam_type = _identify_type(vendor_id, product_id)
        if cam_type == "uvc" and not dev.get("_name", "").lower().endswith("camera"):
            continue  # skip non-camera USB devices

        entry: dict = {"name": dev.get("_name", "Unknown")}
        entry["type"] = cam_type
        if vendor_id:
            entry["vendor_id"] = vendor_id
        if product_id:
            entry["product_id"] = product_id
        if serial := dev.get("serial_num"):
            entry["serial"] = serial
        if manufacturer := dev.get("manufacturer"):
            entry["manufacturer"] = manufacturer
        entry["product"] = dev.get("_name", "Unknown")

        cameras.append(entry)
    return cameras
