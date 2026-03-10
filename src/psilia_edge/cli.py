# Naming convention:
#   function   — CLI command (registered with @app.command)
#   _function  — helper (returns data, wraps logic, not a command itself)
#
# When calling into runtime/cli.py:
#   no leading underscore → acts as a command (owns output, side effects)
#   leading underscore    → helper (returns a value or renderable we use here)

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.padding import Padding

from psilia_edge.runtime.config import DEFAULT_BASE_DIR
from psilia_edge.runtime.cli import app as runtime_app

console = Console()

app = typer.Typer(help="Psilia Edge — spatial perception runtime for edge devices")

_DEFAULT_INSTALL_DIR = DEFAULT_BASE_DIR.parent

app.add_typer(
    runtime_app,
    name="runtime",
    help="Commands to operate the runtime on Jetson devices",
)

app.add_typer(
    runtime_app,
    name="rt",
    help="Alias for 'runtime' commands (e.g. 'psilia rt start <device>')",
)


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
    from psilia_edge.runtime.config import DEVICE_CONFIG_PATH

    _print_file(DEVICE_CONFIG_PATH)


def _debug_device_manager() -> None:
    from psilia_edge.device_manager.config import CONFIG_PATH
    from psilia_edge.device_manager.pair import (
        _SSH_CONFIG_PATH,
        _SSH_SECTION_END,
        _SSH_SECTION_START,
    )

    _print_file(CONFIG_PATH)

    if _SSH_CONFIG_PATH.exists():
        text = _SSH_CONFIG_PATH.read_text()
        if _SSH_SECTION_START in text:
            start = text.index(_SSH_SECTION_START)
            end = text.index(_SSH_SECTION_END) + len(_SSH_SECTION_END)
            _print_section(_SSH_CONFIG_PATH, text[start:end])
        else:
            _print_section(_SSH_CONFIG_PATH, "[dim]No psilia section found[/dim]")
    else:
        _print_section(_SSH_CONFIG_PATH, f"[dim]{_SSH_CONFIG_PATH} not found[/dim]")


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


# Path to bootstrap.py in the repo — works for editable installs (src layout).
_BOOTSTRAP_PY = Path(__file__).parent.parent.parent / "scripts" / "bootstrap.py"


@app.command(rich_help_panel="Device Management")
def bootstrap(device: Annotated[str, typer.Argument(help="Registered device name")]):
    """Bootstrap a Jetson over SSH: streams bootstrap.py via base64 + process substitution.

    The script is base64-encoded and embedded in the SSH command, then decoded on the
    remote via process substitution — so stdin stays as the terminal and the setup
    wizard runs interactively in one shot.
    """
    import base64
    from psilia_edge.ui import ask
    from psilia_edge.utils import run_on_device

    if not _BOOTSTRAP_PY.exists():
        console.print(f"[red]bootstrap.py not found at {_BOOTSTRAP_PY}[/red]")
        raise typer.Exit(1)

    install_dir = ask("Install directory on device", default=str(_DEFAULT_INSTALL_DIR))

    encoded = base64.b64encode(_BOOTSTRAP_PY.read_bytes()).decode()
    cmd = f"python3 <(echo '{encoded}' | base64 -d) {install_dir}"
    run_on_device(device, cmd, replace_process=True)


@app.command(rich_help_panel="Device Management", hidden=True)
def broken_bootstrap(
    device: Annotated[str, typer.Argument(help="Registered device name")],
):
    """Broken bootstrap — pipes script via stdin so interactive prompts get EOF.

    Demonstrates the stdin conflict: bootstrap runs fine but the setup wizard
    at the end cannot read user input because stdin is the exhausted pipe.
    """
    import subprocess
    from psilia_edge.ui import ask

    if not _BOOTSTRAP_PY.exists():
        console.print(f"[red]bootstrap.py not found at {_BOOTSTRAP_PY}[/red]")
        raise typer.Exit(1)

    install_dir = ask("Install directory on device", default=str(_DEFAULT_INSTALL_DIR))

    # Pipe the script via stdin. SSH warns "Pseudo-terminal will not be allocated
    # because stdin is not a terminal" and the setup wizard at the end gets EOF
    # on stdin — interactive prompts fail or silently receive empty input.
    script = _BOOTSTRAP_PY.read_text()
    subprocess.run(
        ["ssh", "-t", device, f"python3 - {install_dir}"],
        input=script,
        text=True,
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
