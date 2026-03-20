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
from typing import Optional, Annotated, get_type_hints
import functools
import inspect
from pathlib import Path

import typer

from psilia_edge import ui
from psilia_edge.runtime.config import _check_config


def device_decorator(func):
    """Inject an optional --device / -d option into a runtime command.

    If --device is given, the command is forwarded over SSH to the named device.
    Otherwise it runs locally, requiring the machine to be a runtime host.
    """
    device_param = inspect.Parameter(
        "device",
        kind=inspect.Parameter.KEYWORD_ONLY,
        default=typer.Option(
            None,
            "--device",
            "-d",
            help="Registered device name (runs command over SSH)",
        ),
        annotation=Optional[str],
    )
    # Resolve string annotations (from __future__ import annotations) before building the
    # new signature — inspect.signature(wrapper, eval_str=True) won't evaluate them when
    # __signature__ is explicitly set, so we pre-evaluate them here.
    type_hints = get_type_hints(func, include_extras=True)
    orig_params = [
        p.replace(annotation=type_hints.get(p.name, p.annotation))
        for p in inspect.signature(func).parameters.values()
    ]
    new_sig = inspect.signature(func).replace(parameters=orig_params + [device_param])

    @functools.wraps(func)
    def wrapper(*args, device=None, **kwargs):
        from psilia_edge.utils import run_on_device

        if device is not None:
            run_on_device(device, f"psilia runtime {func.__name__}")
            return
        else:
            return func(*args, **kwargs)

    del (
        wrapper.__wrapped__
    )  # prevent typer from following __wrapped__ to the original func
    wrapper.__signature__ = new_sig
    return wrapper


app = typer.Typer(help="Psilia Edge — spatial perception runtime for edge devices")


# +----------------------------------------------------------------
# |
# |   CLI Commands on the Data & Device Manager Side
# |
# +----------------------------------------------------------------
@app.command()
def pair():
    """Pair a Jetson: connect, generate SSH keypair, register device on this laptop."""
    from psilia_edge.device_manager.pair import run_pair_wizard

    run_pair_wizard()


@app.command()
def bootstrap(
    device: str = typer.Argument(
        None, help="Registered device name (runs command over SSH)"
    ),
) -> None:
    """Run this once on a fresh Jetson (or laptop for dev)."""
    raise NotImplementedError(
        "Bootstrap command not implemented yet."
        "For now please clone the repo, pip-install, and run 'psilia runtime init' to set up the runtime on the device."
    )


@app.command()
def devices():
    """List all registered Jetson devices."""
    from psilia_edge.runtime.config import read_config

    config = read_config()
    devs = config.get("registered_devices", {})

    if not devs:
        ui.info(
            "[dim]No devices registered. Run 'psilia runtime pair' to add one.[/dim]"
        )
        return

    ui.print_tree(devs, label="Registered Devices")


# +----------------------------------------------------------------
# |
# |   Actual Runtime Commands
# |
# +----------------------------------------------------------------
@app.command()
@device_decorator
def init(
    runtime_home: Annotated[
        Path, typer.Argument(help="Path to the runtime home directory.")
    ] = Path("./"),
    mkdir: Annotated[
        bool,
        typer.Option("--mkdir", "-m", help="Create the directory if it doesn't exist."),
    ] = False,
) -> None:
    """Minimal runtime setup: create directory structure, build Docker image, copy ROS package."""
    from psilia_edge.runtime.setup import run_runtime_init

    ui.header(["Runtime", "Init"], "Setting up a bare-bones runtime home…")
    try:
        run_runtime_init(runtime_home, mkdir=mkdir)
    except RuntimeError as e:
        ui.fail(str(e))
        raise typer.Exit(1)


@app.command()
@device_decorator
def setup(
    init: bool = typer.Option(
        False,
        "--init/--skip-init",
        "-i",
        help="Whether to initialize the runtime home directory",
    ),
    hotspot: bool = typer.Option(
        False, "--hotspot/--no-hotspot", "-h", help="Run AP hotspot setup"
    ),
    wifi: bool = typer.Option(
        False, "--wifi/--no-wifi", "-w", help="Run home WiFi setup"
    ),
    run_all: bool = typer.Option(
        False, "--all/--none", "-a", help="Run all setup steps (init, hotspot, wifi)."
    ),
) -> None:
    """Configure the runtime: init home directory, network hotspot, and WiFi."""
    from psilia_edge.runtime.config import get_runtime_home
    from psilia_edge.runtime.setup import (
        run_runtime_init,
        run_hotspot_setup,
        run_wifi_setup,
    )

    ui.header(["Runtime", "Setup"], "Setting up a runtime...")
    if init or run_all:
        home = ui.ask("Runtime home directory")
        run_runtime_init(home, mkdir=True)
    else:
        home = get_runtime_home()
        ui.info(f"Skipping runtime home initialization. Using: {home}")

    if hotspot or run_all:
        run_hotspot_setup()
    if wifi or run_all:
        run_wifi_setup()


@app.command()
@device_decorator
def update() -> None:
    """Update ROS package and rebuilt docker container."""
    from psilia_edge.runtime.setup import run_update

    ui.header(["Runtime", "Update"], "Updating the runtime working directory…")
    run_update()


@app.command()
@device_decorator
def start(
    spatial_only: bool = typer.Option(
        False, "--spatial", "-s", help="Starts Spatial Runtime only (ROS2)."
    ),
    base_only: bool = typer.Option(
        False, "--base", "-b", help="Starts the Base Layer only (Webserver)."
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Skip spatial requirements check."
    ),
    host: str = typer.Option("0.0.0.0", help="Bind address", hidden=True),
    port: int = typer.Option(None, help="HTTP port", hidden=True),
) -> None:
    """Start base layer then spatial layer."""
    from psilia_edge.runtime.core import (
        SpatialRequirementsError,
        is_base_layer_running,
        is_spatial_layer_running,
        start_base_layer,
        start_spatial_layer,
        start_runtime,
    )

    ui.header(["Runtime", "Start"])

    if base_only:
        if is_base_layer_running():
            ui.warn("Base layer already running.")
            raise typer.Exit(1)
        with ui.status("Starting base layer…"):
            result = start_base_layer(host=host, port=port)
        ui.print_tree(result, label="base")
        return

    if spatial_only:
        if is_spatial_layer_running():
            ui.warn("Spatial layer already running.")
            raise typer.Exit(1)
        try:
            with ui.status("Starting spatial layer…"):
                result = start_spatial_layer(force=force)
        except SpatialRequirementsError as e:
            ui.print_tree(e.checks, label="requirements")
            ui.fail(
                "Spatial requirements not met. Run: psilia runtime start --spatial --force"
            )
            raise typer.Exit(1)
        ui.print_tree(result, label="spatial")
        return

    # default: start both layers
    try:
        with ui.status("Starting runtime…"):
            result = start_runtime(host=host, port=port, force=force)
    except SpatialRequirementsError as e:
        ui.print_tree(e.checks, label="requirements")
        ui.fail(
            "Spatial requirements not met. Run: psilia runtime start --spatial --force"
        )
        raise typer.Exit(1)

    ui.detail("check runtime status", "psilia runtime status [device]")
    ui.detail("live view", "psilia runtime attach [device]")
    ui.detail("stop runtime", "psilia runtime stop [device]")
    ui.print_tree(result, label="runtime")


@app.command()
@device_decorator
def stop(
    spatial_only: bool = typer.Option(
        False, "--spatial", "-s", help="Stops Spatial Runtime only (ROS2)."
    ),
    base_only: bool = typer.Option(
        False, "--base", "-b", help="Stops the Base Layer only (Webserver)."
    ),
) -> None:
    """Stop spatial layer then base layer."""
    from psilia_edge.runtime.core import (
        is_base_layer_running,
        is_spatial_layer_running,
        stop_base_layer,
        stop_spatial_layer,
        stop_runtime,
    )

    ui.header(["Runtime", "Stop"])

    if base_only:
        if not is_base_layer_running():
            ui.warn("Base layer is not running.")
            raise typer.Exit(1)
        with ui.status("Stopping base layer…"):
            result = stop_base_layer()
        ui.print_tree(result, label="base")
        return

    if spatial_only:
        if not is_spatial_layer_running():
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
def status(
    base: bool = typer.Option(
        False, "--base", help="Include base layer state (running, uptime)."
    ),
    spatial_running: bool = typer.Option(
        False, "--spatial-running", help="Include spatial running state only."
    ),
    spatial: bool = typer.Option(
        False,
        "--spatial",
        help="Include full spatial layer state (running, heartbeat, ros).",
    ),
    spatial_requirements: bool = typer.Option(
        False, "--spatial-requirements", help="Include spatial requirements check."
    ),
    server: bool = typer.Option(
        False, "--server", help="Include server details (url, pid, log)."
    ),
    docker: bool = typer.Option(
        False, "--docker", help="Include Docker daemon and container state."
    ),
    ros: bool = typer.Option(
        False, "--ros", help="Include ROS nodes, topics, and rosbridge."
    ),
    storage: bool = typer.Option(False, "--storage", help="Include storage usage."),
    hotspot: bool = typer.Option(False, "--hotspot", help="Include hotspot status."),
    uptime: bool = typer.Option(False, "--uptime", help="Include uptime status."),
    recording: bool = typer.Option(
        False, "--recording", help="Include active recording status."
    ),
) -> None:
    from psilia_edge.runtime.status import runtime_status

    ui.header(["Runtime", "Status"], "State of base & spatial layer and network etc…")
    ui.print_tree(
        runtime_status(
            uptime=uptime,
            base=base,
            spatial_running=spatial_running,
            spatial=spatial,
            spatial_requirements=spatial_requirements,
            server=server,
            docker=docker,
            ros=ros,
            storage=storage,
            hotspot=hotspot,
            recording=recording,
        ),
        label="Runtime Status",
    )


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


@app.command()
@device_decorator
def logs(
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output."),
    lines: int = typer.Option(50, "--tail", "-n", help="Number of lines to show."),
) -> None:
    """Show ROS launch log output."""
    import subprocess
    from psilia_edge.runtime.docker import get_ros_log_path

    log_path = get_ros_log_path()
    if not log_path.exists():
        ui.warn(f"No log file found at {log_path}. Has the spatial layer been started?")
        raise typer.Exit(1)

    cmd = ["tail", f"-{lines}", str(log_path)]
    if follow:
        cmd = ["tail", "-f", str(log_path)]
    subprocess.run(cmd)


@app.command(hidden=True)
def cam() -> None:
    """Detect connected camera and show what would be written to launch_params.yaml."""
    from psilia_edge.runtime.hotplug import pick_camera_device

    ui.header(["Runtime", "Camera"], "Detecting camera…")
    camera = pick_camera_device()
    if not camera:
        ui.warn("No camera detected.")
        return

    launch_params = {"camera_node": {"ros__parameters": camera}}
    ui.print_tree(launch_params, label="launch_params.yaml")


@app.command(hidden=True)
def scan() -> Path:
    """Print the runtime home directory path."""
    from psilia_edge.runtime.hotplug import scan_cameras, usb_list_devices

    ui.header(["Runtime", "Scan"], "Scanning for connected cameras…")
    groups = scan_cameras()
    if not groups:
        ui.warn("No cameras found.")
    else:
        ui.print_tree(groups, label="cameras")

    ui.print_tree(usb_list_devices(), label="USB devices")


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
@device_decorator
def conf() -> None:
    """Print the runtime configuration as YAML."""

    _check_config()
