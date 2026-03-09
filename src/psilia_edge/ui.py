"""Shared terminal UI helpers."""

from __future__ import annotations

from rich.console import Console, Group
from rich.padding import Padding
from rich.live import Live
from rich.spinner import Spinner
from rich.text import Text
from rich.pretty import pprint
import yaml as _yaml_mod

console = Console()

from psilia_edge import __version__ as psilia_version


psilia_version = "v" + psilia_version.replace("alpha", "α").replace("beta", "β")
# ── structural ────────────────────────────────────────────────────────────────

LOGO = """
  ▄  
▚ █ ▞
  █  
  ▀  
""".strip("\n")

HEADER = f"""
  ▄                                    
▚ █ ▞  [bold]Psilia·Edge[/bold] [dim]{psilia_version}[/dim]            
  █    Spatial Runtime for Embodied AI.
  ▀                                    
""".strip("\n")

HEADER_COLOR = f"""
[magenta]  ▄                                    
[magenta]▚ █ ▞  [bold bright_magenta]Psilia·Edge[/bold bright_magenta] [not bold]{psilia_version}            [/]
[cyan]  █    Spatial Runtime for Embodied AI.[/]
[cyan]  ▀                                    [/]
""".strip("\n")

HEADER_COLOR_LIGHT = f"""
[magenta]  ▄  [/magenta]                                  
[magenta]▚ █ ▞[/magenta]  [bold]Psilia·Edge[/bold] [not bold]{psilia_version}            [/]
[cyan]  █[/cyan]    Spatial Runtime for Embodied AI.
[cyan]  ▀[/cyan]                                    
""".strip("\n")

def _banner_bw() -> None:
    b = Padding(HEADER, (1,5), expand=False, style="")
    console.print(b, highlight=False)

def _banner_color_light() -> None:
    b = Padding(HEADER_COLOR_LIGHT, (1,5), expand=False, style="")
    console.print(Padding(b, (1,1), expand=False))

def _banner_color() -> None:
    b = Padding(HEADER_COLOR, (1,5), expand=False, style="on black")
    console.print(Padding(b, (1,1), expand=False))

def banner() -> None:
    _banner_color()


PADDING_LEFT = 2

def nav_path(path:list[str], descr=None) -> None:
    title = " → ".join([*path[:-1], f"[bold]{path[-1]}[/bold]"])
    if descr is None:
        group = Group(f"{title}")
    else:
        group = Group(f"{title}", f"[dim]{descr}[/dim]")
    console.print(Padding(group, (0,PADDING_LEFT), style="", expand=False))

HEADER_TEXT = Text()
HEADER_TEXT.append("Psilia-Edge", style="bold")
HEADER_TEXT.append(" v0.1.1\n", style="dim")
HEADER_TEXT.append("Spatial Runtime for Embodied AI.", style="dim")

def header(path:list[str], descr=None) -> None:
    """Branded header using grouped padding (original version)."""
    banner()
    nav_path(path, descr)

def done(msg: str, hint: str = "") -> None:
    """Success panel printed at the end of a command."""
    lines = f"[bold green]✓  {msg}[/bold green]"
    if hint:
        lines += f"\n[dim]{hint}[/dim]"
    console.print(Padding(lines,(3,PADDING_LEFT,2,PADDING_LEFT), expand=False))


def title(text: str) -> None:
    """Simple title line with bold text."""
    console.print(Padding(Text(text, style="bold"), (1,PADDING_LEFT), style="", expand=False))

def print_line(text: str, padding_left=PADDING_LEFT) -> None:
    """Simple line of text."""
    console.print(Padding(text, (0,padding_left), style="", expand=False))

def ask(prompt: str, default: str = "", password: bool = False) -> str:
    """Styled user prompt."""
    from rich.prompt import Prompt
    return Prompt.ask(
        f"{' '*PADDING_LEFT}{prompt}", 
        default=default, 
        password=password)

def ok(msg: str) -> None:
    """Success line: green checkmark."""
    print_line(f"[green]✓[/green] {msg}")


def fail(msg: str) -> None:
    """Failure line: red cross."""
    print_line(f"[red]✗[/red] {msg}")


def warn(msg: str) -> None:
    """Warning line: yellow triangle."""
    print_line(f"[yellow]⚠[/yellow] {msg}")

def stub(msg: str = "not yet implemented") -> None:
    """Placeholder for unimplemented steps."""
    print_line(f"[dim yellow]▢[/dim yellow] {msg}")




def status(msg: str) -> None:
    """Status line with custom psilia spinner."""
    return Live(
            Padding(Spinner("dots", text=msg, style="bright_magenta"), (0,PADDING_LEFT), expand=False),
            console=console,
            transient=True,
            refresh_per_second=12.5,
    )

def info(msg: str) -> None:
    """Indented descriptive text."""
    print_line(f"{msg}")

def fyi(msg: str) -> None:
    print_line(f"[dim](FYI: {msg})[/dim]")

def item(msg: str) -> None:
    """List item with a dim arrow."""
    print_line(f"[dim]→[/dim]  {msg}", padding_left=PADDING_LEFT )


def detail(key: str, value: str) -> None:
    """Key/value config detail line."""
    print_line(f"[dim]{key}:[/dim]  {value}", padding_left=PADDING_LEFT)

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
    nav_path(["Device Manager", "Pair with Device"], 
        "Pair a Jetson: connect, generate SSH keypair, register device.")

    _banner_color()
    nav_path(["Device Manager", "Pair with Device"], 
        "Pair a Jetson: connect, generate SSH keypair, register device.")
    
    header(["Device Manager", "Pair with Device"],
           "Pair a Jetson: connect, generate SSH keypair, register device.")
    
    title("A section header")
    print_line("a simple line of text")
    print_line("another line")
    info("Connecting to the Jetson over SSH. (info)")
    info("Trying [bold]192.168.1.42[/bold]… (info)")
    stub("detect SSD, confirm mount point, configure /etc/fstab (stub)")
    import time
    with status("Connecting to 192.168.1.42… (status)"):
        time.sleep(0.5)
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

    r = ask("hello enter", default = "testing", password = True)
    console.print(r)
    console.print(type(r))

if __name__ == "__main__":
    _demo()
