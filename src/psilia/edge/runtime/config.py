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


from psilia.edge.utils import NestedDict, read_yaml, write_yaml


class ConfigurationError(Exception):
    """Raised when psilia configuration is missing or invalid."""


#
# -- "System-level directories" --
#
# Hidden CLI-internal directory — ~/.psilia/ on any machine and
# Unified config file — ~/.psilia/psilia.yaml
CONFIG_DIR = Path(os.environ.get("PSILIA_DIR", "~/.psilia")).expanduser()
CONFIG_PATH = CONFIG_DIR / "psilia.yaml"
RUN_DIR = CONFIG_DIR / "run"
LOG_DIR = CONFIG_DIR / "log"
CALIBRATIONS_DIR = CONFIG_DIR / "calibrations"
INITIAL_CONFIG_PATH = (
    importlib.resources.files("psilia.edge.runtime") / "psilia.initial.yaml"
)

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
    importlib.resources.files("psilia.edge.runtime") / "runtime.initial.yaml"
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


def read_config(missing_ok: bool = True) -> NestedDict:
    """Read ~/.psilia/psilia.yaml.

    If missing_ok is True (default), returns {} when the file doesn't exist.
    If missing_ok is False, raises FileNotFoundError.
    """
    if not CONFIG_PATH.exists():
        if missing_ok:
            return initial_config()
        raise ConfigurationError(f"Config file not found: {CONFIG_PATH}")
    return NestedDict(read_yaml(CONFIG_PATH))


def write_config(config: dict | NestedDict) -> None:
    """Write config dict to ~/.psilia/psilia.yaml."""
    write_yaml(CONFIG_PATH, config, parents=True)


def initial_config() -> NestedDict:
    """Return the initial psilia config as a dict."""
    return NestedDict(read_yaml(INITIAL_CONFIG_PATH))


def get_api_port() -> int:
    return read_config().get("runtime", {}).get("api_port", 8080)


def get_rosbridge_port() -> int:
    return read_config().get("runtime", {}).get("rosbridge_port", 9090)


def get_runtime_home() -> Path:
    """Return the runtime home directory from config.

    Raises RuntimeError if not set — run `psilia runtime setup` first.
    """
    value = read_config(missing_ok=False).get("runtime", {}).get("home_path")
    if not value:
        raise ConfigurationError("No runtime home configured in the main config.")
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


def get_runtime_config_path(missing_ok: bool = False) -> Path:
    # TODO: We could make an env var for the runtime config path and return it here if set.
    # `if (p := os.environ.get("PSILIA_RUNTIME_CONFIG_PATH")): return Path(p).expanduser()`

    # home is required!
    rt_config_path = get_runtime_home() / DEFAULT_RUNTIME_CONFIG_NAME

    if rt_config_path.exists() or missing_ok:
        return rt_config_path

    raise ConfigurationError(f"Runtime config file `{rt_config_path}` not found. ")


def read_runtime_config(missing_ok: bool = True) -> NestedDict:
    """Read the runtime config file (runtime.yaml).

    If missing_ok is True (default), returns an initial runtime config when the file doesn't exist.
    If missing_ok is False, and the runtime.yaml file doesn't exist, raises FileNotFoundError.
    """

    rt_config_path = get_runtime_config_path(missing_ok=missing_ok)
    if not rt_config_path.exists():
        if missing_ok:
            return initial_runime_config()
        raise ConfigurationError(f"Runtime config file not found: {rt_config_path}")

    return NestedDict(read_yaml(rt_config_path))


def initial_runime_config() -> NestedDict:
    """Return the initial runtime config as a dict."""
    return NestedDict(read_yaml(INITIAL_RUNTIME_CONFIG_PATH))


def write_runtime_config(
    runtime_config: dict | NestedDict, missing_ok: bool = True
) -> None:
    rt_config_path = get_runtime_config_path(missing_ok=missing_ok)
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


def get_dockerfile() -> Path:
    """Return the Dockerfile path for the current platform.

    TODO: Improve platform detection — currently uses a simple arch check.
    Could use /etc/nv_tegra_release, a config option, or both.
    """
    import platform

    docker_dir = get_docker_dir()
    if platform.machine() == "aarch64":
        return docker_dir / "Dockerfile.jetson"
    return docker_dir / "Dockerfile.laptop"


def get_docker_image() -> str:
    """Return the name of the Docker image to use for the runtime container."""
    return read_runtime_config().get("docker", {}).get("image", DEFAULT_DOCKER_IMAGE)


def _check_paths(path_dict) -> None:
    """Check that all important paths exist and are directories.

    Raises FileNotFoundError if any path is missing or not a directory.
    """
    import psilia.edge.ui as ui

    for name, path in path_dict.items():
        if callable(path):
            name = f"{name} = [not bold]{path.__name__}()[/not bold]"
            try:
                path = path()
            except ConfigurationError as e:
                ui.fail(f"[red]{name}[/red]: [dim]{e}[/dim]")
                continue
        if path.exists():
            ui.ok(f"[green]{name}[/green]: [dim]{path}[/dim]")
        else:
            ui.fail(f"[red]{name}[/red]: [dim]{path}[/dim]")


def _check_config() -> None:
    import psilia.edge.ui as ui

    _check_paths(
        {
            "repo_dir": get_repo_dir,
            "docker_dir": get_docker_dir,
            "config_dir": CONFIG_DIR,
            "system_run_dir": RUN_DIR,
            "system_log_dir": LOG_DIR,
            "main_config": CONFIG_PATH,
            "home_dir": get_runtime_home,
            "ros_dir": get_ros_dir,
            "data_dir": get_data_dir,
            "log_dir": get_log_dir,
            "runtime_config": get_runtime_config_path,
        }
    )

    try:
        ui.print_tree(
            read_config(missing_ok=True), label="read_config(missing_ok=True)"
        )
    except ConfigurationError:
        pass
    try:
        ui.print_tree(
            read_runtime_config(missing_ok=True),
            label="read_runtime_config(missing_ok=True)",
        )
    except ConfigurationError:
        pass
