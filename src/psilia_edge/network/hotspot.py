"""Create and manage a WiFi hotspot via nmcli.

AP (Access Point) mode: the wifi interface acts as a base station that other
devices connect to, as opposed to infrastructure (client) mode where it
connects to an existing router.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable

Runner = Callable[..., subprocess.CompletedProcess]

HOTSPOT_CON_NAME = "Borne-Hotspot"
HOTSPOT_SSID = "Borne"


def _run(cmd: list[str], runner: Runner = subprocess.run) -> tuple[int, str, str]:
    try:
        result = runner(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError:
        return 127, "", "command not found"


def hotspot_exists(
    con_name: str = HOTSPOT_CON_NAME,
    runner: Runner = subprocess.run,
) -> bool:
    """Return True if a hotspot connection profile already exists."""
    rc, out, _ = _run(["nmcli", "-t", "-f", "NAME", "connection", "show"], runner)
    if rc != 0:
        return False
    return any(line.strip() == con_name for line in out.splitlines())


def hotspot_is_active(
    con_name: str = HOTSPOT_CON_NAME,
    runner: Runner = subprocess.run,
) -> bool:
    """Return True if the hotspot connection profile is active (per nmcli)."""
    rc, out, _ = _run(
        ["nmcli", "-t", "-f", "NAME,STATE", "connection", "show", "--active"],
        runner,
    )
    if rc != 0:
        return False
    for line in out.splitlines():
        parts = line.split(":")
        if parts[0] == con_name and len(parts) > 1:
            return True
    return False


def hotspot_is_broadcasting(
    con_name: str = HOTSPOT_CON_NAME,
    runner: Runner = subprocess.run,
) -> bool:
    """Return True if the hotspot is actually broadcasting in AP mode.

    nmcli can report a connection as active while the interface is still in
    managed mode — this checks iw dev to confirm the radio is in AP mode.
    """
    # Get the device associated with the active connection
    rc, out, _ = _run(
        ["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show", "--active"],
        runner,
    )
    if rc != 0:
        return False
    device = None
    for line in out.splitlines():
        parts = line.split(":")
        if parts[0] == con_name and len(parts) > 1:
            device = parts[1].strip()
            break
    if not device:
        return False
    _, iw_out, _ = _run(["iw", "dev", device, "info"])
    return "type AP" in iw_out


def find_active_hotspot(
    ifname: str,
    runner: Runner = subprocess.run,
) -> str | None:
    """
    Return the active connection name if `ifname` is currently running as an AP.

    Gets the active connection name from the device, then checks the connection
    profile's wireless mode. Using `connection show` is more reliable than
    `device show` for reading the 802-11-WIRELESS.MODE field.
    """
    # Step 1: get the active connection name for this interface.
    rc, out, _ = _run(
        ["nmcli", "-t", "-f", "GENERAL.CONNECTION", "device", "show", ifname],
        runner,
    )
    if rc != 0 or not out:
        return None
    m = re.search(r"GENERAL\.CONNECTION:(.*)", out)
    con_name = m.group(1).strip() if m else None
    if not con_name:
        return None

    # Step 2: check whether that connection profile is in AP mode.
    rc, out, _ = _run(
        ["nmcli", "-t", "-f", "802-11-WIRELESS.MODE", "connection", "show", con_name],
        runner,
    )
    if rc != 0 or not out:
        return None
    return con_name if "ap" in out.lower() else None


def create_hotspot(
    ifname: str,
    password: str,
    ssid: str = HOTSPOT_SSID,
    con_name: str = HOTSPOT_CON_NAME,
    runner: Runner = subprocess.run,
) -> tuple[bool, str]:
    """
    Create and bring up a WiFi hotspot on `ifname`.

    Uses `nmcli connection add` with explicit AP mode settings rather than
    `nmcli device wifi hotspot`, which ignores con-name on some nmcli versions
    and always creates a profile called "Hotspot".

    Returns (success, error_message).
    """
    # Delete any AP already running on this interface — bring-down alone isn't
    # enough since autoconnect would immediately restore it.
    active = find_active_hotspot(ifname, runner)
    if active and active != con_name:
        _run(["nmcli", "connection", "delete", active], runner)

    # Remove stale profile with the same name if it exists.
    if hotspot_exists(con_name, runner):
        _run(["nmcli", "connection", "delete", con_name], runner)

    rc, _, err = _run(
        [
            "nmcli",
            "connection",
            "add",
            "type",
            "wifi",
            "ifname",
            ifname,
            "con-name",
            con_name,
            "ssid",
            ssid,
            "802-11-wireless.mode",
            "ap",
            "802-11-wireless-security.key-mgmt",
            "wpa-psk",
            "802-11-wireless-security.psk",
            password,
            "ipv4.method",
            "shared",
            "connection.autoconnect",
            "yes",
        ],
        runner,
    )
    if rc != 0:
        return False, err or "nmcli connection add failed"

    rc, _, err = _run(["nmcli", "connection", "up", con_name], runner)
    if rc != 0:
        return False, err or "nmcli connection up failed"

    # Some drivers activate in managed mode on first up — cycle to ensure AP mode.
    _, iw_out, _ = _run(["iw", "dev", ifname, "info"])
    if "type AP" not in iw_out:
        _run(["nmcli", "connection", "down", con_name], runner)
        rc, _, err = _run(["nmcli", "connection", "up", con_name], runner)
        if rc != 0:
            return False, err or "nmcli connection up failed on retry"

    return True, ""


def bring_up_hotspot(
    con_name: str = HOTSPOT_CON_NAME,
    runner: Runner = subprocess.run,
) -> bool:
    """Bring up an existing hotspot profile."""
    rc, _, _ = _run(["nmcli", "connection", "up", con_name], runner)
    return rc == 0


def bring_down_hotspot(
    con_name: str = HOTSPOT_CON_NAME,
    runner: Runner = subprocess.run,
) -> bool:
    """Bring down the hotspot without deleting the profile."""
    rc, _, _ = _run(["nmcli", "connection", "down", con_name], runner)
    return rc == 0
