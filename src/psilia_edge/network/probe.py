"""Read-only network interface probing via nmcli and iw."""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field

Runner = Callable[..., subprocess.CompletedProcess]


def _run(cmd: list[str], runner: Runner = subprocess.run) -> tuple[int, str]:
    try:
        result = runner(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout.strip()
    except FileNotFoundError:
        # Command not available (e.g. running on dev machine without nmcli/iw)
        return 127, ""


def _split_terse(line: str) -> list[str]:
    """Split nmcli terse output on unescaped colons."""
    return re.split(r"(?<!\\):", line)


@dataclass
class Interface:
    name: str
    type: str  # "wifi" | "ethernet" | "loopback" | "other"
    state: str  # "connected" | "disconnected" | "unavailable" | "unmanaged"
    connection: str | None = None  # active NM connection profile name
    ip4: str | None = None
    supports_ap: bool = False
    extra: dict = field(default_factory=dict)

    @property
    def is_usb_wifi(self) -> bool:
        """USB WiFi dongles get kernel names starting with wlx."""
        return self.name.startswith("wlx")

    @property
    def is_wifi(self) -> bool:
        return self.type == "wifi"

    @property
    def is_ethernet(self) -> bool:
        return self.type == "ethernet"

    @property
    def is_connected(self) -> bool:
        return self.state == "connected"


def list_interfaces(runner: Runner = subprocess.run) -> list[Interface]:
    """Return all non-loopback network interfaces via nmcli."""
    rc, out = _run(
        ["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"],
        runner,
    )
    if rc != 0 or not out:
        return []

    _SKIP_TYPES = {"loopback", "bridge", "wifi-p2p", "can", "tun", "dummy"}

    interfaces = []
    for line in out.splitlines():
        parts = _split_terse(line)
        if len(parts) < 4:
            continue
        name, typ, state = parts[0], parts[1], parts[2]
        conn = ":".join(parts[3:]).replace("\\:", ":") or None
        if name == "lo" or typ in _SKIP_TYPES:
            continue
        # Skip unmanaged ethernet (USB gadget interfaces like usb0, usb1)
        if typ == "ethernet" and state == "unmanaged":
            continue
        interfaces.append(Interface(name=name, type=typ, state=state, connection=conn))

    for iface in interfaces:
        if iface.is_connected:
            iface.ip4 = _get_ip4(iface.name, runner)
        if iface.is_wifi:
            iface.supports_ap = _check_ap_support(iface.name, runner)

    return interfaces


def _get_ip4(ifname: str, runner: Runner = subprocess.run) -> str | None:
    rc, out = _run(
        ["nmcli", "-t", "-f", "IP4.ADDRESS", "device", "show", ifname],
        runner,
    )
    if rc != 0 or not out:
        return None
    # Output: IP4.ADDRESS[1]:192.168.1.10/24
    m = re.search(r"IP4\.ADDRESS\[\d+\]:(.+?)/\d+", out)
    return m.group(1) if m else None


def _check_ap_support(ifname: str, runner: Runner = subprocess.run) -> bool:
    """Return True if the interface's underlying phy advertises AP mode."""
    rc, out = _run(["iw", "dev", ifname, "info"], runner)
    if rc != 0 or not out:
        return False
    m = re.search(r"wiphy (\d+)", out)
    if not m:
        return False
    phy = f"phy{m.group(1)}"

    rc, out = _run(["iw", "phy", phy, "info"], runner)
    if rc != 0 or not out:
        return False

    # Walk the "Supported interface modes" section and look for "* AP"
    in_modes_section = False
    for line in out.splitlines():
        if "Supported interface modes" in line:
            in_modes_section = True
            continue
        if in_modes_section:
            stripped = line.strip()
            if not stripped.startswith("*"):
                break  # end of section
            if stripped == "* AP":
                return True
    return False
