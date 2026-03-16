"""Connect to existing WiFi networks via nmcli."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

Runner = Callable[..., subprocess.CompletedProcess]

# Autoconnect priority — higher means NM prefers this connection.
# Hotspot gets 10; we give client connections 20 so they're preferred when
# both are available on the same interface (shouldn't happen, but just in case).
CLIENT_AUTOCONNECT_PRIORITY = 20


def _run(cmd: list[str], runner: Runner = subprocess.run) -> tuple[int, str]:
    from psilia_edge import ui

    ui.info(f"RUN: {' '.join(cmd)}")
    try:
        result = runner(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout.strip()
    except FileNotFoundError:
        return 127, ""


@dataclass
class WifiNetwork:
    ssid: str
    signal: int  # 0-100
    security: str  # e.g. "WPA2", "--" for open


@dataclass
class WifiConnection:
    name: str  # NM connection profile name
    active: bool  # whether currently connected
    device: str | None = None  # active device name, if connected


def list_wifi_connections(runner: Runner = subprocess.run) -> list[WifiConnection]:
    """Return saved NM WiFi connection profiles."""
    rc, out = _run(
        [
            "nmcli",
            "--escape",
            "no",
            "-t",
            "-f",
            "NAME,TYPE,DEVICE",
            "connection",
            "show",
        ],
        runner,
    )
    if rc != 0 or not out:
        return []
    connections = []
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 3:
            continue
        name, typ = parts[0], parts[1]
        device = ":".join(parts[2:]).strip() or None
        if typ != "wifi":
            continue
        connections.append(
            WifiConnection(name=name, active=device is not None, device=device)
        )
    return connections


def activate_connection(
    con_name: str,
    ifname: str | None = None,
    autoconnect: bool = True,
    priority: int = CLIENT_AUTOCONNECT_PRIORITY,
    runner: Runner = subprocess.run,
) -> bool:
    """Bring up an existing NM connection profile and update autoconnect settings."""
    _run(
        [
            "nmcli",
            "connection",
            "modify",
            con_name,
            "connection.autoconnect",
            "yes" if autoconnect else "no",
            "connection.autoconnect-priority",
            str(priority),
        ],
        runner,
    )
    cmd = ["nmcli", "connection", "up", con_name]
    if ifname:
        cmd += ["ifname", ifname]
    rc, _ = _run(cmd, runner)
    return rc == 0


def scan_networks(
    ifname: str | None = None,
    runner: Runner = subprocess.run,
) -> list[WifiNetwork]:
    """Return visible WiFi networks sorted by signal strength (strongest first)."""
    cmd = [
        "nmcli",
        "--escape",
        "no",
        "-t",
        "-f",
        "SSID,SIGNAL,SECURITY",
        "dev",
        "wifi",
        "list",
    ]
    if ifname:
        cmd += ["ifname", ifname]

    rc, out = _run(cmd, runner)
    if rc != 0 or not out:
        return []

    seen: set[str] = set()
    networks: list[WifiNetwork] = []
    for line in out.splitlines():
        parts = line.split(":")
        if len(parts) < 3:
            continue
        ssid = parts[0].strip()
        if not ssid or ssid in seen:
            continue
        seen.add(ssid)
        try:
            signal = int(parts[1])
        except ValueError:
            signal = 0
        security = parts[2] if parts[2] != "--" else "open"
        networks.append(WifiNetwork(ssid=ssid, signal=signal, security=security))

    networks.sort(key=lambda n: n.signal, reverse=True)
    return networks


def connect_to_network(
    ssid: str,
    password: str,
    ifname: str | None = None,
    autoconnect: bool = True,
    priority: int = CLIENT_AUTOCONNECT_PRIORITY,
    runner: Runner = subprocess.run,
) -> bool:
    """
    Connect to a WiFi network and persist it as a connection profile.

    Returns True on success.
    """
    cmd = ["nmcli", "dev", "wifi", "connect", ssid, "password", password]
    if ifname:
        cmd += ["ifname", ifname]

    rc, _ = _run(cmd, runner)
    if rc != 0:
        return False

    _run(
        [
            "nmcli",
            "connection",
            "modify",
            ssid,
            "connection.autoconnect",
            "yes" if autoconnect else "no",
            "connection.autoconnect-priority",
            str(priority),
        ],
        runner,
    )
    return True


def get_connected_ip(ssid: str, runner: Runner = subprocess.run) -> str | None:
    """Return the IPv4 address of a connected profile, if any."""
    rc, out = _run(
        ["nmcli", "-t", "-f", "IP4.ADDRESS", "connection", "show", ssid],
        runner,
    )
    if rc != 0 or not out:
        return None
    m = re.search(r"IP4\.ADDRESS\[\d+\]:(.+?)/\d+", out)
    return m.group(1) if m else None
