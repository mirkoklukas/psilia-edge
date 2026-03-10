"""CLI presentation layer for runtime commands.

Calls core functions and displays results. No logic lives here.

Naming convention:
  function   — acts as a CLI command (owns output and side effects,
               called directly from cli.py command handlers)
  _function  — helper (returns a value or renderable, no direct output)

TODO: Define a typer sub-app here (e.g. `app = typer.Typer(...)`) with
      base/spatial start/stop commands, then import and mount it in cli.py
      via `app.add_typer(runtime_app, name="runtime")` or similar.
"""

from __future__ import annotations
from typing import Optional
import functools
import inspect

import typer

from psilia_edge import ui
from psilia_edge.ui import console


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
@device_decorator
def start(
    host: str = typer.Option("0.0.0.0", help="Bind address", hidden=True),
    port: int = typer.Option(8080, help="HTTP port", hidden=True),
) -> None:
    """Start base layer then spatial layer."""
    from psilia_edge.runtime.daemon import is_running
    from psilia_edge.runtime.core import start_runtime

    if is_running():
        ui.warn("[yellow]Already running.[/yellow].")
        raise typer.Exit(1)

    ui.header(["Runtime", "Start"])

    with ui.status("Starting runtime…"):
        result = start_runtime(host=host, port=port)

    ui.detail("check runtime status", "psilia runtime status \[device]")
    ui.detail("live view", "psilia runtime attach \[device]")
    ui.detail("stop runtime", "psilia runtime stop \[device]")
    ui.print_tree(result, label="runtime")


@app.command()
@device_decorator
def stop() -> None:
    """Stop spatial layer then base layer."""
    from psilia_edge.runtime.core import stop_runtime
    from psilia_edge.runtime.daemon import is_running

    if not is_running():
        ui.warn("[yellow]Nothing running.[/yellow]")
        raise typer.Exit(1)

    with ui.status("Stopping runtime…"):
        result = stop_runtime()

    ui.header(["Runtime", "Stop"])

    ui.print_tree(result, label="runtime")


@app.command()
@device_decorator
def status() -> None:
    from psilia_edge.runtime.status import runtime_status

    ui.header(["Runtime", "Status"])
    ui.print_tree(runtime_status(), label="Runtime Status")


@app.command("attach")
@device_decorator
def live_view() -> None:
    """Live status display. Runs until Ctrl-C."""
    import time
    from rich.console import Group
    from rich.live import Live
    from rich.panel import Panel
    from rich.text import Text
    from psilia_edge import ui
    from psilia_edge.runtime.status import live_status
    from psilia_edge.runtime.daemon import read_log_tail

    ui.header(["Runtime", "Live View"], "Ctrl-C to detach...")
    try:
        with Live(refresh_per_second=1, screen=False) as live:
            while True:
                log = Text("\n".join(read_log_tail(5)), style="dim", overflow="fold")
                live.update(
                    Group(
                        ui.build_tree(live_status(), label="status"),
                        Panel(log, title="log", border_style="dim"),
                    )
                )
                time.sleep(1.0)
    except KeyboardInterrupt:
        console.print("\n[dim]Detached.[/dim]")


@app.command()
@device_decorator
def update() -> None:
    """Pull latest psilia-edge and rebuild the Docker image."""
    from psilia_edge.runtime.setup import run_update

    run_update()


@app.command(hidden=True)
@device_decorator
def setup() -> None:
    """Pull latest psilia-edge and rebuild the Docker image."""
    from psilia_edge.runtime.setup import run_setup

    run_setup()
