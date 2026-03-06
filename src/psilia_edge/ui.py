"""Shared terminal UI helpers."""

from __future__ import annotations

from rich.console import Console, Group
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text

console = Console()

# ── status indicators ─────────────────────────────────────────────────────────

def _ok(msg: str) -> None:
    """Success line: green checkmark."""
    console.print(f"  [green]✓[/green] {msg}")


def _fail(msg: str) -> None:
    """Failure line: red cross."""
    console.print(f"  [red]✗[/red] {msg}")


def _warn(msg: str) -> None:
    """Warning line: yellow triangle."""
    console.print(f"  [yellow]⚠[/yellow]  {msg}")


def _stub(msg: str = "not yet implemented") -> None:
    """Placeholder for unimplemented steps."""
    console.print(f"  [dim italic]({msg})[/dim italic]")


# ── content helpers ───────────────────────────────────────────────────────────

def _info(msg: str) -> None:
    """Indented descriptive text."""
    console.print(f"  {msg}")


def _item(msg: str) -> None:
    """List item with a dim arrow."""
    console.print(f"    [dim]→[/dim]  {msg}")


def _detail(key: str, value: str) -> None:
    """Key/value config detail line."""
    console.print(f"    [dim]{key}:[/dim]  {value}")


# ── structural ────────────────────────────────────────────────────────────────

HEADER_TEXT = Text()
HEADER_TEXT.append("Psilia-Edge", style="bold")
HEADER_TEXT.append(" v0.1.1\n", style="dim")
HEADER_TEXT.append("Spatial Runtime for Embodied AI.", style="dim")

def _header(title: str, msg: str = "") -> None:
    """Branded header using grouped padding (original version)."""
    p1 = Padding(HEADER_TEXT, (2, 1, 1, 6), style="magenta", expand=False)
    p2 = Padding(Group(title, msg), (0, 1, 2, 6), style="cyan", expand=False)
    r = Rule(style="cyan")
    console.print(Panel(Group(p1, p2), expand=False, border_style=""))
    # console.print(Group(p1, p2))


def _section_header(title: str) -> None:
    """Cyan rule used to open a wizard step or named section."""
    # console.print(Rule(f"[bold]{title}[/bold]", style="cyan", align="left"))
    console.print(Padding(Text(title, style="bold"), (1,1,1,2), style="", expand=False))



def _header_panel(title: str, msg: str = "") -> None:
    """Branded header as a dark panel (original version)."""
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

def _header2(title: str, subtitle: str = "") -> None:
    """Branded command header as a cyan panel."""
    brand = Text()
    brand.append("Ψ  Psilia Edge", style="bold")
    brand.append("  v0.1", style="dim")

    body = Text()
    body.append(title, style="bold")
    if subtitle:
        body.append(f"\n{subtitle}", style="dim")

    content = Group(
        Padding(brand, (0, 0, 0, 0)),
        Text(""),
        Padding(body, (0, 0, 0, 0)),
    )
    console.print(Panel(content, border_style="cyan", expand=False, padding=(1, 3)))


def _done(msg: str, hint: str = "") -> None:
    """Success panel printed at the end of a command."""
    lines = f"[bold green]✓  {msg}[/bold green]"
    if hint:
        lines += f"\n[dim]{hint}[/dim]"
    console.print(Panel(lines, border_style="green", expand=False, padding=(1, 3)))


# ── demo ─────────────────────────────────────────────────────────────────────

def _demo() -> None:
    """Print a fake wizard flow to preview all UI helpers."""
    _header("Device Manager → [bold]Pair with Device[/bold]", 
            "[dim]Pair a Jetson: connect, generate SSH keypair, register device.[/dim]")

    _section_header("Step 1 — Connect")
    _info("Connecting to the Jetson over SSH.")
    _info("Trying [bold]192.168.1.42[/bold]…")
    _ok("Connected to 192.168.1.42")
    console.print()

    _section_header("Step 2 — Device Name")
    _info("[dim]Changing the name will update the Jetson hostname and /etc/hosts.[/dim]")
    _info("Current hostname: [bold]nvidia-jetson[/bold]")
    _ok("Hostname set to 'psilia-jetson'")
    console.print()

    _section_header("Step 3 — SSH Keypair")
    _ok("Keypair saved to ~/.psilia/keys/psilia-jetson")
    _ok("Public key installed on Jetson (~/.ssh/authorized_keys)")
    console.print()

    _section_header("Step 4 — SSH Config")
    _ok("SSH config updated (~/.ssh/config)")
    _item(f"Host psilia-jetson         → psilia-jetson.local")
    _item(f"Host psilia-jetson-hotspot → 10.42.0.1")
    _detail("connect with", "ssh psilia-jetson")
    console.print()

    _section_header("Step 5 — Register Device")
    _ok("Device registered in ~/.psilia/config.yaml")
    _detail("name", "psilia-jetson")
    _detail("host", "psilia-jetson.local")
    _detail("user", "nvidia")
    console.print()

    _section_header("Step 6 — Stubbed Step")
    _stub("detect SSD, confirm mount point, configure /etc/fstab")
    _warn("No USB wifi dongle found — falling back to built-in wifi.")
    _fail("Could not reach device at 10.42.0.1")
    console.print()

    _done(
        "psilia-jetson paired.",
        "Run [bold]psilia setup psilia-jetson[/bold] to bootstrap the runtime.",
    )
    console.print()


if __name__ == "__main__":
    _demo()
