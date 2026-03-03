"""psilia init — interactive Jetson setup wizard."""

from __future__ import annotations

from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from psilia_edge.init.discovery import discover_jetson
from psilia_edge.init.ssh import JetsonConn, SSHError, connect

console = Console()

_DEFAULT_USER = "nvidia"
_DEFAULT_PASSWORD = "nvidia"
_DEFAULT_DEVICE_NAME = "psilia-jetson"


# ── helpers ───────────────────────────────────────────────────────────────────


def _ok(msg: str) -> None:
    console.print(f"  [green]✓[/green] {msg}")


def _fail(msg: str) -> None:
    console.print(f"  [red]✗[/red] {msg}")


def _stub(msg: str = "not yet implemented") -> None:
    console.print(f"  [dim]({msg})[/dim]")


# ── step 1: prerequisites ─────────────────────────────────────────────────────


def _step_prerequisites() -> bool:
    console.rule("[bold]Step 1 — Prerequisites")
    console.print(
        Panel(
            "Before we begin, make sure you have:\n\n"
            "  [green]✓[/green] Jetson flashed with JetPack\n"
            "  [green]✓[/green] Ethernet cable connected between Jetson and your laptop/router\n"
            "  [green]✓[/green] Jetson powered on",
            expand=False,
            border_style="dim",
        )
    )
    return Confirm.ask("Ready to continue?", default=True)


# ── step 2: connect ───────────────────────────────────────────────────────────


def _step_connect(host: str | None) -> JetsonConn | None:
    console.rule("[bold]Step 2 — Connect")

    if host:
        console.print(f"  Using provided host: [bold]{host}[/bold]")
        target_ip = host
    else:
        console.print("  Discovering Jetson over ARP…")
        target_ip = discover_jetson()
        if target_ip is None:
            _fail("No Jetson found. Check ethernet connection and try again.")
            return None

    console.print(f"  Connecting as [bold]{_DEFAULT_USER}@{target_ip}[/bold]…")
    console.print(
        f"  [dim](Using default JetPack password: '{_DEFAULT_PASSWORD}')[/dim]"
    )

    try:
        with console.status("  Connecting over SSH…"):
            conn = connect(target_ip, user=_DEFAULT_USER, password=_DEFAULT_PASSWORD)
        _ok(f"Connected to {target_ip}")
        return conn
    except SSHError as exc:
        _fail(str(exc))
        console.print(
            "  [dim]Tip: If the Jetson is not on default credentials, "
            "use --host and ensure the device is reachable.[/dim]"
        )
        return None


# ── step 3: SSH keypair ───────────────────────────────────────────────────────


def _step_ssh_keypair(conn: JetsonConn) -> None:
    console.rule("[bold]Step 3 — SSH Keypair")
    _stub("generate dedicated keypair and copy pubkey to Jetson")


# ── step 4: network ───────────────────────────────────────────────────────────


def _step_network(conn: JetsonConn) -> None:
    console.rule("[bold]Step 4 — Network Setup")
    console.print(
        "  Sets up hotspot (USB wifi dongle preferred) and wifi client connections."
    )
    _stub("hotspot + wifi client setup over SSH")


# ── step 5: device name ───────────────────────────────────────────────────────


def _step_device_name(conn: JetsonConn) -> str:
    console.rule("[bold]Step 5 — Device Name")
    name = Prompt.ask("  Device name", default=_DEFAULT_DEVICE_NAME)
    _stub(f"set hostname to '{name}' on Jetson")
    return name


# ── step 6: SSH config ────────────────────────────────────────────────────────


def _step_ssh_config(name: str, host: str) -> None:
    console.rule("[bold]Step 6 — SSH Config")
    if not Confirm.ask(
        f"  Add SSH config entry for '{name}' to ~/.ssh/config?", default=True
    ):
        console.print("  [dim]Skipped.[/dim]")
        return

    ssh_config_path = Path.home() / ".ssh" / "config"
    key_path = Path.home() / ".psilia" / "keys" / name
    entry = (
        f"\nHost {name}\n"
        f"    HostName {name}.local\n"
        f"    User {_DEFAULT_USER}\n"
        f"    IdentityFile {key_path}\n"
    )

    ssh_config_path.parent.mkdir(parents=True, exist_ok=True)
    # Avoid duplicate entries
    existing = ssh_config_path.read_text() if ssh_config_path.exists() else ""
    if f"Host {name}" in existing:
        console.print(f"  [dim]Entry for '{name}' already exists — skipped.[/dim]")
        return

    with ssh_config_path.open("a") as f:
        f.write(entry)
    _ok(f"Added entry 'Host {name}' to {ssh_config_path}")
    console.print(f"  [dim]Connect later with: ssh {name}[/dim]")


# ── step 7: create dirs ───────────────────────────────────────────────────────


def _step_create_dirs(conn: JetsonConn) -> None:
    console.rule("[bold]Step 7 — Directory Structure")
    _stub("mkdir -p /opt/psilia/ros /opt/psilia/data on Jetson")


# ── step 8: SSD ───────────────────────────────────────────────────────────────


def _step_ssd(conn: JetsonConn) -> None:
    console.rule("[bold]Step 8 — Storage / SSD")
    console.print(
        "  Detects available drives and configures /ssd/psilia-data/ as data directory."
    )
    _stub("detect SSD, confirm mount point, configure data directory")


# ── step 9: Docker ───────────────────────────────────────────────────────────


def _step_docker(conn: JetsonConn) -> None:
    console.rule("[bold]Step 9 — Docker")
    _stub("install Docker on Jetson")


# ── step 10: clone repo ───────────────────────────────────────────────────────


def _step_clone(conn: JetsonConn) -> None:
    console.rule("[bold]Step 10 — Clone psilia-edge")
    _stub("git clone psilia-edge on Jetson and pip install -e .")


# ── step 11: copy ROS package ─────────────────────────────────────────────────


def _step_copy_ros(conn: JetsonConn) -> None:
    console.rule("[bold]Step 11 — ROS Package")
    _stub("copy psilia_runtime to /opt/psilia/ros/ on Jetson")


# ── step 12: build Docker image ───────────────────────────────────────────────


def _step_build_image(conn: JetsonConn) -> None:
    console.rule("[bold]Step 12 — Build Docker Image")
    console.print("  Builds psilia/runtime:latest on the Jetson from ros/Dockerfile.")
    _stub("docker build on Jetson (this will take a while)")


# ── step 13: camera ───────────────────────────────────────────────────────────


def _step_camera(conn: JetsonConn) -> None:
    console.rule("[bold]Step 13 — Camera (optional)")
    if not Confirm.ask("  Detect and configure connected camera now?", default=False):
        console.print(
            "  [dim]Skipped — configure later with 'psilia config camera'.[/dim]"
        )
        return
    _stub("detect USB stereo camera on Jetson")


# ── step 14: systemd ─────────────────────────────────────────────────────────


def _step_systemd(conn: JetsonConn) -> None:
    console.rule("[bold]Step 14 — Autostart")
    _stub("install systemd service on Jetson")
    autostart = Confirm.ask("  Enable autostart on boot?", default=True)
    if autostart:
        _stub("systemctl enable psilia on Jetson")
        console.print("  [dim]Psilia will start automatically on next boot.[/dim]")
    else:
        console.print("  [dim]Start manually with: psilia start[/dim]")


# ── step 15: write local config ───────────────────────────────────────────────


def _step_write_config(name: str, host: str) -> None:
    console.rule("[bold]Step 15 — Write Config")

    config_path = Path.home() / ".psilia" / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing or start fresh
    config: dict = {}
    if config_path.exists():
        try:
            config = yaml.safe_load(config_path.read_text()) or {}
        except yaml.YAMLError:
            config = {}

    config.setdefault("devices", {})[name] = {
        "host": f"{name}.local",
        "user": _DEFAULT_USER,
        "key": str(Path.home() / ".psilia" / "keys" / name),
        "data_path": "/ssd/psilia-data/recordings",
    }
    config.setdefault("defaults", {}).setdefault(
        "pull_to", str(Path.home() / "psilia-data")
    )

    config_path.write_text(yaml.dump(config, default_flow_style=False))
    _ok(f"Config written to {config_path}")


# ── entry point ───────────────────────────────────────────────────────────────


def run_init_wizard(host: str | None = None) -> None:
    console.print(
        Panel(
            "[bold]Psilia Edge[/bold] — Device Init Wizard\n"
            "[dim]Sets up a fresh Jetson for spatial perception.[/dim]",
            expand=False,
            border_style="cyan",
        )
    )

    # Step 1 — prerequisites
    if not _step_prerequisites():
        console.print("\n[yellow]Aborted.[/yellow]")
        return

    # Step 2 — connect (may fail gracefully)
    conn = _step_connect(host)

    # Steps 3–14 require a live connection
    device_name = _DEFAULT_DEVICE_NAME
    target_host = host or ""

    if conn is not None:
        with conn:
            _step_ssh_keypair(conn)
            _step_network(conn)
            device_name = _step_device_name(conn)
            target_host = conn.host

            _step_create_dirs(conn)
            _step_ssd(conn)
            _step_docker(conn)
            _step_clone(conn)
            _step_copy_ros(conn)
            _step_build_image(conn)
            _step_camera(conn)
            _step_systemd(conn)
    else:
        console.print(
            "\n[yellow]No SSH connection — skipping remote steps 3–14.[/yellow]"
        )
        device_name = Prompt.ask(
            "  Device name to record in config", default=_DEFAULT_DEVICE_NAME
        )
        target_host = host or f"{device_name}.local"

    # Steps 6 and 15 work without SSH
    _step_ssh_config(device_name, target_host)
    _step_write_config(device_name, target_host)

    # Done
    console.print()
    console.rule("[bold]Done")
    console.print(
        f"\n  Device [bold]{device_name}[/bold] registered."
        f"\n  Run [bold]psilia start[/bold] to launch the spatial runtime."
    )
