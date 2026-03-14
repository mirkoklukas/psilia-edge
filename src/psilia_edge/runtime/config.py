"""Path constants and config access for the psilia tooling."""

from __future__ import annotations

import importlib.resources
import os
from pathlib import Path

import yaml

from psilia_edge.utils import NestedDict

# Default runtime config shipped with the package.
INITIAL_RUNTIME_CONFIG_PATH = (
    importlib.resources.files("psilia_edge.runtime") / "runtime.default.yaml"
)

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

DEFAULT_RUNTIME_CONFIG_NAME = "runtime.yaml"

# These are the subdirs of the runtime home that we create and manage.
# The repo dir is not included here since it's not necessarily a subdir of the runtime home.
RUNTIME_DIRS = ["ros", "data", "log", "conf"]


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


def get_docker_dir() -> Path:
    return get_repo_dir() / "ros" / "docker"


def get_data_dir() -> Path:
    """Return the data directory where MCAP recordings are stored."""
    return get_runtime_home() / "data"


def get_log_dir() -> Path:
    """Return the data directory where MCAP recordings are stored."""
    return get_runtime_home() / "log"


def get_repo_dir() -> Path:
    """Return the repository root directory, derived from the installed package location.

    Assumes `pip install -e .` (editable install) — always the case for v0.
    TODO: This breaks for a non-editable PyPI install. Before publishing, anything
    sourced from the repo dir (e.g. web assets) must move to package data via
    `importlib.resources`.
    """
    return Path(__file__).resolve().parents[3]


def get_docker_image() -> str | None:
    """Return the name of the Docker image to use for the runtime container or None."""
    return read_config().get("runtime", {}).get("image", DEFAULT_DOCKER_IMAGE)


def set_runtime_config_path(path: str) -> None:
    """Set the path to the runtime config file in the main config."""
    config = read_config()
    config["runtime"]["config_path"] = path.expanduser()
    write_config(config)


def get_runtime_config_path() -> Path:
    # TODO: We could make an env var for the runtime config path and return it here if set.
    # `if (p := os.environ.get("PSILIA_RUNTIME_CONFIG_PATH")): return Path(p).expanduser()`
    value = read_config().get("runtime", {}).get("config_path", None)
    if value:
        rt_config_path = Path(value).expanduser()
    else:
        # Try the default location in the runtime home directory if not set in config.
        rt_config_path = get_runtime_home() / DEFAULT_RUNTIME_CONFIG_NAME

    if not rt_config_path.exists():
        raise RuntimeError(
            f"Runtime config file `{rt_config_path}` not found. "
            f"Check runtime path in `{CONFIG_PATH}` and/or your runtime home `{get_runtime_home()}`."
        )
    return rt_config_path


def read_runtime_config(config_path: Path | None = None) -> NestedDict:
    if config_path is not None:
        rt_config_path = config_path.expanduser()
    else:
        rt_config_path = get_runtime_config_path()

    if not rt_config_path.exists():
        raise RuntimeError(
            f"Runtime config file `{rt_config_path}` not found. Run `psilia runtime configure` first."
        )
    try:
        return NestedDict(yaml.safe_load(rt_config_path.read_text()) or {})
    except yaml.YAMLError as e:
        raise RuntimeError(f"Error parsing runtime config: {e}") from e


def write_runtime_config(
    config: dict | NestedDict, config_path: Path | None = None
) -> None:
    if config_path is not None:
        rt_config_path = config_path.expanduser()
    else:
        rt_config_path = get_runtime_config_path()
    rt_config_path.write_text(yaml.dump(dict(**config), default_flow_style=False))


def get_launch_script() -> Path:
    """Return the path to the runtime launch script inside the repo."""
    rt_config = read_runtime_config()
    launch_script = rt_config.get("ros", {}).get("launch", "default.launch.py")
    return launch_script
