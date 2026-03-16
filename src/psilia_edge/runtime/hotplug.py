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
        usb = cam.get("usb", {})
        key = usb.get("serial") or usb.get("bus_id")
        if key:
            groups.setdefault(key, []).append(cam)
        else:
            ungrouped.append([cam])
    return list(groups.values()) + ungrouped


def scan_cameras() -> list[list[dict]]:
    """Return cameras grouped by physical device (serial or bus_id).

    On Linux: scans /dev/video* and reads the device name from sysfs.
    On macOS: uses system_profiler SPCameraDataType.
    """
    if sys.platform == "linux":
        return _group_cameras(_scan_linux())
    if sys.platform == "darwin":
        return _group_cameras(_scan_macos())
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
            entry["usb"] = {"vendor_id": vendor_id, "product_id": product_id, **usb}

        cameras.append(entry)
    return cameras


def _parse_macos_model_id(model_id: str) -> tuple[str, str]:
    """Parse 'UVC Camera VendorID_1133 ProductID_2085' → ('046d', '0825')."""
    import re

    vendor = product = ""
    if m := re.search(r"VendorID_(\d+)", model_id):
        vendor = f"{int(m.group(1)):04x}"
    if m := re.search(r"ProductID_(\d+)", model_id):
        product = f"{int(m.group(1)):04x}"
    return vendor, product


def _scan_macos() -> list[dict]:
    try:
        result = subprocess.run(
            ["system_profiler", "SPCameraDataType", "-json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        data = json.loads(result.stdout)
        cameras = []
        for cam in data.get("SPCameraDataType", []):
            entry: dict = {"name": cam.get("_name", "Unknown")}

            vendor_id, product_id = "", ""
            if model_id := cam.get("spcamera_model-id"):
                vendor_id, product_id = _parse_macos_model_id(model_id)

            entry["type"] = _identify_type(vendor_id, product_id)

            usb: dict = {}
            if vendor_id:
                usb["vendor_id"] = vendor_id
            if product_id:
                usb["product_id"] = product_id
            if uid := cam.get("spcamera_unique-id"):
                usb["serial"] = uid
            if usb:
                entry["usb"] = usb

            cameras.append(entry)
        return cameras
    except Exception:
        return []
