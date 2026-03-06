"""Runtime CLI command helpers (start, stop, status, monitor).

These are called from psilia_edge.cli — the CLI commands own argument parsing
and the if-device branching; these functions contain the actual logic.
"""

from __future__ import annotations

import socket
import time

import typer
import yaml

from psilia_edge.runtime.status import _runtime_status
from psilia_edge.ui import _header, _yaml, console
from rich.pretty import pprint

def _require_runtime_host(device_hint: str) -> None:
    """Exit with a clear message if not running on a runtime host (Jetson)."""
    from psilia_edge.runtime.core import is_runtime_host

    if not is_runtime_host():
        console.print(
            f"[red]This command only runs on a Jetson.[/red]\n"
            f"  To target a registered device: [bold]psilia {device_hint}[/bold]"
        )
        raise typer.Exit(1)



def _base_start(host: str, port: int, foreground: bool) -> None:
    from psilia_edge.runtime.daemon import LOG_FILE, is_running, start_daemon
    from psilia_edge.runtime.server import serve

    if is_running():
        console.print("[yellow]Already running.[/yellow] Use `psilia stop` first.")
        raise typer.Exit(1)

    if foreground:
        console.print(f"Starting on [bold]http://{host}:{port}[/bold]  (foreground, Ctrl-C to stop)")
        serve(host=host, port=port)
        return

    with console.status("Starting base layer…"):
        pid = start_daemon(host=host, port=port)
        time.sleep(1.5)  # give uvicorn a moment to bind

    hostname = socket.gethostname().split(".")[0]
    try:
        _s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _s.connect(("8.8.8.8", 80))
        lan_ip = _s.getsockname()[0]
        _s.close()
    except OSError:
        lan_ip = None
    console.print(f"[green]✓[/green] Base layer started  (PID {pid})")
    console.print(f"  Web UI:  [bold]http://{hostname}.local:{port}[/bold]  [dim](from other devices)[/dim]")
    if lan_ip:
        console.print(f"           [bold]http://{lan_ip}:{port}[/bold]  [dim](always works)[/dim]")
    console.print(f"  Logs:    {LOG_FILE}")
    console.print("  Monitor: [bold]psilia monitor[/bold]")


def _base_stop() -> None:
    from psilia_edge.runtime.daemon import stop_daemon

    if stop_daemon():
        console.print("[green]✓[/green] Base layer stopped.")
    else:
        console.print("[dim]Not running.[/dim]")


def _base_status() -> None:
    import yaml
    from psilia_edge.runtime.status import _runtime_status
    from psilia_edge.ui import _header

    _header("Runtime → [bold]Status[/bold]", "Current status of the runtime, connected devices, etc.")
    _yaml(_runtime_status())


def _build_monitor_display(log_lines: list[str]):
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
