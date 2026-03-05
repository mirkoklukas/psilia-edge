"""Runtime CLI command helpers (start, stop, status, monitor).

These are called from psilia_edge.cli — the CLI commands own argument parsing
and the if-device branching; these functions contain the actual logic.
"""

from __future__ import annotations

import shlex
import socket
import time

import typer

from psilia_edge.ui import console


def _require_runtime_host(device_hint: str) -> None:
    """Exit with a clear message if not running on a runtime host (Jetson)."""
    from psilia_edge.config import is_runtime_host

    if not is_runtime_host():
        console.print(
            f"[red]This command only runs on a Jetson.[/red]\n"
            f"  To target a registered device: [bold]psilia {device_hint}[/bold]"
        )
        raise typer.Exit(1)


def _ssh_run(device: str, *args: str) -> None:
    """Run `psilia <args>` on a registered device over SSH and stream output.

    -t allocates a pseudo-TTY (teletypewriter) on the remote side, making the
    remote process think it is connected to a real terminal. Without it, SSH
    stdout is a pipe and Rich detects no TTY, falling back to unstyled output.
    """
    import subprocess

    cmd = shlex.join(["psilia", *args])
    result = subprocess.run(["ssh", "-t", device, "bash", "-lc", f"'{cmd}'"])
    raise typer.Exit(result.returncode)


def _ssh_exec(device: str, *args: str) -> None:
    """Replace current process with `ssh <device> psilia <args>` (preserves TTY)."""
    import os

    cmd = shlex.join(["psilia", *args])
    os.execvp("ssh", ["ssh", "-t", device, "bash", "-lc", f"'{cmd}'"])


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
    from psilia_edge.network.probe import list_interfaces
    from psilia_edge.runtime.daemon import is_running

    running = is_running()
    style = "green" if running else "dim"
    label = "running" if running else "stopped"
    console.print(f"psilia base layer: [{style}]{label}[/{style}]")

    with console.status("Scanning interfaces…"):
        interfaces = list_interfaces()
    if interfaces:
        _show_interface_table(interfaces)
    else:
        console.print("[dim]No interfaces found.[/dim]")


def _show_interface_table(interfaces) -> None:
    from rich.table import Table

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Interface")
    table.add_column("Type")
    table.add_column("State")
    table.add_column("IP")
    table.add_column("Connection")
    for i in interfaces:
        state_style = "green" if i.is_connected else "dim"
        table.add_row(
            i.name,
            i.type,
            f"[{state_style}]{i.state}[/{state_style}]",
            i.ip4 or "—",
            i.connection or "—",
        )
    console.print(table)


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
