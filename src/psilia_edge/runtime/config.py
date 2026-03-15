"""Path constants and config access for the psilia tooling.


Rough dependency structure:


    psilia.yaml
        ├──> Device & Data Management (Non-host specific)
        └──> Runtime home (user-specified)
                ├──> Runtime subdirs (ros/, data/, log/, conf/)
                └──> runtime.yaml (runtime config, generated from default and user overrides)

    psilia-edge repository (read-only, derived from package location)
        ├──> Dockerfile and related files (e.g. entrypoint.sh)
        └──> Web assets
"""

from __future__ import annotations

import importlib.resources
import os
from pathlib import Path


from psilia_edge.utils import NestedDict, read_yaml, write_yaml

#
# -- "System-level directories" --
#
# Hidden CLI-internal directory — ~/.psilia/ on any machine and
# Unified config file — ~/.psilia/psilia.yaml
CONFIG_DIR = Path(os.environ.get("PSILIA_DIR", "~/.psilia")).expanduser()
CONFIG_PATH = CONFIG_DIR / "psilia.yaml"
RUN_DIR = Path(os.environ.get("PSILIA_RUN_DIR", "~/.psilia/run")).expanduser()
LOG_DIR = Path(os.environ.get("PSILIA_LOG_DIR", "~/.psilia/log")).expanduser()

#
# -- "Runtime-level directories" --
#
# These are the subdirs of the runtime home that we create and manage.
# The repo dir is not included here since it's not necessarily a subdir of the runtime home.
# The runtime home is set by the user during init and is
# where all runtime-related files go — ROS workspace, data, logs, and runtime config.
RUNTIME_DIRS = ["ros", "data", "log", "conf"]
# Runtime config file name inside the runtime home.
# The full path is stored in the main config.
DEFAULT_RUNTIME_CONFIG_NAME = "runtime.yaml"
# Default runtime config shipped with the package.
INITIAL_RUNTIME_CONFIG_PATH = (
    importlib.resources.files("psilia_edge.runtime") / "runtime.initial.yaml"
)

#
# -- Docker-related constants --
#
CONTAINER_NAME = "psilia-runtime"
DEFAULT_DOCKER_IMAGE = "psilia/runtime:latest"


# TODO: Check dependency structure. We should make explicit who reads from what,
#   who has default fall-back values, and who overwrites these values.
#   For example, we're tryint to read the docker image from the runtime config, but
#   fall back to the default image if it's not set.
# TODO: all getter that read the config, explicitly or explicitly,
#   should have an optional config argument. If provided they should read from that
#   instead of the default config path. E.g. `get_ros_dir(config: NestedDict | None = None)`,
#   `get_runtime_home(config: NestedDict | None = None)`, etc. Note that in the
#   example above `get_ros_dir` should then hand down the config to `get_runtime_home`.
# TODO: We need validators for the configs.


# TODO: Should we raise an error if the config file doesn't exist?
def read_config() -> NestedDict:
    """Read ~/.psilia/psilia.yaml, returning {} if missing or unreadable."""
    if not CONFIG_PATH.exists():
        return NestedDict()
    else:
        return NestedDict(read_yaml(CONFIG_PATH))


def write_config(config: dict | NestedDict) -> None:
    """Write config dict to ~/.psilia/psilia.yaml."""
    write_yaml(CONFIG_PATH, config, parents=True)


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


def get_log_dir() -> Path:
    """Return the data directory where MCAP recordings are stored."""
    return get_runtime_home() / "log"


def set_runtime_config_path(path: str) -> None:
    """Set the path to the runtime config file in the main config."""
    config = read_config()
    if "runtime" not in config:
        config["runtime"] = {}
    config["runtime"]["config_path"] = path.expanduser()
    write_config(config)


def get_runtime_config_path() -> Path:
    # TODO: We could make an env var for the runtime config path and return it here if set.
    # `if (p := os.environ.get("PSILIA_RUNTIME_CONFIG_PATH")): return Path(p).expanduser()`
    value = read_config().get("runtime", {}).get("config_path", None)
    if value:
        # If path is set, great. Use it.
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


def read_runtime_config() -> NestedDict:
    rt_config_path = get_runtime_config_path()
    if not rt_config_path.exists():
        return NestedDict(read_yaml(INITIAL_RUNTIME_CONFIG_PATH))
    else:
        return NestedDict(read_yaml(rt_config_path))


def write_runtime_config(runtime_config: dict | NestedDict) -> None:
    rt_config_path = get_runtime_config_path()
    write_yaml(rt_config_path, runtime_config, parents=True)


def get_launch_script() -> Path:
    """Return the path to the runtime launch script inside the repo."""
    rt_config = read_runtime_config()
    launch_script = rt_config.get("ros", {}).get("launch", "default.launch.py")
    return launch_script


def get_repo_dir() -> Path:
    """Return the repository root directory, derived from the installed package location.

    Assumes `pip install -e .` (editable install) — always the case for v0.
    TODO: This breaks for a non-editable PyPI install. Before publishing, anything
    sourced from the repo dir (e.g. web assets) must move to package data via
    `importlib.resources`.
    """
    return Path(__file__).resolve().parents[3]


def get_docker_dir() -> Path:
    return get_repo_dir() / "ros" / "docker"


def get_docker_image() -> str:
    """Return the name of the Docker image to use for the runtime container."""
    return read_runtime_config().get("docker", {}).get("image", DEFAULT_DOCKER_IMAGE)
