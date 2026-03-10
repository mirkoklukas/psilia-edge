"""Laptop-side config management for psilia-edge."""

from __future__ import annotations

from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".psilia" / "config.yaml"
KEYS_DIR = Path.home() / ".psilia" / "keys"
DATA_DIR = Path.home() / "psilia-data"


def read_config() -> dict:
    """Read ~/.psilia/config.yaml, returning {} if missing or unreadable."""
    if not CONFIG_PATH.exists():
        return {}
    try:
        return yaml.safe_load(CONFIG_PATH.read_text()) or {}
    except yaml.YAMLError:
        return {}


def write_config(config: dict) -> None:
    """Write config dict to ~/.psilia/config.yaml."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.dump(config, default_flow_style=False))


def register_device(name: str, host: str, user: str, key_path: Path) -> None:
    """Write minimal device entry (connection info only — no data_path/camera/hotspot yet).

    Merges into existing config without overwriting other devices or defaults.
    """
    config = read_config()
    config.setdefault("devices", {})[name] = {
        "host": host,
        "user": user,
        "key": str(key_path),
    }
    config.setdefault("defaults", {}).setdefault(
        "pull_to", str(Path.home() / "psilia-data")
    )
    write_config(config)
