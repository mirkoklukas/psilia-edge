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
            run_on_device(device, f"psilia {func.__name__}")
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
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground", hidden=True),
) -> None:
    """Start base layer then spatial layer."""
    from psilia_edge.runtime.daemon import is_running
    from psilia_edge.runtime.server import serve
    from psilia_edge.runtime.core import start_runtime

    if is_running():
        console.print("[yellow]Already running.[/yellow] Use `psilia stop` first.")
        raise typer.Exit(1)
    
    if foreground:
        console.print(f"Starting on [bold]http://{host}:{port}[/bold]  (foreground, Ctrl-C to stop)")
        serve(host=host, port=port)
        return

    with console.status("Starting runtime…"):
        result = start_runtime(host=host, port=port)

    console.print(
        "\n  [dim]psilia status [device][/dim]   — check runtime status"
        "\n  [dim]psilia attach [device][/dim]   — live view"
        "\n  [dim]psilia stop   [device][/dim]   — stop the runtime\n"
    )
    ui.print_tree(result, label="runtime")


@app.command()
@device_decorator
def stop() -> None:
    """Stop spatial layer then base layer."""
    from psilia_edge.runtime.core import stop_runtime

    with console.status("Stopping runtime…"):
        result = stop_runtime()

    ui.print_tree(result, label="runtime")


@app.command()
@device_decorator
def status() -> None:
    from psilia_edge.runtime.status import runtime_status
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

    console.print("Live view  [dim]Ctrl-C to detach[/dim]\n")
    try:
        with Live(refresh_per_second=1, screen=False) as live:
            while True:
                log = Text("\n".join(read_log_tail(5)), style="dim", overflow="fold")
                live.update(Group(
                    ui.build_tree(live_status(), label="status"),
                    Panel(log, title="log", border_style="dim"),
                ))
                time.sleep(1.0)
    except KeyboardInterrupt:
        console.print("\n[dim]Detached.[/dim]")



@app.command()
@device_decorator
def update() -> None:
    """Pull latest psilia-edge and rebuild the Docker image."""
    from psilia_edge.runtime.setup import run_update
    run_update()