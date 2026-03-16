"""CLI presentation layer for runtime commands.

Calls core functions and displays results. No logic lives here.

Naming convention:
  function   — acts as a CLI command (owns output and side effects,
               called directly from cli.py command handlers)
  _function  — helper (returns a value or renderable, no direct output)

TODO: Define a typer sub-app here (e.g. `app = typer.Typer(...)`) with
      base/spatial start/stop commands, then import and mount it in cli.py
      via `app.add_typer(runtime_app, name="runtime")` or similar.

TODO: Add a --dev flag (default from env var PSILIA_DEV=1) for dev mode.
      In dev mode, commands like `update` and `start` could:
        - sync the ROS workspace from the repo into the dev install path
        - skip or bypass Docker image rebuild (use local build)
        - optionally rebuild the Docker image from the local Dockerfile
      This would allow running `psilia runtime start --dev` to pick up local
      node changes without a full bootstrap cycle.
"""

from __future__ import annotations
from typing import Optional, Annotated
import functools
import inspect
from pathlib import Path

import typer

from psilia_edge import ui
from psilia_edge.runtime.config import _check_config


app = typer.Typer(help="Psilia Edge — spatial perception runtime for edge devices")


def device_decorator(func):
    """Decorator to run a command on a registered device if given a device name."""
    device_param = inspect.Parameter(
        "device",
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        default=typer.Argument(None, help="Registered device name (SSH wrapper)"),
        annotation=Optional[str],
    )
    orig_params = list(inspect.signature(func).parameters.values())
    new_sig = inspect.signature(func).replace(parameters=[device_param] + orig_params)

    @functools.wraps(func)
    def wrapper(device, *args, **kwargs):
        from psilia_edge.runtime.core import require_runtime_host
        from psilia_edge.utils import run_on_device

        if device is not None:
            run_on_device(device, f"psilia runtime {func.__name__}")
            return
        else:
            require_runtime_host(f"{func.__name__} <device>")
            return func(*args, **kwargs)

    wrapper.__signature__ = new_sig
    return wrapper


@app.command()
def init(
    runtime_home: Annotated[
        Path, typer.Argument(help="The path to the runtime home directory.")
    ] = Path("./"),
    mkdir: Annotated[
        bool,
        typer.Option(
            "--mkdir",
            "-m",
            help="Create the runtime home directory if it doesn't exist.",
        ),
    ] = False,
) -> None:
    """Initializes a runtime home directory."""
    from psilia_edge.runtime.setup import run_runtime_init

    if not runtime_home.exists() and not mkdir:
        ui.error(
            f"Runtime home directory '{runtime_home}' does not exist."
            f"Run with --mkdir (-m) to create it."
        )
        raise typer.Exit(1)

    ui.banner_nav(
        ["Runtime", "Initialize"], "Initializing the runtime home directory ..."
    )
    run_runtime_init(runtime_home or Path.cwd(), mkdir=mkdir)


@app.command(hidden=True)
@device_decorator
def setup(
    # home: Optional[Path] = typer.Option(None, "--home", "-h", help="The path to the runtime home directory."),
    # mkdir: bool = typer.Option(True, "--mkdir", "-m", help="Whether to create the runtime home directory if it doesn't exist."),
    init: bool = typer.Option(
        False,
        "--init/--skip-init",
        "-i",
        help="Whether to initialize the runtime home directory",
    ),
    network: bool = typer.Option(
        False, "--network/--no-network", "-n", help="Run AP hotspot setup"
    ),
    wifi: bool = typer.Option(
        False, "--wifi/--no-wifi", "-w", help="Run WiFi client setup"
    ),
    run_all: bool = typer.Option(
        False, "--all/--none", "-a", help="Run all setup steps (init, network, wifi)."
    ),
) -> None:
    """Pull latest psilia-edge and rebuild the Docker image."""
    from psilia_edge.runtime.config import get_runtime_home
    from psilia_edge.runtime.setup import (
        run_runtime_init,
        run_network_setup,
        run_wifi_setup,
    )

    ui.banner_nav(["Runtime", "Setup"], "Setting up a runtime ...")
    if init or run_all:
        home = ui.ask("Runtime home directory")
        run_runtime_init(home, mkdir=True)
    else:
        home = get_runtime_home()
        ui.info(f"Skipping runtime home initialization. Using: \{home}")

    if network or run_all:
        run_network_setup()
    if wifi or run_all:
        run_wifi_setup()


@app.command()
@device_decorator
def update() -> None:
    """Update ROS package and rebuilt docker container."""
    from psilia_edge.runtime.setup import runtime_home_update

    ui.banner_nav(["Runtime", "Update"], "Updating the runtime working directory…")
    runtime_home_update()


@app.command()
@device_decorator
def start(
    spatial_only: bool = typer.Option(
        False, "--spatial-only", "-s", help="Starts Spatial Runtime only (ROS2)."
    ),
    base_only: bool = typer.Option(
        False, "--base-only", "-b", help="Starts the Base Layer only (Webserver)."
    ),
    host: str = typer.Option("0.0.0.0", help="Bind address", hidden=True),
    port: int = typer.Option(8080, help="HTTP port", hidden=True),
) -> None:
    """Start base layer then spatial layer."""
    from psilia_edge.runtime.daemon import is_running
    from psilia_edge.runtime.docker import is_container_running
    from psilia_edge.runtime.core import (
        start_base_layer,
        start_spatial_layer,
        start_runtime,
    )

    ui.header(["Runtime", "Start"])

    if base_only:
        if is_running():
            ui.warn("Base layer already running.")
            raise typer.Exit(1)
        with ui.status("Starting base layer…"):
            result = start_base_layer(host=host, port=port)
        ui.print_tree(result, label="base")
        return

    if spatial_only:
        if is_container_running():
            ui.warn("Spatial layer already running.")
            raise typer.Exit(1)
        with ui.status("Starting spatial layer…"):
            result = start_spatial_layer()
        ui.print_tree(result, label="spatial")
        return

    # default: start both layers
    with ui.status("Starting runtime…"):
        result = start_runtime(host=host, port=port)

    ui.detail("check runtime status", "psilia runtime status [device]")
    ui.detail("live view", "psilia runtime attach [device]")
    ui.detail("stop runtime", "psilia runtime stop [device]")
    ui.print_tree(result, label="runtime")


@app.command()
@device_decorator
def stop(
    spatial_only: bool = typer.Option(
        False, "--spatial-only", "-s", help="Stops Spatial Runtime only (ROS2)."
    ),
    base_only: bool = typer.Option(
        False, "--base-only", "-b", help="Stops the Base Layer only (Webserver)."
    ),
) -> None:
    """Stop spatial layer then base layer."""
    from psilia_edge.runtime.core import (
        stop_base_layer,
        stop_spatial_layer,
        stop_runtime,
    )
    from psilia_edge.runtime.daemon import is_running
    from psilia_edge.runtime.docker import is_container_running

    ui.header(["Runtime", "Stop"])

    if base_only:
        if not is_running():
            ui.warn("Base layer is not running.")
            raise typer.Exit(1)
        with ui.status("Stopping base layer…"):
            result = stop_base_layer()
        ui.print_tree(result, label="base")
        return

    if spatial_only:
        if not is_container_running():
            ui.warn("Spatial layer is not running.")
            raise typer.Exit(1)
        with ui.status("Stopping spatial layer…"):
            result = stop_spatial_layer()
        ui.print_tree(result, label="spatial")
        return

    # default: stop both layers
    with ui.status("Stopping runtime…"):
        result = stop_runtime()
    ui.print_tree(result, label="runtime")


@app.command()
@device_decorator
def status() -> None:
    from psilia_edge.runtime.status import runtime_status

    ui.header(["Runtime", "Status"], "State of base & spatial layer and network etc…")
    ui.print_tree(runtime_status(), label="Runtime Status")


# @app.command(hidden=True)
# @device_decorator
# def attach() -> None:
#     """Live status display. Runs until Ctrl-C."""
#     import time
#     from rich.console import Group
#     from rich.live import Live
#     from rich.panel import Panel
#     from rich.text import Text
#     from psilia_edge import ui
#     from psilia_edge.runtime.status import live_status
#     from psilia_edge.runtime.daemon import read_log_tail

#     ui.header(["Runtime", "Live View"], "Ctrl-C to detach…")
#     try:
#         with Live(refresh_per_second=1, screen=False) as live:
#             while True:
#                 log = Text("\n".join(read_log_tail(5)), style="dim", overflow="fold")
#                 live.update(
#                     Group(
#                         ui.build_tree(live_status(), label="status"),
#                         Panel(log, title="log", border_style="dim"),
#                     )
#                 )
#                 time.sleep(1.0)
#     except KeyboardInterrupt:
#         console.print("\n[dim]Detached.[/dim]")


@app.command(hidden=True)
def scan() -> Path:
    """Print the runtime home directory path."""
    from psilia_edge.runtime.hotplug import scan_cameras

    ui.header(["Runtime", "Scan"], "Scanning for connected cameras…")
    groups = scan_cameras()
    if not groups:
        ui.warn("No cameras found.")
    else:
        # for i, group in enumerate(groups):
        # ui.print_tree(group, label=f"camera {i}")
        ui.print_tree(groups, label="cameras")


@app.command(hidden=True)
def home() -> Path:
    """Print the runtime home directory path."""
    from psilia_edge.runtime.config import get_runtime_home

    print(get_runtime_home())


@app.command(hidden=True)
def repo() -> Path:
    """Print the runtime home directory path."""
    from psilia_edge.runtime.config import get_repo_dir

    print(get_repo_dir())


@app.command(hidden=True)
def conf() -> None:
    """Print the runtime configuration as YAML."""

    _check_config()
