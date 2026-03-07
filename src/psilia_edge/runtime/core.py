"""Runtime utilities shared across the runtime package."""

from __future__ import annotations

from pathlib import Path

RUNTIME_CONFIG_PATH = Path("/opt/psilia/runtime_config.yaml")


def is_runtime_host() -> bool:
    """Return True if this machine is a runtime host (Jetson).

    Heuristic: runtime_config.yaml only exists after `psilia setup` has run.
    """
    return RUNTIME_CONFIG_PATH.exists()


def require_runtime_host(device_hint: str) -> None:
    """Exit with a clear message if not running on a runtime host (Jetson)."""
    import typer
    from psilia_edge.ui import console

    if not is_runtime_host():
        console.print(
            f"[red]This command only runs on a Jetson.[/red]\n"
            f"  To target a registered device: [bold]psilia {device_hint}[/bold]"
        )
        raise typer.Exit(1)
