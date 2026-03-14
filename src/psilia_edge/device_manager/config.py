"""Device manager config helpers — device registry and laptop-side paths."""

from __future__ import annotations

from pathlib import Path

from psilia_edge.runtime.config import CONFIG_DIR, read_config, write_config

KEYS_DIR = CONFIG_DIR / "keys"
DATA_DIR = Path.home() / "psilia-data"


def register_device(name: str, host: str, user: str, key_path: Path) -> None:
    """Write minimal device entry (connection info only — no data_path/camera/hotspot yet).

    Merges into existing config without overwriting other devices or defaults.
    """
    config = read_config()
    config.setdefault("registered_devices", {})[name] = {
        "host": host,
        "user": user,
        "key": str(key_path),
        "hotspot_ip": None,
    }
    config.setdefault("defaults", {}).setdefault(
        "pull_to", str(Path.home() / "psilia-data")
    )
    write_config(config)
