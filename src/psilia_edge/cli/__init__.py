import time
from pathlib import Path
from typing import Optional, Annotated

import typer
from rich.console import Console
from rich.live import Live
from rich.padding import Padding


console = Console()

app = typer.Typer(help="Psilia Edge — spatial perception runtime for edge devices")
base_app = typer.Typer(help="Manage the base layer (daemon + web server)")
spatial_app = typer.Typer(help="Manage the Spatial Runtime (ROS nodes)")

app.add_typer(base_app, name="base", hidden=True)
app.add_typer(spatial_app, name="spatial", hidden=True)


# ── print helper commands ─────────────────────────────────────────────────────
def _print_section(title: str, content: str) -> None:
    console.rule(f"[bold]'{title}'", align="center")
    console.print(Padding(content, 1))


def _print_file(fname: str | Path) -> None:
    fname = Path(fname)
    if fname.exists():
        _print_section(fname, fname.read_text())
    else:
        _print_section(fname, f"[dim]{str(fname)} not found[/dim]")


@app.command(hidden=True)
def debug():
    """Show internal state, adapts to role (runtime host vs device manager)."""
    from psilia_edge.config import is_runtime_host

    if is_runtime_host():
        _debug_runtime_host()
    else:
        _debug_device_manager()


def _debug_runtime_host() -> None:
    from psilia_edge.config import JETSON_CONFIG_PATH
    _print_file(JETSON_CONFIG_PATH)


def _debug_device_manager() -> None:
    from psilia_edge.config import LAPTOP_CONFIG_PATH
    from psilia_edge.pair import _SSH_CONFIG_PATH, _SSH_SECTION_END, _SSH_SECTION_START

    _print_file(LAPTOP_CONFIG_PATH)

    if _SSH_CONFIG_PATH.exists():
        text = _SSH_CONFIG_PATH.read_text()
        if _SSH_SECTION_START in text:
            start = text.index(_SSH_SECTION_START)
            end = text.index(_SSH_SECTION_END) + len(_SSH_SECTION_END)
            _print_section(
                _SSH_CONFIG_PATH, 
                text[start:end])
        else:
            _print_section(
                _SSH_CONFIG_PATH, 
                "[dim]No psilia section found[/dim]")
    else:
        _print_section(
            _SSH_CONFIG_PATH, 
            f"[dim]{_SSH_CONFIG_PATH} not found[/dim]")

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   DEVICE MANAGEMENT COMMANDS
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
@app.command(rich_help_panel="Device Management")
def pair():
    """Pair a Jetson: connect, generate SSH keypair, register device on this laptop."""
    from psilia_edge.pair import run_pair_wizard

    run_pair_wizard()


# def setup(device: Optional[str] = typer.Argument(None, help="Registered device name")):
@app.command(rich_help_panel="Device Management")
def setup(device: Annotated[str, typer.Argument(help="Registered device name")]):
    """Bootstrap a Jetson device."""
    # TODO: eventually we may want to support local setup from the laptop as well.
    # But for that, we'd need to first install psilia_edge on the device. So probably there will 
    # be an install script that installs psilia_edge and then calls this setup command locally.
    if device:
        from psilia_edge.setup import run_setup_remote
        run_setup_remote(device)
    else:
        console.print(
            "[red]No device specified.[/red]\n"
            "  On a laptop: [bold]psilia setup <device>[/bold]\n"
            "  Run [bold]psilia devices[/bold] to see registered devices."
        )


@app.command(rich_help_panel="Device Management")
def devices():
    """List all registered Jetson devices."""
    from psilia_edge.config import read_laptop_config

    config = read_laptop_config()
    devs = config.get("devices", {})

    if not devs:
        console.print("[dim]No devices registered. Run 'psilia pair' to add one.[/dim]")
        return

    from rich.table import Table
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

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   RUNTIME COMMANDS
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
@app.command(rich_help_panel="Runtime")
def start(
    device: Optional[str] = typer.Argument(None, help="Registered device name (SSH wrapper)"),
    host: str = typer.Option("0.0.0.0", help="Bind address", hidden=True),
    port: int = typer.Option(8080, help="HTTP port", hidden=True),
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground", hidden=True),
):
    """Start the runtime. With <device>: SSH wrapper for a registered device."""
    from psilia_edge.runtime.commands import _base_start, _require_runtime_host, _ssh_run

    if device:
        _ssh_run(device, "start")
    else:
        _require_runtime_host("start <device>")
        _base_start(host=host, port=port, foreground=foreground)


@app.command(rich_help_panel="Runtime")
def stop(
    device: Optional[str] = typer.Argument(None, help="Registered device name (SSH wrapper)"),
):
    """Stop the runtime. With <device>: SSH wrapper for a registered device."""
    from psilia_edge.runtime.commands import _base_stop, _require_runtime_host, _ssh_run

    if device:
        _ssh_run(device, "stop")
    else:
        _require_runtime_host("stop <device>")
        _base_stop()


@app.command(rich_help_panel="Runtime")
def status(
    device: Optional[str] = typer.Argument(None, help="Registered device name (SSH wrapper)"),
):
    """Show runtime status. With <device>: SSH wrapper for a registered device."""
    from psilia_edge.runtime.commands import _base_status, _require_runtime_host, _ssh_run

    if device:
        _ssh_run(device, "status")
    else:
        _require_runtime_host("status <device>")
        _base_status()


@app.command("monitor", rich_help_panel="Runtime")
def monitor(
    device: Optional[str] = typer.Argument(None, help="Registered device name (SSH wrapper)"),
):
    """Live log view. Ctrl-C to detach. With <device>: SSH wrapper for a registered device."""
    from psilia_edge.runtime.commands import _build_monitor_display, _require_runtime_host, _ssh_exec
    from psilia_edge.runtime.daemon import is_running, read_log_tail

    if device:
        _ssh_exec(device, "monitor")
        return

    _require_runtime_host("monitor <device>")

    if not is_running():
        console.print("[yellow]Base layer is not running.[/yellow] Start it with: psilia start")
        raise typer.Exit(1)

    console.print("Monitoring psilia base layer  [dim]Ctrl-C to detach[/dim]\n")
    try:
        with Live(refresh_per_second=2, screen=False) as live:
            while True:
                live.update(_build_monitor_display(read_log_tail(30)))
                time.sleep(0.5)
    except KeyboardInterrupt:
        console.print("\n[dim]Detached. Daemon is still running.[/dim]")

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   DATA MANAGEMENT COMMANDS
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
@app.command(rich_help_panel="Data Management")
def pull(device: str = typer.Argument(None, help="Target device name")):
    """Pull recordings from Jetson to laptop. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@app.command(hidden=True)
def serve(
    host: str = typer.Argument(default="0.0.0.0"),
    port: int = typer.Argument(default=8080),
):
    """Internal: run the FastAPI server (called by the daemon subprocess)."""
    from psilia_edge.runtime.server import serve as run_server

    run_server(host=host, port=port)
