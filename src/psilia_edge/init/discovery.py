"""ARP-based Jetson discovery on the local ethernet interface."""

from __future__ import annotations

import re
import subprocess

from rich.console import Console
from rich.prompt import Prompt

console = Console()

# arp -a output line:  hostname (ip) at mac [ether] on iface
_ARP_RE = re.compile(r"^(\S+)\s+\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+\S+.*\s+on\s+(\S+)", re.MULTILINE)


def _parse_arp(output: str, iface: str | None) -> list[tuple[str, str]]:
    """Return list of (hostname, ip) found in arp output, optionally filtered by iface."""
    results = []
    for m in _ARP_RE.finditer(output):
        hostname, ip, found_iface = m.group(1), m.group(2), m.group(3)
        if iface and found_iface != iface:
            continue
        results.append((hostname, ip))
    return results


def _run_arp() -> str:
    try:
        result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=5)
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def discover_jetson(iface: str | None = None) -> str | None:
    """Scan ARP table and return an IP address to connect to.

    If exactly one host is found, returns it automatically.
    If multiple are found, prompts the user to choose.
    Returns None if nothing is found.
    """
    with console.status("Scanning ARP table for devices…"):
        arp_output = _run_arp()

    hosts = _parse_arp(arp_output, iface)

    if not hosts:
        iface_note = f" on interface [bold]{iface}[/bold]" if iface else ""
        console.print(f"  [yellow]No hosts found{iface_note}.[/yellow]")
        console.print("  Make sure the Jetson is powered on and the ethernet cable is connected.")
        return None

    if len(hosts) == 1:
        hostname, ip = hosts[0]
        console.print(f"  Found: [bold]{hostname}[/bold] at [bold]{ip}[/bold]")
        return ip

    # Multiple hosts — let the user pick.
    console.print(f"  Found {len(hosts)} hosts:")
    for i, (hostname, ip) in enumerate(hosts, 1):
        console.print(f"    [bold]{i}[/bold]. {hostname} ({ip})")

    while True:
        raw = Prompt.ask("  Select device number").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(hosts):
                return hosts[idx][1]
        except ValueError:
            pass
        console.print("  [red]Invalid selection.[/red]")
