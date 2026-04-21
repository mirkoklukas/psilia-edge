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
from builtins import print as builtins_print
from typing import Any, Optional, Annotated, get_type_hints
import functools
import inspect
import socket
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
    device: str = typer.Argument(..., help="Registered device name"),
    install_dir: str = typer.Option(
        None,
        "--install-dir",
        "-i",
        help="Install directory on the device (e.g. /ssd)",
    ),
) -> None:
    """Bootstrap a fresh Jetson: clone repo, install CLI, set up runtime.

    The device must already be paired (psilia pair). This copies the bootstrap
    script to the device over SSH and runs it there.
    """
    import subprocess

    from psilia_edge.runtime.config import get_repo_dir

    ui.header(["Runtime", "Bootstrap"])

    if install_dir is None:
        ui.info("The install directory is where the repo will be cloned")
        ui.info("and the runtime home will be created.")
        install_dir = ui.ask("Install directory on the device", default="/ssd")

    script = get_repo_dir() / "scripts" / "bootstrap.py"
    if not script.exists():
        ui.fail(f"bootstrap.py not found at {script}")
        raise typer.Exit(1)

    ui.info(f"Copying bootstrap script to {device}…")
    rc = subprocess.run(
        ["scp", "-q", str(script), f"{device}:/tmp/psilia_bootstrap.py"]
    ).returncode
    if rc != 0:
        ui.fail("Failed to copy bootstrap script to device")
        raise typer.Exit(1)
    ui.ok("Script copied")

    ui.info(f"Running bootstrap on {device}…")
    rc = subprocess.run(
        [
            "ssh",
            "-t",
            "-o",
            "LogLevel=ERROR",
            device,
            "bash",
            "-lc",
            f"'python3 /tmp/psilia_bootstrap.py {install_dir}'",
        ]
    ).returncode
    if rc != 0:
        ui.fail("Bootstrap failed")
        raise typer.Exit(1)
    ui.done(
        f"{device} bootstrapped.",
        f"Next: [bold]psilia runtime start --base -d {device}[/bold]",
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
    quiet: Annotated[
        bool,
        typer.Option(
            "--quiet", "-q", help="Suppress the final summary and done message."
        ),
    ] = False,
) -> None:
    """Minimal runtime setup: create directory structure, build Docker image, copy ROS package."""
    from psilia_edge.runtime.setup import run_runtime_init

    if not quiet:
        ui.header(["Runtime", "Init"], "Setting up a bare-bones runtime home…")
    try:
        run_runtime_init(runtime_home, mkdir=mkdir, quiet=quiet)
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


def _checks_dict(ctx) -> dict:
    return ctx.to_dict()


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
    """Start the base layer (default), or spatial layer with --spatial."""
    import logging

    from psilia_edge.runtime.core import (
        SpatialRequirementsError,
        is_base_layer_running,
        is_spatial_layer_running,
        start_base_layer,
        start_spatial_layer,
    )

    ui.header(["Runtime", "Start"])
    logging.getLogger("psilia_edge.runtime.core").setLevel(logging.INFO)

    if spatial_only:
        if is_spatial_layer_running():
            ui.warn("Spatial layer already running.")
            raise typer.Exit(1)
        try:
            result = start_spatial_layer(force=force)
        except SpatialRequirementsError as e:
            ui.print_tree(_checks_dict(e.result), label="requirements")
            ui.fail(
                "Spatial requirements not met. Run: psilia runtime start --spatial --force"
            )
            raise typer.Exit(1)
        ui.print_tree(result, label="spatial")
        return

    # default (and --base): start base layer only
    if is_base_layer_running():
        ui.warn("Base layer already running.")
        raise typer.Exit(1)
    result = start_base_layer(host=host, port=port)
    ui.print_tree(result, label="base")


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
    import logging

    from psilia_edge.runtime.core import (
        is_base_layer_running,
        is_spatial_layer_running,
        stop_base_layer,
        stop_spatial_layer,
        stop_runtime,
    )

    ui.header(["Runtime", "Stop"])
    logging.getLogger("psilia_edge.runtime.core").setLevel(logging.INFO)

    if base_only:
        if not is_base_layer_running():
            ui.warn("Base layer is not running.")
            raise typer.Exit(1)
        result = stop_base_layer()
        ui.print_tree(result, label="base")
        return

    if spatial_only:
        if not is_spatial_layer_running():
            ui.warn("Spatial layer is not running.")
            raise typer.Exit(1)
        result = stop_spatial_layer()
        ui.print_tree(result, label="spatial")
        return

    # default: stop both layers
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
        False,
        "--checks",
        "--spatial-requirements",
        help="Include spatial requirements check.",
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
    json: bool = typer.Option(
        False,
        "--json",
        help="Print result as JSON (machine-readable, suppresses all other output).",
    ),
) -> None:
    import json as _json

    from psilia_edge.runtime.status import runtime_status

    if json:
        ui.silence()

    result = runtime_status(
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
    )

    if json:
        builtins_print(_json.dumps(result))
    else:
        ui.header(
            ["Runtime", "Status"], "State of base & spatial layer and network etc…"
        )
        ui.print_tree(result, label="Runtime Status")


@app.command()
@device_decorator
def attach() -> None:
    """Live runtime view: heartbeat, topic Hz, ROS logs. [s]tart/[x] stop spatial."""
    from psilia_edge.runtime.core import is_base_layer_running

    if not is_base_layer_running():
        ui.warn(
            "Base layer is not running. Start it first: psilia runtime start --base"
        )
        raise typer.Exit(1)

    _run_attach()


def _run_attach() -> None:
    import json
    import select
    import sys
    import termios
    import threading
    import time
    import tty

    from rich.console import Group
    from rich.live import Live
    from rich.padding import Padding
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    from psilia_edge.runtime.config import RUN_DIR
    from psilia_edge.runtime.core import SpatialRequirementsError
    from psilia_edge.runtime.docker import get_ros_log_path

    hz_file = RUN_DIR / "hz.json"
    hb_file = RUN_DIR / "heartbeat.json"
    log_file = get_ros_log_path()

    status_msg = ""
    status_style = "dim"
    force_mode = True
    show_logs = False
    checks: dict = {}  # flat dict: dotted key → {"ok": bool, "detail": str}

    def read_json(path):
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def read_log_tail(n=12):
        try:
            lines = log_file.read_text(errors="replace").splitlines()
            return lines[-n:]
        except OSError:
            return []

    def refresh_checks():
        nonlocal checks
        from psilia_edge.runtime.core import check_spatial_requirements

        ctx = check_spatial_requirements()
        checks = ctx.to_dict()

    def build_display():
        from psilia_edge.runtime.daemon import is_running as is_daemon_running

        parts = []

        # ── Shortcuts bar ────────────────────────────────────
        bar = Text("  ")
        bar.append("[s]", style="bold")
        bar.append(" start  ", style="dim")
        bar.append("[x]", style="bold")
        bar.append(" stop  ", style="dim")
        bar.append("[f]", style="bold")
        bar.append(" force  ", style="dim")
        bar.append("[r]", style="bold")
        bar.append(" checks  ", style="dim")
        bar.append("[l]", style="bold")
        bar.append(" logs  ", style="dim")
        bar.append("[q]", style="bold")
        bar.append(" quit", style="dim")
        parts.append(bar)

        # ── Status message ───────────────────────────────────
        parts.append(Text(f"  {status_msg}" if status_msg else " ", style=status_style))

        # ── Base layer ───────────────────────────────────────
        base_running = is_daemon_running()
        base_text = (
            Text("running", style="green")
            if base_running
            else Text("stopped", style="red")
        )
        line = Text("  base layer: ")
        line.append_text(base_text)
        if base_running:
            from psilia_edge.runtime.config import get_api_port

            port = get_api_port()
            hostname = socket.gethostname().split(".")[0]
            line.append(f"  http://{hostname}.local:{port}", style="dim")
        parts.append(line)

        # ── Spatial layer ────────────────────────────────────
        hb = read_json(hb_file)
        if hb:
            try:
                age = time.time() - hb_file.stat().st_mtime
            except OSError:
                age = 999
            if age < 5:
                spatial_text = Text("running", style="green")
                hb_detail = f"  heartbeat {age:.1f}s ago"
            else:
                spatial_text = Text("stale", style="yellow")
                hb_detail = f"  heartbeat {age:.0f}s ago"
        else:
            spatial_text = Text("not running", style="dim")
            hb_detail = ""

        line = Text("  spatial layer: ")
        line.append_text(spatial_text)
        if hb_detail:
            line.append(hb_detail, style="dim")
        parts.append(line)
        parts.append(Text(""))

        # ── Preflight checks ─────────────────────────────────
        if checks:
            pf_line = Text("  preflight checks: ")
            force_label = "on" if force_mode else "off"
            force_style = "green" if force_mode else "dim"
            pf_line.append("(force: ", style="dim")
            pf_line.append(force_label, style=force_style)
            pf_line.append(")", style="dim")
            parts.append(pf_line)
            for key, info in checks.items():
                ok = info["ok"]
                detail = info.get("detail", "")
                symbol = "✓" if ok else "✗"
                symbol_style = "green" if ok else "red"
                line = Text("  ")
                line.append(f"  {symbol} ", style=symbol_style)
                line.append(key, style="bold" if not ok else "")
                if detail:
                    line.append(f"  {detail}", style="dim")
                parts.append(line)
            parts.append(Text(""))

        # ── Hz table ─────────────────────────────────────────
        hz = read_json(hz_file)
        if hz:
            try:
                hz_age = time.time() - hz_file.stat().st_mtime
            except OSError:
                hz_age = 999
            hz_live = hz_age < 3

            diag_line = Text("  diagnostics: ")
            if hz_live:
                diag_line.append("running", style="green")
            else:
                diag_line.append("offline", style="red")
            parts.append(diag_line)

            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_column(style="dim", min_width=40)
            table.add_column(justify="right")
            for topic, info in hz.items():
                rate_val = info.get("hz", 0)
                if hz_live and rate_val > 0:
                    rate = Text(f"{rate_val:.1f} Hz", style="cyan")
                else:
                    rate = Text("—", style="dim")
                table.add_row(topic, rate)
            parts.append(Padding(table, (0, 2, 0, 2)))
            parts.append(Text(""))

        # ── Log tail ─────────────────────────────────────────
        if show_logs:
            log_lines = read_log_tail()
            log_text = Text(
                "\n".join(log_lines) if log_lines else "(no log)",
                style="dim",
                overflow="fold",
            )
            parts.append(Panel(log_text, title="log", border_style="dim", expand=True))

        return Group(*parts)

    def do_spatial_start():
        nonlocal status_msg, status_style, checks
        status_msg = "starting spatial layer..."
        status_style = "yellow"
        try:
            from psilia_edge.runtime.core import start_spatial_layer

            start_spatial_layer(force=force_mode)
            status_msg = "spatial layer started"
            status_style = "green"
        except SpatialRequirementsError as e:
            checks = e.result.to_dict()
            failed = [k for k, v in checks.items() if not v["ok"]]
            status_msg = f"failed: {', '.join(failed)}"
            status_style = "red"
        except Exception as e:
            status_msg = f"error: {e}"
            status_style = "red"

    def do_spatial_stop():
        nonlocal status_msg, status_style
        status_msg = "stopping spatial layer..."
        status_style = "yellow"
        try:
            from psilia_edge.runtime.core import stop_spatial_layer

            stop_spatial_layer()
            status_msg = "spatial layer stopped"
            status_style = "green"
        except Exception as e:
            status_msg = f"error: {e}"
            status_style = "red"

    def do_refresh_checks():
        nonlocal status_msg, status_style
        status_msg = "checking spatial requirements..."
        status_style = "yellow"
        try:
            refresh_checks()
            status_msg = ""
        except Exception as e:
            status_msg = f"check error: {e}"
            status_style = "red"

    def read_key():
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1)
        return None

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    ui.header(["Runtime", "Attach"])

    # Initial checks run before entering the live display.
    try:
        refresh_checks()
    except Exception:
        pass

    try:
        tty.setcbreak(fd)
        with Live(
            build_display(), refresh_per_second=1, console=ui.console, transient=False
        ) as live:
            while True:
                key = read_key()
                if key in ("q", "\x03"):
                    break
                elif key == "s":
                    threading.Thread(target=do_spatial_start, daemon=True).start()
                elif key == "x":
                    threading.Thread(target=do_spatial_stop, daemon=True).start()
                elif key == "f":
                    force_mode = not force_mode
                elif key == "l":
                    show_logs = not show_logs
                elif key == "r":
                    threading.Thread(target=do_refresh_checks, daemon=True).start()

                live.update(build_display())
                time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        ui.print("[dim]Detached.[/dim]")


@app.command(name="ui")
def run_ui() -> None:
    """Launch the Textual TUI for runtime monitoring."""
    from psilia_edge.runtime.app import run

    run()


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


# TODO: device_decorator does not forward flags to the remote command — it only
# forwards `psilia runtime {func_name}` with no arguments. This means any command
# decorated with @device_decorator that also takes flags (like `config`) will silently
# drop those flags when run with -d. This needs to be fixed in device_decorator by
# reconstructing the full CLI invocation (e.g. from sys.argv, stripping --device/-d
# and its value) before passing to run_on_device.
@app.command()
def config(
    keys: Optional[list[str]] = typer.Argument(
        None, help="Config keys to query. Omit to list all."
    ),
    json: bool = typer.Option(
        False, "--json", help="Print result as JSON (machine-readable)."
    ),
) -> None:
    """Query runtime config values. Plain output (one value per line) or --json.

    Available keys: home-dir, data-dir, ros-dir, log-dir, repo-dir, api-port, rosbridge-port

    Examples:
      psilia runtime config home-dir
      psilia runtime config home-dir data-dir
      psilia runtime config home-dir data-dir --json
    """
    import json as _json

    from psilia_edge.runtime import config as _config

    _KEYS: dict[str, Any] = {
        "home-dir": _config.get_runtime_home,
        "data-dir": _config.get_data_dir,
        "ros-dir": _config.get_ros_dir,
        "log-dir": _config.get_log_dir,
        "repo-dir": _config.get_repo_dir,
        "api-port": _config.get_api_port,
        "rosbridge-port": _config.get_rosbridge_port,
    }

    queried = keys or list(_KEYS.keys())

    unknown = [k for k in queried if k not in _KEYS]
    if unknown:
        for k in unknown:
            ui.warn(f"Unknown config key: '{k}'. Available: {', '.join(_KEYS)}")
        raise typer.Exit(1)

    result = {k: str(_KEYS[k]()) for k in queried}

    if json:
        builtins_print(_json.dumps(result))
    else:
        for value in result.values():
            builtins_print(value)
