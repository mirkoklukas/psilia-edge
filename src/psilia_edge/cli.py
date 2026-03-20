# Naming convention:
#   function   — CLI command (registered with @app.command)
#   _function  — helper (returns data, wraps logic, not a command itself)
#
# When calling into runtime/cli.py:
#   no leading underscore → acts as a command (owns output, side effects)
#   leading underscore    → helper (returns a value or renderable we use here)

from pathlib import Path

import typer
from rich.console import Console
from rich.padding import Padding

from psilia_edge.runtime.cli import app as runtime_app

console = Console()

app = typer.Typer(help="Psilia Edge — spatial perception runtime for edge devices")

app.add_typer(
    runtime_app,
    name="runtime",
    help="Commands to operate the runtime on Jetson devices",
)

# ── data sub-app ──────────────────────────────────────────────────────────────
data_app = typer.Typer(help="Data operations (pull, sync)")
app.add_typer(data_app, name="data")


@data_app.command()
def pull(
    device: str = typer.Argument(
        None,
        help="Registered device name. Pulls from all registered devices if not specified.",
    ),
    to: Path = typer.Option(
        None,
        "--to",
        help="Local destination directory. Overrides data.pull_to in psilia.yaml (not saved).",
    ),
) -> None:
    """Pull recorded MCAP data from a device to the local machine."""
    from psilia_edge.device_manager.data import pull_from_device, resolve_pull_to
    from psilia_edge.runtime.config import read_config

    pull_to = resolve_pull_to(to)

    devices = (
        [device] if device else list(read_config().get("registered_devices", {}).keys())
    )

    if not devices:
        console.print(
            "[dim]No registered devices. Run 'psilia runtime pair' to add one.[/dim]"
        )
        raise typer.Exit(1)

    for dev in devices:
        console.rule(f"[bold]{dev}")
        console.print(f"[dim]→ {pull_to}[/dim]")
        rc = pull_from_device(dev, pull_to)
        if rc != 0:
            console.print(f"[red]✗ pull from {dev} failed (exit {rc})[/red]")
        else:
            console.print("[green]✓ done[/green]")


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
    from psilia_edge.runtime.config import CONFIG_PATH

    _print_file(CONFIG_PATH)


def _debug_device_manager() -> None:
    from psilia_edge.runtime.config import CONFIG_PATH
    from psilia_edge.device_manager.config import (
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
