"""Runtime-side path constants and config access."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

CONFIG_DIR = Path(os.environ.get("PSILIA_CONFIG_DIR", "/etc/psilia"))
RUN_DIR = Path(os.environ.get("PSILIA_RUN_DIR", "/run/psilia"))
LOG_DIR = Path(os.environ.get("PSILIA_LOG_DIR", "/var/log/psilia"))

RUNTIME_CONFIG_PATH = CONFIG_DIR / "runtime_config.yaml"


def read_runtime_config() -> dict:
    """Read runtime_config.yaml, returning {} if missing or unreadable."""
    if not RUNTIME_CONFIG_PATH.exists():
        return {}
    try:
        return yaml.safe_load(RUNTIME_CONFIG_PATH.read_text()) or {}
    except yaml.YAMLError:
        return {}


def write_runtime_config(config: dict) -> None:
    """Write config dict to runtime_config.yaml (requires sudo for /etc/psilia/)."""
    RUNTIME_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    RUNTIME_CONFIG_PATH.write_text(yaml.dump(config, default_flow_style=False))


def get_base_dir() -> Path:
    """Return the base install directory on the SSD (e.g. /ssd/psilia)."""
    return Path(read_runtime_config()["runtime"]["base_dir"])


def get_ros_dir() -> Path:
    """Return the colcon workspace directory, mounted into Docker at runtime (e.g. /ssd/psilia/ros)."""
    return Path(read_runtime_config()["runtime"]["ros_dir"])


def get_data_dir() -> Path:
    """Return the data directory where MCAP recordings are stored (e.g. /ssd/psilia/data)."""
    return Path(read_runtime_config()["runtime"]["data_dir"])
