"""Jetson discovery: mDNS first, active ping sweep fallback, passive ARP fallback."""

from __future__ import annotations

import concurrent.futures
import ipaddress
import re
import socket
import subprocess

from rich.console import Console
from rich.prompt import Prompt

console = Console()

# arp -a output line:  hostname (ip) at mac [ether] on iface
# Only match entries with a resolved MAC (exclude '(incomplete)' entries).
_ARP_RE = re.compile(
    r"^(\S+)\s+\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-f]{1,2}:){5}[0-9a-f]{1,2}.*\bon\s+(\S+)",
    re.MULTILINE,
)

_MDNS_HOSTNAME = "nvidia.local"

# Port name keywords that identify non-wired interfaces to exclude.
_EXCLUDE_PORT_KEYWORDS = {"wi-fi", "thunderbolt", "bluetooth", "bridge"}


# ── interface helpers ─────────────────────────────────────────────────────────


def _find_wired_ifaces() -> list[str]:
    """Return active wired ethernet interface names (macOS only).

    Parses `networksetup -listallhardwareports`, drops Wi-Fi / Thunderbolt /
    Bluetooth / Bridge ports, then keeps only those with `status: active`.
    Returns an empty list if `networksetup` is not available.
    """
    try:
        result = subprocess.run(
            ["networksetup", "-listallhardwareports"],
            capture_output=True, text=True, timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    ifaces: list[str] = []
    port_name: str | None = None
    for line in result.stdout.splitlines():
        if line.startswith("Hardware Port:"):
            port_name = line.split(":", 1)[1].strip().lower()
        elif line.startswith("Device:") and port_name is not None:
            device = line.split(":", 1)[1].strip()
            if not any(kw in port_name for kw in _EXCLUDE_PORT_KEYWORDS):
                ifaces.append(device)
            port_name = None

    active: list[str] = []
    for iface in ifaces:
        try:
            r = subprocess.run(
                ["ifconfig", iface], capture_output=True, text=True, timeout=3,
            )
            if "status: active" in r.stdout:
                active.append(iface)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return active


def _iface_cidr24(iface: str) -> str | None:
    """Return the /24 subnet containing the interface's IP, e.g. '192.168.100.0/24'.

    CIDR (Classless Inter-Domain Routing) notation describes a subnet as an IP
    address plus a prefix length: 192.168.100.0/24. The /24 means the first 24
    bits identify the network, leaving 8 bits for hosts — i.e. addresses
    192.168.100.1–254.

    The actual netmask on the interface may be wider (e.g. /16 = 65k hosts),
    but we force /24 to keep the ping sweep to a manageable 254 addresses.
    This is safe because a Jetson on a direct cable will always land in the
    same /24 as the laptop.
    """
    try:
        r = subprocess.run(["ifconfig", iface], capture_output=True, text=True, timeout=3)
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", r.stdout)
        if m:
            network = ipaddress.IPv4Network(f"{m.group(1)}/24", strict=False)
            return str(network)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


# ── discovery strategies ──────────────────────────────────────────────────────


def _try_mdns(hostname: str = _MDNS_HOSTNAME) -> str | None:
    """Resolve hostname via mDNS/Bonjour. Returns IPv4 address or None."""
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_INET)
        if results:
            return results[0][4][0]
    except socket.gaierror:
        return None


def _run_arp() -> str:
    """Read the OS ARP cache and return the raw output as a string.

    ARP (Address Resolution Protocol) is how devices on a local network map
    IP addresses to MAC addresses. Every time your laptop talks to another
    device, the OS records the mapping (IP → MAC) in a table called the ARP
    cache. This cache is passive — it only contains devices the laptop has
    recently communicated with, and entries expire after ~20 minutes.

    `arp -a` dumps the full cache. Example output line:
        ? (192.168.100.3) at 3c:6d:66:76:67:ad on en10 ifscope [ethernet]
         hostname  ip              mac address       interface
    """
    try:
        result = subprocess.run(
            ["arp", "-a"], capture_output=True, text=True, timeout=5
        )
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _parse_arp(output: str, ifaces: list[str] | None = None) -> list[tuple[str, str]]:
    """Parse `arp -a` output into a list of (hostname, ip) tuples.

    Only entries with a resolved MAC address are returned — entries marked
    '(incomplete)' mean no device responded to the ARP request and are skipped.

    An interface (iface) is a network adapter — e.g. `en0` is Wi-Fi,
    `en10` is a USB-ethernet dongle. Filtering by interface lets us ignore
    hosts seen on Wi-Fi and focus only on what's physically connected via
    the ethernet cable.
    """
    results = []
    for m in _ARP_RE.finditer(output):
        hostname, ip, found_iface = m.group(1), m.group(2), m.group(4)
        if ifaces and found_iface not in ifaces:
            continue
        results.append((hostname, ip))
    return results


def _ping_sweep(subnet: str, max_workers: int = 50) -> None:
    """Ping all hosts in a subnet concurrently to populate the ARP cache.

    The ping response doesn't matter — it's discarded. The point is to trigger
    an ARP request for every address: the OS broadcasts "who has x.x.x.x?"
    before sending the ICMP packet. Any device that replies updates the ARP
    cache with its MAC address, which we then read with `arp -a`.

    The subnet is derived from the laptop's own IP on the wired interface,
    forced to /24. E.g. if the laptop is 192.168.100.99, we sweep
    192.168.100.1–254. This assumes the Jetson lands in the same /24,
    which is true for direct-cable connections in practice.

    Devices that were already in the ARP cache from a previous connection
    are caught earlier by the passive scan and don't need the sweep.
    """
    network = ipaddress.IPv4Network(subnet)

    def _ping(ip: str) -> None:
        subprocess.run(
            ["ping", "-c", "1", "-W", "300", ip],
            capture_output=True,
            timeout=2,
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(_ping, (str(h) for h in network.hosts()))


def _arp_scan(ifaces: list[str]) -> list[tuple[str, str]]:
    """Passive ARP table read, filtered to the given interfaces."""
    return _parse_arp(_run_arp(), ifaces)


def _active_scan(ifaces: list[str]) -> list[tuple[str, str]]:
    """Ping-sweep each iface's /24, then read ARP filtered to those ifaces."""
    subnets = [s for iface in ifaces if (s := _iface_cidr24(iface))]
    for subnet in subnets:
        console.print(f"  Sweeping [bold]{subnet}[/bold]…")
        _ping_sweep(subnet)
    return _parse_arp(_run_arp(), ifaces)


# ── entry point ───────────────────────────────────────────────────────────────


def _iface_ips(ifaces: list[str]) -> set[str]:
    """Return the set of IP addresses assigned to the given interfaces (i.e. the laptop's own IPs)."""
    ips: set[str] = set()
    for iface in ifaces:
        try:
            r = subprocess.run(["ifconfig", iface], capture_output=True, text=True, timeout=3)
            for m in re.finditer(r"inet (\d+\.\d+\.\d+\.\d+)", r.stdout):
                ips.add(m.group(1))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return ips


def _pick_host(hosts: list[tuple[str, str]], own_ips: set[str] | None = None) -> str | None:
    """Auto-return if one host, prompt user to pick if multiple.

    own_ips: the laptop's own IP addresses — shown as '(this machine)' in the list.
    """
    if not hosts:
        return None
    if len(hosts) == 1:
        hostname, ip = hosts[0]
        console.print(f"  Found: [bold]{hostname}[/bold] at [bold]{ip}[/bold]")
        return ip

    console.print(f"  Found {len(hosts)} hosts:")
    for i, (hostname, ip) in enumerate(hosts, 1):
        label = " [dim](this machine)[/dim]" if own_ips and ip in own_ips else ""
        console.print(f"    [bold]{i}[/bold]. {hostname} ({ip}){label}")

    while True:
        raw = Prompt.ask("  Select device number").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(hosts):
                return hosts[idx][1]
        except ValueError:
            pass
        console.print("  [red]Invalid selection.[/red]")


def discover_jetson() -> str | None:
    """Discover a Jetson on the local network.

    1. mDNS (nvidia.local) — instant if Avahi/Bonjour is working.
    2. Passive ARP scan filtered to active wired interfaces — fast, uses cache.
    3. Active ping sweep of each wired iface's /24 — populates cache, then re-reads.

    Returns None if nothing is found after all three strategies.
    """
    # 1. mDNS
    with console.status(f"  Trying mDNS ({_MDNS_HOSTNAME})…"):
        ip = _try_mdns()
    if ip:
        console.print(f"  Found via mDNS: [bold]{_MDNS_HOSTNAME}[/bold] → [bold]{ip}[/bold]")
        return ip
    console.print(f"  [dim]mDNS not found.[/dim]")

    wired = _find_wired_ifaces()
    if wired:
        console.print(f"  Wired interface(s): [bold]{', '.join(wired)}[/bold]")

    own_ips = _iface_ips(wired)

    # 2. Passive ARP
    with console.status("  Checking ARP cache…"):
        hosts = _arp_scan(wired or [])
    if hosts:
        console.print("  Found in ARP cache:")
        if ip := _pick_host(hosts, own_ips):
            return ip

    # 3. Active ping sweep
    console.print("  Running active scan…")
    with console.status("  Sweeping subnet(s)…"):
        hosts = _active_scan(wired or [])
    if ip := _pick_host(hosts, own_ips):
        return ip

    console.print("  [yellow]No devices found.[/yellow]")
    console.print("  Make sure the Jetson is powered on and the ethernet cable is connected.")
    return None
