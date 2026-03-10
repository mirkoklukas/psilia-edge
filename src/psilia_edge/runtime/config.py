"""Runtime-side path constants and config access."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from psilia_edge.utils import NestedDict

# System directories
CONFIG_DIR = Path(os.environ.get("PSILIA_CONFIG_DIR", "/etc/psilia"))
RUN_DIR = Path(os.environ.get("PSILIA_RUN_DIR", "/run/psilia"))
LOG_DIR = Path(os.environ.get("PSILIA_LOG_DIR", "/var/log/psilia"))

# Base directory for installs, ROS workspace, data, and repo.
# Set by bootstrap.sh and read from device_config.yaml at runtime.
DEFAULT_BASE_DIR = Path(os.environ.get("PSILIA_DEFAULT_BASE_DIR", "/ssd/psilia"))


DEVICE_CONFIG_PATH = CONFIG_DIR / "device_config.yaml"


def read_device_config() -> NestedDict:
    """Read device_config.yaml, returning {} if missing or unreadable."""
    if not DEVICE_CONFIG_PATH.exists():
        return NestedDict()
    try:
        return NestedDict(yaml.safe_load(DEVICE_CONFIG_PATH.read_text()) or {})
    except yaml.YAMLError:
        return NestedDict()


def write_device_config(config: dict | NestedDict) -> None:
    """Write config dict to device_config.yaml (requires sudo for /etc/psilia/)."""
    DEVICE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    DEVICE_CONFIG_PATH.write_text(yaml.dump(dict(**config), default_flow_style=False))


# TODO: get_base_dir shouldn't really be used, we can directly call get_ros_dir, get_data_dir, get_repo_dir which read from the config.
#   But for now we can keep it for backwards compatibility with some of the setup code that still references base_dir.
def get_base_dir() -> Path:
    """Return the base install directory on the SSD (e.g. /ssd/psilia)."""
    return Path(read_device_config()["runtime"]["base_dir"])


def get_ros_dir() -> Path:
    """Return the colcon workspace directory, mounted into Docker at runtime (e.g. /ssd/psilia/ros)."""
    return Path(read_device_config()["runtime"]["ros_dir"])


def get_data_dir() -> Path:
    """Return the data directory where MCAP recordings are stored (e.g. /ssd/psilia/data)."""
    return Path(read_device_config()["runtime"]["data_dir"])


def get_repo_dir() -> Path:
    """Return the repository directory (e.g. /ssd/psilia/psilia-edge)."""
    return Path(read_device_config()["runtime"]["repo_dir"])


def get_docker_image() -> str | None:
    """Return the name of the Docker image to use for the runtime container or None."""
    return read_device_config().get("runtime", {}).get("image", None)
