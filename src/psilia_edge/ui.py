"""Shared terminal UI helpers."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.padding import Padding
from rich.console import Group
from rich.rule import Rule


console = Console()


def _ok(msg: str) -> None:
    console.print(f"  [green]✓[/green] {msg}")


def _fail(msg: str) -> None:
    console.print(f"  [red]✗[/red] {msg}")


def _stub(msg: str = "not yet implemented") -> None:
    console.print(f"  [dim]({msg})[/dim]")


def _header_panel(title: str,  msg: str = "") -> None:
    console.print(
        Panel(
            f"Ψ PSILIA Edge\n"
            f"[bold]{title}[/bold]\n" 
            f"{msg}",
            style="on #0d1f2d", 
            expand=False,
            border=None,
        )
    )

HEADER_TEXT = Text() 
HEADER_TEXT.append("Psilia-Edge", style="bold")
HEADER_TEXT.append(" v0.1.1\n", style="dim")
HEADER_TEXT.append("Spatial Runtime for Embodied AI.", style="dim")

def _header(title: str,  msg: str = "") -> None:

    p1 = Padding(HEADER_TEXT, (1,1,1,3), style="", expand=False)
    p2 = Padding(Group(title, msg), (0,1,0,3), style="", expand=False)

    g = Group(p1, p2)
    console.print(g)


