"""Path constants and config access for the psilia tooling."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from psilia_edge.utils import NestedDict

# Hidden CLI-internal directory — ~/.psilia/ on any machine.
CONFIG_DIR = Path(os.environ.get("PSILIA_DIR", "~/.psilia")).expanduser()

RUN_DIR = Path(os.environ.get("PSILIA_RUN_DIR", "~/.psilia/run")).expanduser()
LOG_DIR = Path(os.environ.get("PSILIA_LOG_DIR", "~/.psilia/log")).expanduser()

# Unified config file — ~/.psilia/psilia.yaml
CONFIG_PATH = CONFIG_DIR / "psilia.yaml"

# Default runtime home — user-facing directory where the runtime lives.
# TODO: Not sure why we need a env var for this.
DEFAULT_RUNTIME_HOME = Path(
    os.environ.get("PSILIA_DEFAULT_RUNTIME_HOME", "~/psilia-runtime-home")
).expanduser()

CONTAINER_NAME = "psilia-runtime"
DEFAULT_DOCKER_IMAGE = "psilia/runtime:latest"

# These are the subdirs of the runtime home that we create and manage.
# The repo dir is not included here since it's not necessarily a subdir of the runtime home.
RUNTIME_DIRS = ["ros", "data", "log"]


# TODO: Should we raise an error if the config file doesn't exist?
def read_config() -> NestedDict:
    """Read ~/.psilia/psilia.yaml, returning {} if missing or unreadable."""
    if not CONFIG_PATH.exists():
        return NestedDict()
    try:
        return NestedDict(yaml.safe_load(CONFIG_PATH.read_text()) or {})
    except yaml.YAMLError:
        return NestedDict()


def write_config(config: dict | NestedDict) -> None:
    """Write config dict to ~/.psilia/psilia.yaml."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.dump(dict(**config), default_flow_style=False))


def get_runtime_home() -> Path:
    """Return the runtime home directory from config.

    Raises RuntimeError if not set — run `psilia runtime setup` first.
    """
    value = read_config().get("runtime", {}).get("home_path")
    if not value:
        raise RuntimeError(
            "No runtime home configured. Run `psilia runtime setup` first."
        )
    return Path(value).expanduser()


def get_ros_dir() -> Path:
    """Return the colcon workspace directory (e.g. ~/psilia-runtime-home/ros)."""
    return get_runtime_home() / "ros"


def get_data_dir() -> Path:
    """Return the data directory where MCAP recordings are stored."""
    return get_runtime_home() / "data"


def get_repo_dir() -> Path:
    """Return the repository root directory, derived from the installed package location.

    Assumes `pip install -e .` (editable install) — always the case for v0.
    """
    return Path(__file__).resolve().parents[3]


def get_docker_image() -> str | None:
    """Return the name of the Docker image to use for the runtime container or None."""
    return read_config().get("runtime", {}).get("image", DEFAULT_DOCKER_IMAGE)
