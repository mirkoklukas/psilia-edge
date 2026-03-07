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
    from psilia_edge.runtime.core import is_runtime_host

    if is_runtime_host():
        _debug_runtime_host()
    else:
        _debug_device_manager()


def _debug_runtime_host() -> None:
    from psilia_edge.runtime.core import RUNTIME_CONFIG_PATH
    _print_file(RUNTIME_CONFIG_PATH)


def _debug_device_manager() -> None:
    from psilia_edge.device_manager.core import CONFIG_PATH
    from psilia_edge.device_manager.pair import _SSH_CONFIG_PATH, _SSH_SECTION_END, _SSH_SECTION_START

    _print_file(CONFIG_PATH)

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
    from psilia_edge.device_manager.pair import run_pair_wizard

    run_pair_wizard()


_SETUP_SCRIPT_URL = "https://raw.githubusercontent.com/mirkoklukas/psilia-edge/main/scripts/setup.sh"


@app.command(rich_help_panel="Device Management")
def setup(device: Annotated[str, typer.Argument(help="Registered device name")]):
    """Bootstrap a Jetson device over SSH by running setup.sh on the device."""
    import os
    import shlex
    from rich.prompt import Prompt

    config = None
    try:
        from psilia_edge.device_manager.config import read_config
        config = read_config()
    except Exception:
        pass

    if config and device not in config.get("devices", {}):
        console.print(f"[red]Device '{device}' not registered.[/red] Run 'psilia pair' first.")
        raise typer.Exit(1)

    install_dir = Prompt.ask("  Install directory on device", default="/ssd/psilia")
    cmd = f"curl -fsSL {_SETUP_SCRIPT_URL} | bash -s -- --install-dir {shlex.quote(install_dir)}"
    ssh_argv = ["ssh", "-t", device, "bash", "-lc", f"'{cmd}'"]
    os.execvp("ssh", ssh_argv)


@app.command(rich_help_panel="Device Management")
def update(device: Annotated[str, typer.Argument(help="Registered device name")]):
    """Pull latest psilia-edge and rebuild the Docker image on a device."""
    from psilia_edge.device_manager.config import read_config
    from psilia_edge.device_manager.ssh import SSHError, connect
    from psilia_edge.runtime.setup import _step_pull, _step_build_image

    config = read_config()
    devices = config.get("devices", {})
    if device not in devices:
        console.print(f"[red]Device '{device}' not registered.[/red] Run 'psilia pair' first.")
        raise typer.Exit(1)

    dev = devices[device]
    host, user, key = dev["host"], dev["user"], dev.get("key")
    base = dev.get("install_dir", "/ssd/psilia")

    from psilia_edge import ui
    ui.header(f"psilia update — {device}", f"[dim]Updating over SSH as {user}@{host}[/dim]")
    try:
        with console.status("  Connecting…"):
            conn = connect(host, user=user, key=key)
    except SSHError as exc:
        console.print(f"[red]SSH connection failed:[/red] {exc}")
        raise typer.Exit(1)

    with conn:
        if not _step_pull(conn, base):
            raise typer.Exit(1)
        _step_build_image(conn, base)

    ui.done(
        f"{device} updated.",
        f"Run [bold]psilia start {device}[/bold] to restart the runtime.",
    )


@app.command(rich_help_panel="Device Management")
def devices():
    """List all registered Jetson devices."""
    from psilia_edge.device_manager.config import read_config

    config = read_config()
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
    from psilia_edge.runtime.cli import base_start
    from psilia_edge.runtime.core import require_runtime_host
    from psilia_edge.device_manager.ssh import ssh_on_device

    if device:
        ssh_on_device(device, "start")
    else:
        require_runtime_host("start <device>")
        base_start(host=host, port=port, foreground=foreground)


@app.command(rich_help_panel="Runtime")
def stop(
    device: Optional[str] = typer.Argument(None, help="Registered device name (SSH wrapper)"),
):
    """Stop the runtime. With <device>: SSH wrapper for a registered device."""
    from psilia_edge.runtime.cli import base_stop
    from psilia_edge.runtime.core import require_runtime_host
    from psilia_edge.device_manager.ssh import ssh_on_device

    if device:
        ssh_on_device(device, "stop")
    else:
        require_runtime_host("stop <device>")
        base_stop()


@app.command(rich_help_panel="Runtime")
def status(
    device: Optional[str] = typer.Argument(None, help="Registered device name (SSH wrapper)"),
):
    """Show runtime status. With <device>: SSH wrapper for a registered device."""
    from psilia_edge.runtime.cli import base_status
    from psilia_edge.runtime.core import require_runtime_host
    from psilia_edge.device_manager.ssh import ssh_on_device

    if device:
        ssh_on_device(device, "status")
    else:
        require_runtime_host("status <device>")
        base_status()


@app.command("attach", rich_help_panel="Runtime")
def attach(
    device: Optional[str] = typer.Argument(None, help="Registered device name (SSH wrapper)"),
):
    """Attach to the running daemon log. Ctrl-C to detach. With <device>: SSH wrapper for a registered device."""
    from psilia_edge.runtime.cli import build_monitor_display
    from psilia_edge.runtime.core import require_runtime_host
    from psilia_edge.runtime.daemon import is_running, read_log_tail
    from psilia_edge.device_manager.ssh import ssh_on_device

    if device:
        ssh_on_device(device, "attach", replace_process=True)
        return

    require_runtime_host("attach <device>")

    if not is_running():
        console.print("[yellow]Base layer is not running.[/yellow] Start it with: psilia start")
        raise typer.Exit(1)

    console.print("Monitoring psilia base layer  [dim]Ctrl-C to detach[/dim]\n")
    try:
        with Live(refresh_per_second=2, screen=False) as live:
            while True:
                live.update(build_monitor_display(read_log_tail(30)))
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
