import socket
import time
from typing import Optional

import typer
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

app = typer.Typer(help="Psilia Edge — spatial perception runtime for edge devices")
base_app = typer.Typer(help="Manage the base layer (daemon + web server)")
spatial_app = typer.Typer(help="Manage the Spatial Runtime (ROS nodes)")

app.add_typer(base_app, name="base")
app.add_typer(spatial_app, name="spatial")

console = Console()


# ── top-level commands ────────────────────────────────────────────────────────


@app.command()
def pair():
    """Pair a Jetson: connect, generate SSH keypair, register device on this laptop."""
    from psilia_edge.init import run_pair_wizard

    run_pair_wizard()


@app.command()
def setup(device: Optional[str] = typer.Argument(None, help="Registered device name")):
    """Bootstrap a Jetson device.

    With DEVICE: runs all setup steps over SSH from this laptop.
    Without DEVICE: runs setup locally (on the Jetson itself).
    """
    if device:
        from psilia_edge.setup import run_setup_remote

        run_setup_remote(device)
    else:
        from psilia_edge.setup import run_setup_local

        run_setup_local()


@app.command(hidden=True)
def debug():
    """Show internal state: psilia config and managed SSH config section."""
    from psilia_edge.config import LAPTOP_CONFIG_PATH
    from psilia_edge.init import _SSH_CONFIG_PATH, _SSH_SECTION_END, _SSH_SECTION_START

    console.rule("[bold]~/.psilia/config.yaml")
    if LAPTOP_CONFIG_PATH.exists():
        console.print(LAPTOP_CONFIG_PATH.read_text())
    else:
        console.print(f"[dim]{LAPTOP_CONFIG_PATH} not found[/dim]")

    console.rule("[bold]~/.ssh/config  (psilia section)")
    if _SSH_CONFIG_PATH.exists():
        text = _SSH_CONFIG_PATH.read_text()
        if _SSH_SECTION_START in text:
            start = text.index(_SSH_SECTION_START)
            end = text.index(_SSH_SECTION_END) + len(_SSH_SECTION_END)
            console.print(text[start:end])
        else:
            console.print("[dim]No psilia section found[/dim]")
    else:
        console.print(f"[dim]{_SSH_CONFIG_PATH} not found[/dim]")


@app.command()
def devices():
    """List all registered Jetson devices."""
    from psilia_edge.config import read_laptop_config

    config = read_laptop_config()
    devs = config.get("devices", {})

    if not devs:
        console.print("[dim]No devices registered. Run 'psilia pair' to add one.[/dim]")
        return

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Name")
    table.add_column("Host")
    table.add_column("User")
    table.add_column("Camera")
    table.add_column("Data Path")

    for name, dev in devs.items():
        table.add_row(
            name,
            dev.get("host", "—"),
            dev.get("user", "—"),
            dev.get("camera") or "—",
            dev.get("data_path") or "—",
        )

    console.print(table)


@app.command()
def start(
    host: str = typer.Option("0.0.0.0", help="Bind address"),
    port: int = typer.Option(8080, help="HTTP port"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground"),
):
    """Start the base layer and Spatial Runtime."""
    _base_start(host=host, port=port, foreground=foreground)


@app.command()
def stop():
    """Stop the base layer and Spatial Runtime."""
    _base_stop()


@app.command()
def status():
    """Show base layer status and network interfaces."""
    _base_status()


@app.command()
def pull(device: str = typer.Argument(None, help="Target device name")):
    """Pull recordings from Jetson to laptop. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@app.command()
def push():
    """Push recordings from laptop to cloud. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@app.command()
def sync(device: str = typer.Argument(None, help="Target device name")):
    """Pull from Jetson then push to cloud. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@app.command(hidden=True)
def serve(
    host: str = typer.Argument(default="0.0.0.0"),
    port: int = typer.Argument(default=8080),
):
    """Internal: run the FastAPI server (called by the daemon subprocess)."""
    from psilia_edge.runtime.server import serve as run_server

    run_server(host=host, port=port)


# ── psilia base * ─────────────────────────────────────────────────────────────


@base_app.command("start")
def base_start(
    host: str = typer.Option("0.0.0.0", help="Bind address"),
    port: int = typer.Option(8080, help="HTTP port"),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground"),
):
    """Start the base layer (daemon + web server)."""
    _base_start(host=host, port=port, foreground=foreground)


@base_app.command("stop")
def base_stop():
    """Stop the base layer."""
    _base_stop()


@base_app.command("status")
def base_status():
    """Show base layer status and network interfaces."""
    _base_status()


@base_app.command("monitor")
def base_monitor():
    """Live log view. Ctrl-C to detach (does not stop the daemon)."""
    from psilia_edge.runtime.daemon import is_running, read_log_tail

    if not is_running():
        console.print("[yellow]Base layer is not running.[/yellow] Start it with: psilia base start")
        raise typer.Exit(1)

    console.print("Monitoring psilia base layer  [dim]Ctrl-C to detach[/dim]\n")
    try:
        with Live(refresh_per_second=2, screen=False) as live:
            while True:
                live.update(_build_monitor_display(read_log_tail(30)))
                time.sleep(0.5)
    except KeyboardInterrupt:
        console.print("\n[dim]Detached. Daemon is still running.[/dim]")


# ── psilia spatial * ──────────────────────────────────────────────────────────


@spatial_app.command("start")
def spatial_start():
    """Start the Spatial Runtime (ROS layer) only. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@spatial_app.command("stop")
def spatial_stop():
    """Stop the Spatial Runtime (ROS layer) only. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


# ── helpers ───────────────────────────────────────────────────────────────────


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
    console.print("  Monitor: [bold]psilia base monitor[/bold]")


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


def _build_monitor_display(log_lines: list[str]) -> Table:
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
