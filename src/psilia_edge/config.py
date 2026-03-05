"""Laptop-side config management for psilia-edge."""

from __future__ import annotations

from pathlib import Path

import yaml

LAPTOP_CONFIG_PATH = Path.home() / ".psilia" / "config.yaml"


def read_laptop_config() -> dict:
    """Read ~/.psilia/config.yaml, returning {} if missing or unreadable."""
    if not LAPTOP_CONFIG_PATH.exists():
        return {}
    try:
        return yaml.safe_load(LAPTOP_CONFIG_PATH.read_text()) or {}
    except yaml.YAMLError:
        return {}


def write_laptop_config(config: dict) -> None:
    """Write config dict to ~/.psilia/config.yaml."""
    LAPTOP_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAPTOP_CONFIG_PATH.write_text(yaml.dump(config, default_flow_style=False))


def register_device(name: str, host: str, user: str, key_path: Path) -> None:
    """Write minimal device entry (connection info only — no data_path/camera/hotspot yet).

    Merges into existing config without overwriting other devices or defaults.
    """
    config = read_laptop_config()
    config.setdefault("devices", {})[name] = {
        "host": host,
        "user": user,
        "key": str(key_path),
    }
    config.setdefault("defaults", {}).setdefault(
        "pull_to", str(Path.home() / "psilia-data")
    )
    write_laptop_config(config)


def sync_device_config(device: str, conn) -> None:
    """Read /opt/psilia/config.yaml from Jetson and merge relevant fields into laptop config.

    Merges: data_path, hotspot.ssid, camera.type.
    conn must implement .run(cmd) -> (rc, stdout, stderr).
    """
    rc, out, _ = conn.run("cat /opt/psilia/config.yaml")
    if rc != 0:
        return
    try:
        jetson_cfg = yaml.safe_load(out) or {}
    except yaml.YAMLError:
        return

    config = read_laptop_config()
    dev = config.setdefault("devices", {}).setdefault(device, {})

    storage = jetson_cfg.get("storage", {})
    if data_path := storage.get("data_path"):
        # data_path in Jetson config is /ssd/psilia/data/ — recordings live one level deeper
        dev["data_path"] = data_path.rstrip("/") + "/recordings"

    hotspot = jetson_cfg.get("hotspot", {})
    if ssid := hotspot.get("ssid"):
        dev["hotspot_ssid"] = ssid
    if password := hotspot.get("password"):
        dev["hotspot_password"] = password

    camera = jetson_cfg.get("camera", {})
    dev["camera"] = camera.get("type")

    write_laptop_config(config)
