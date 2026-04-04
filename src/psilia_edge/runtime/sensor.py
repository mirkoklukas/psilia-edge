"""Sensor registration and calibration management.

Manages the `sensors:` section in `psilia.yaml` and calibration files
in `~/.psilia/calibrations/`.

A sensor entry is keyed by either a human-friendly label or a UID
(vendor_id:product_id:serial). Both are treated the same way.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from psilia_edge.runtime.config import CALIBRATIONS_DIR, read_config, write_config


def build_sensor_id(usb_info: dict) -> str:
    """Build a sensor UID from USB descriptor fields.

    Returns a string like '2b03:0b3a:SN123456'. If serial is missing,
    the trailing field is empty (e.g. '2b03:0b3a:').
    """
    vendor = usb_info.get("vendor_id", "")
    product = usb_info.get("product_id", "")
    serial = usb_info.get("serial", "")
    return f"{vendor}:{product}:{serial}"


def _sanitize(s: str) -> str:
    """Replace characters that are problematic in filenames."""
    return s.replace(":", "-").replace(" ", "-").replace("/", "-")


def _calibration_filename(label: str, uid: str | None, ext: str) -> str:
    """Build a calibration filename from label and optional UID.

    Examples:
        ("ZED 2i", "2b03:0b3a:SN123456", ".yaml") → "ZED-2i__2b03-0b3a-SN123456.yaml"
        ("ZED 2i", None, ".yaml")                   → "ZED-2i.yaml"
    """
    name = _sanitize(label)
    if uid:
        name = f"{name}__{_sanitize(uid)}"
    return f"{name}{ext}"


def register_sensor(
    key: str,
    entry: dict,
    calibration_src: Path,
) -> None:
    """Register a sensor: copy calibration file and write entry to psilia.yaml.

    Args:
        key: The sensor key (label or UID).
        entry: Sensor metadata (type, manufacturer, product, label, etc.).
        calibration_src: Path to the calibration file to import.
    """
    CALIBRATIONS_DIR.mkdir(parents=True, exist_ok=True)

    label = entry.get("label", key)
    uid = key if key != label else None
    cal_name = _calibration_filename(label, uid, calibration_src.suffix)

    calibration_dst = CALIBRATIONS_DIR / cal_name
    shutil.copy2(calibration_src, calibration_dst)

    entry["calibration"] = cal_name

    config = read_config()
    if "sensors" not in config:
        config["sensors"] = {}
    config["sensors"][key] = entry
    write_config(config)


def list_sensors() -> dict:
    """Return the sensors dict from psilia.yaml."""
    return read_config().get("sensors", {})


def remove_sensor(key: str, delete_calibration: bool = False) -> None:
    """Remove a sensor entry from psilia.yaml.

    Args:
        key: The sensor key to remove.
        delete_calibration: If True, also delete the calibration file.

    Raises:
        KeyError: If the sensor key is not found.
    """
    config = read_config()
    sensors = config.get("sensors", {})
    if key not in sensors:
        raise KeyError(f"Sensor '{key}' not found.")

    if delete_calibration:
        cal_name = sensors[key].get("calibration")
        if cal_name:
            cal_path = CALIBRATIONS_DIR / cal_name
            if cal_path.exists():
                cal_path.unlink()

    del sensors[key]
    config["sensors"] = sensors
    write_config(config)


def push_sensors(device: str, keys: list[str] | None = None) -> list[str]:
    """Push sensor entries and calibration files to a remote device.

    Args:
        device: Registered device name (SSH host alias).
        keys: Specific sensor keys to push. If None, pushes all.

    Returns:
        List of keys that were pushed.

    Raises:
        KeyError: If a requested key is not found locally.
    """
    import json as _json
    from psilia_edge.utils import run_on_device_capture, run_streamed

    sensors = list_sensors()
    if keys is None:
        keys = list(sensors.keys())

    # Validate all keys exist locally.
    for key in keys:
        if key not in sensors:
            raise KeyError(f"Sensor '{key}' not found locally.")

    to_push = {key: sensors[key] for key in keys}

    # 1. rsync calibration files
    cal_files = []
    for entry in to_push.values():
        cal_name = entry.get("calibration")
        if cal_name:
            cal_path = CALIBRATIONS_DIR / cal_name
            if cal_path.exists():
                cal_files.append(cal_path)

    if cal_files:
        # Ensure remote calibrations dir exists.
        run_on_device_capture(device, "mkdir -p ~/.psilia/calibrations")
        file_args = " ".join(str(f) for f in cal_files)
        rc = run_streamed(
            f"rsync --archive --progress --human-readable "
            f"{file_args} {device}:~/.psilia/calibrations/"
        )
        if rc != 0:
            raise RuntimeError(f"Failed to rsync calibration files to {device}")

    # 2. Merge sensor entries into remote psilia.yaml.
    #    Base64-encode the JSON to avoid shell quoting issues.
    import base64

    sensors_json = _json.dumps(to_push)
    b64 = base64.b64encode(sensors_json.encode()).decode()
    merge_script = (
        'python3 -c "'
        "import json, base64; "
        "from psilia_edge.runtime.config import read_config, write_config; "
        "c = read_config(); "
        "c.setdefault('sensors', {}); "
        f"c['sensors'].update(json.loads(base64.b64decode('{b64}').decode())); "
        "write_config(c)"
        '"'
    )
    rc, _, stderr = run_on_device_capture(device, merge_script)
    if rc != 0:
        raise RuntimeError(f"Failed to merge sensor entries on {device}: {stderr}")

    return keys


def find_sensor(name: str) -> tuple[str, dict] | None:
    """Find a sensor by key or label.

    Tries direct key match first, then searches label fields.
    Returns (key, entry) or None if not found.
    """
    sensors = list_sensors()
    # Direct key match.
    if name in sensors:
        return name, sensors[name]
    # Search by label.
    for key, entry in sensors.items():
        if entry.get("label") == name:
            return key, entry
    return None


def get_calibration_file(*names: str) -> Path | None:
    """Try each name (UID or label), return the first matching calibration path.

    Iterates through the given names, looks up each in the sensor registry
    (by key first, then by label), and returns the calibration file path
    for the first match that has one. Returns None if no match is found.

    TODO: Support explicit file paths (e.g. from runtime.yaml camera.calibration)
    as a bypass that skips the sensor registry lookup.
    """
    for name in names:
        if not name:
            continue
        result = find_sensor(name)
        if result:
            _, entry = result
            cal_name = entry.get("calibration")
            if cal_name:
                return CALIBRATIONS_DIR / cal_name
    return None
