"""Shared terminal UI helpers."""

from __future__ import annotations

from rich.console import Console, Group
from rich.columns import Columns
from rich.padding import Padding
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.pretty import pprint
import yaml as _yaml_mod

console = Console()

# ── structural ────────────────────────────────────────────────────────────────

LOGO = """
  ▄  
▚ █ ▞
  █  
  ▀  
""".strip("\n")

HEADER = """
  ▄                                    
▚ █ ▞  [bold]Psilia·Edge[/bold] [dim]v0.1.0-α[/dim]            
  █    Spatial Runtime for Embodied AI.
  ▀                                    
""".strip("\n")

HEADER_COLOR = """
[magenta]  ▄                                    
[magenta]▚ █ ▞  [bold bright_magenta]Psilia·Edge[/bold bright_magenta] [not bold]v0.1.0-α            [/]
[cyan]  █    Spatial Runtime for Embodied AI.[/]
[cyan]  ▀                                    [/]
""".strip("\n")

def _banner_bw() -> None:
    b = Padding(HEADER, (1,5), expand=False, style="")
    console.print(b, highlight=False)

def _banner_color() -> None:
    b = Padding(HEADER_COLOR, (1,5), expand=False, style="on black")
    console.print(Padding(b, (1,1), expand=False))

def banner() -> None:
    _banner_color()
        
def nav(items, descr="") -> None:
    title = " → ".join([*items[:-1], f"[bold]{items[-1]}[/bold]"])
    group = Group(title, f"[dim]{descr}[/dim]")
    console.print(Padding(group, (0,2), style="", expand=False))

HEADER_TEXT = Text()
HEADER_TEXT.append("Psilia-Edge", style="bold")
HEADER_TEXT.append(" v0.1.1\n", style="dim")
HEADER_TEXT.append("Spatial Runtime for Embodied AI.", style="dim")

def header(title: str, msg: str = "") -> None:
    """Branded header using grouped padding (original version)."""
    p1 = Padding(HEADER_TEXT, (2, 1, 1, 6), style="magenta", expand=False)
    p2 = Padding(Group(title, msg), (0, 1, 2, 6), style="cyan", expand=False)
    r = Rule(style="cyan")
    # console.print(Panel(Group(p1, p2), expand=False, border_style="", style=""))
    console.print(Group(p1, p2))


def section_header(title: str) -> None:
    """Cyan rule used to open a wizard step or named section."""
    # console.print(Rule(f"[bold]{title}[/bold]", style="cyan", align="left"))
    console.print(Padding(Text(title, style="bold"), (1,1,1,2), style="", expand=False))


def done(msg: str, hint: str = "") -> None:
    """Success panel printed at the end of a command."""
    lines = f"[bold green]✓  {msg}[/bold green]"
    if hint:
        lines += f"\n[dim]{hint}[/dim]"
    # console.print(Panel(lines, border_style="green", expand=False, padding=(1, 3)))
    console.print(Padding(lines,(3,6,2,6), expand=False))



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


# ── status indicators ─────────────────────────────────────────────────────────

def ok(msg: str) -> None:
    """Success line: green checkmark."""
    console.print(f"  [green]✓[/green] {msg}")


def fail(msg: str) -> None:
    """Failure line: red cross."""
    console.print(f"  [red]✗[/red] {msg}")


def warn(msg: str) -> None:
    """Warning line: yellow triangle."""
    console.print(f"  [yellow]⚠[/yellow]  {msg}")


def stub(msg: str = "not yet implemented") -> None:
    """Placeholder for unimplemented steps."""
    console.print(f"  [dim italic]({msg})[/dim italic]")


# ── content helpers ───────────────────────────────────────────────────────────

def info(msg: str) -> None:
    """Indented descriptive text."""
    console.print(f"  {msg}")


def item(msg: str) -> None:
    """List item with a dim arrow."""
    console.print(f"    [dim]→[/dim]  {msg}")


def detail(key: str, value: str) -> None:
    """Key/value config detail line."""
    console.print(f"    [dim]{key}:[/dim]  {value}")

def _dict(d: dict) -> None:
    """Pretty-print a dictionary with rich's pprint."""
    pprint(d, expand_all=True, console=console, indent_guides=False)

def _yaml2(d) -> None:
    console.print(
        Padding(
            _yaml_mod.dump(d, default_flow_style=False),
            (2, 2),
        )
    )


def build_tree(
        d: dict,
        label: str = "",
        key_style: str = "cyan",
        value_style: str = "normal",
        label_style: str = "magenta",
        guide_style: str = "dim cyan",
    ):
    """Build and return a Rich Tree from a nested dict (without printing)."""
    from rich.tree import Tree

    def _add(node, d: dict) -> None:
        for key, value in d.items():
            if isinstance(value, dict):
                branch = node.add(f"[{key_style}]{key}[/{key_style}]")
                _add(branch, value)
            elif isinstance(value, list):
                branch = node.add(f"[{key_style}]{key}[/{key_style}]")
                for it in value:
                    if isinstance(it, dict):
                        _add(branch, it)
                    else:
                        branch.add(f"[{value_style}]{it}[/{value_style}]")
            else:
                node.add(f"[{key_style}]{key}:[/{key_style}] [{value_style}]{value}[/{value_style}]")

    tree = Tree(Padding(label, (0, 0, 1, 0), style=label_style, expand=False), guide_style=guide_style)
    _add(tree, d)
    return Padding(tree, (2, 2))


def print_tree(
        d: dict,
        label: str = "",
        key_style: str = "cyan",
        value_style: str = "normal",
        label_style: str = "magenta",
        guide_style: str = "dim cyan",
    ) -> None:
    """Display a nested dict as a Rich Tree."""
    console.print(build_tree(d, label=label, key_style=key_style, value_style=value_style,
                              label_style=label_style, guide_style=guide_style))


def print_yaml(d: dict, key_color="") -> None:
    """YAML-like dict printer with bold keys (Rich markup)."""
    def _collect(d: dict, indent: int) -> list[str]:
        lines = []
        pad = "\t" * indent
        for key, value in d.items():
            if isinstance(value, dict):
                lines.append(f"{pad}[bold {key_color}]{key}:[/bold {key_color}]")
                lines.extend(_collect(value, indent + 1))
            elif isinstance(value, list):
                lines.append(f"{pad}[bold {key_color}]{key}:[/bold {key_color}]")
                for item in value:
                    if isinstance(item, dict):
                        lines.append(f"{pad}  -")
                        lines.extend(_collect(item, indent + 2))
                    else:
                        lines.append(f"{pad}  - {item}")
            else:
                lines.append(f"{pad}[bold {key_color}]{key}:[/bold {key_color}] {value}")
        return lines

    console.print("\n".join(_collect(d, 0)))






# ── demo ─────────────────────────────────────────────────────────────────────

def _demo() -> None:
    """Print a fake wizard flow to preview all UI helpers."""
    _banner_bw()
    nav(["Device Manager", "Pair with Device"], 
        "Pair a Jetson: connect, generate SSH keypair, register device.")


    _banner_color()
    nav(["Device Manager", "Pair with Device"], 
        "Pair a Jetson: connect, generate SSH keypair, register device.")
    
    console.print(Padding("Device Manager → [bold]Pair with Device[/bold]", (1,1), style="", expand=False))
    header("Device Manager → [bold]Pair with Device[/bold]",
           "[dim]Pair a Jetson: connect, generate SSH keypair, register device.[/dim]")

    section_header("A section header")
    info("Connecting to the Jetson over SSH. (info)")
    info("Trying [bold]192.168.1.42[/bold]… (info)")
    stub("detect SSD, confirm mount point, configure /etc/fstab (stub)")
    ok("Connected to 192.168.1.42 (ok)")
    detail("connect with", "ssh psilia-jetson (detail)")
    fail("Failed to connect to 192.168.1.42 (fail)")
    item("Try again with the hotspot IP (item)")
    warn("No USB wifi dongle found — falling back to built-in wifi. (warn)")

    done(
        "psilia-jetson paired.",
        "Run [bold]psilia setup psilia-jetson[/bold] to bootstrap the runtime.",
    )

    config = {
        "device": {
            "name": "psilia-jetson",
            "host": "psilia-jetson.local",
            "user": "nvidia",
        },
        "status": "paired",
        "nested": [1, 2 ,{"x": [3,4]}],

    }   

    print_tree(config, label="Config")

if __name__ == "__main__":
    _demo()
