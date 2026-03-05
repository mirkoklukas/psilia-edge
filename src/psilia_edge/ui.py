"""Shared terminal UI helpers."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel


console = Console()


def _ok(msg: str) -> None:
    console.print(f"  [green]✓[/green] {msg}")


def _fail(msg: str) -> None:
    console.print(f"  [red]✗[/red] {msg}")


def _stub(msg: str = "not yet implemented") -> None:
    console.print(f"  [dim]({msg})[/dim]")


def _header(title, msg) -> None:
    console.print(
        Panel(
            f"[Ψ] [bold]{title}[/bold]\n"
            f"{msg}",
            expand=False,
            border_style="cyan",
        )
    )