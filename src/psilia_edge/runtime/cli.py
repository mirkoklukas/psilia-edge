"""CLI presentation layer for runtime commands.

Calls core functions and displays results. No logic lives here.

TODO: Define a typer sub-app here (e.g. `app = typer.Typer(...)`) with
      base/spatial start/stop commands, then import and mount it in cli.py
      via `app.add_typer(runtime_app, name="runtime")` or similar.
"""

from __future__ import annotations

import typer

from psilia_edge import ui
from psilia_edge.ui import console


def runtime_start(host: str, port: int, foreground: bool) -> None:
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

    ui.print_tree(result, label="runtime")


def runtime_stop() -> None:
    """Stop spatial layer then base layer."""
    from psilia_edge.runtime.core import stop_runtime

    with console.status("Stopping runtime…"):
        result = stop_runtime()

    ui.print_tree(result, label="runtime")


def base_start(host: str, port: int, foreground: bool) -> None:
    from psilia_edge.runtime.daemon import is_running
    from psilia_edge.runtime.server import serve
    from psilia_edge.runtime.core import start_base_layer

    if is_running():
        console.print("[yellow]Already running.[/yellow] Use `psilia stop` first.")
        raise typer.Exit(1)

    if foreground:
        console.print(f"Starting on [bold]http://{host}:{port}[/bold]  (foreground, Ctrl-C to stop)")
        serve(host=host, port=port)
        return

    with console.status("Starting base layer…"):
        result = start_base_layer(host=host, port=port)

    ui.ok(f"Base layer started  (PID {result['pid']})")
    ui.print_tree(result, label="base layer")


def base_stop() -> None:
    from psilia_edge.runtime.core import stop_base_layer

    result = stop_base_layer()
    if result["status"] == "stopped":
        ui.ok("Base layer stopped.")
    else:
        console.print("[dim]Not running.[/dim]")


def base_status() -> None:
    from psilia_edge.runtime.status import runtime_status

    ui.print_tree(runtime_status(), label="Runtime Status")


def spatial_start() -> None:
    from psilia_edge.runtime.core import start_spatial_layer

    with console.status("Starting spatial runtime…"):
        result = start_spatial_layer()

    if result.get("status") == "error":
        ui.fail(result.get("error", "Unknown error"))
        raise typer.Exit(1)
    elif result.get("status") == "already_running":
        console.print("[yellow]Spatial runtime already running.[/yellow]")
    else:
        ui.ok("Spatial runtime started.")
        ui.print_tree(result, label="spatial")


def spatial_stop() -> None:
    from psilia_edge.runtime.core import stop_spatial_layer

    with console.status("Stopping spatial runtime…"):
        result = stop_spatial_layer()

    if result.get("status") == "error":
        ui.fail(result.get("error", "Unknown error"))
        raise typer.Exit(1)
    elif result.get("status") == "not_running":
        console.print("[dim]Not running.[/dim]")
    else:
        ui.ok("Spatial runtime stopped.")


def build_monitor_display(log_lines: list[str]):
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from psilia_edge.runtime.daemon import is_running

    grid = Table.grid(padding=(0, 1))
    grid.add_column()

    running = is_running()
    svc = Text("● psilia base layer  ")
    svc.append("running" if running else "stopped", style="green" if running else "red")
    grid.add_row(Panel(svc, expand=True, border_style="cyan"))

    log_text = Text("\n".join(log_lines), style="dim", overflow="fold")
    grid.add_row(Panel(log_text, title="log", expand=True, border_style="dim"))

    return grid
