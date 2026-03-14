"""Hotplug — USB camera detection.

Currently uses an active scan. Future: replace with a pyudev MonitorObserver
for event-driven detection without polling.

Usage:
    devices = scan_cameras()
    # [{"device": "/dev/video0", "name": "..."}, ...]
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def scan_cameras() -> list[dict]:
    """Return a list of detected camera devices.

    On Linux: scans /dev/video* and reads the device name from sysfs.
    On macOS: uses system_profiler SPCameraDataType.
    """
    if sys.platform == "linux":
        return _scan_linux()
    if sys.platform == "darwin":
        return _scan_macos()
    return []


def _scan_linux() -> list[dict]:
    cameras = []
    for dev in sorted(Path("/dev").glob("video*")):
        entry: dict = {"device": str(dev)}
        name_file = Path(f"/sys/class/video4linux/{dev.name}/name")
        if name_file.exists():
            entry["name"] = name_file.read_text().strip()
        cameras.append(entry)
    return cameras


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
            if uid := cam.get("spcamera_unique-id"):
                entry["uid"] = uid
            if model := cam.get("spcamera_model-id"):
                entry["model"] = model
            cameras.append(entry)
        return cameras
    except Exception:
        return []
