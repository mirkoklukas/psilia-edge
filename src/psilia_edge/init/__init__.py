"""psilia init — interactive Jetson setup wizard."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import paramiko
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from psilia_edge.init.discovery import discover_jetson
from psilia_edge.init.ssh import JetsonConn, SSHError, connect

console = Console()


_DEFAULT_DEVICE_NAME = "psilia-jetson"
# TODO: switch to "main" (or a release tag) once the project is stable.
_PSILIA_REPO_URL = "https://github.com/mirkoklukas/psilia-edge.git"
_PSILIA_REPO_BRANCH = "dev"
_SSH_CONFIG_PATH = Path.home() / ".ssh" / "config"
_PSILIA_CONFIG_PATH = Path.home() / ".psilia" / "config.yaml"
_SSH_SECTION_START = "# >>> psilia-edge (managed by psilia — do not edit manually)"
_SSH_SECTION_END = "# <<< psilia-edge"


# ── helpers ───────────────────────────────────────────────────────────────────


def _ok(msg: str) -> None:
    console.print(f"  [green]✓[/green] {msg}")


def _fail(msg: str) -> None:
    console.print(f"  [red]✗[/red] {msg}")


def _stub(msg: str = "not yet implemented") -> None:
    console.print(f"  [dim]({msg})[/dim]")


# ── step 1: connect (Path A / Path B) ────────────────────────────────────────


def _step_connect() -> JetsonConn | None:
    console.rule("[bold]Step 1 — Connect")

    has_ip = Confirm.ask(
        "  Do you have an IP or hostname for the Jetson already?", default=False
    )

    if has_ip:
        # Path A — existing access
        target_ip = Prompt.ask("  Host (IP or hostname)")
        user = Prompt.ask("  Username")
        password = Prompt.ask("  Password", default="", password=True)
    else:
        # Path B — fresh setup: show checklist, then discover
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
        console.print("  Discovering Jetson…")
        target_ip = discover_jetson()
        if target_ip is None:
            _fail("No Jetson found. Check ethernet connection and try again.")
            return None
        user = Prompt.ask("  Username")
        password = Prompt.ask("  Password", default="", password=True)

    console.print(f"  Connecting as [bold]{user}@{target_ip}[/bold]…")
    try:
        with console.status("  Connecting over SSH…"):
            conn = connect(target_ip, user=user, password=password or None)
        _ok(f"Connected to {target_ip}")
        return conn
    except SSHError as exc:
        _fail(str(exc))
        return None


# ── step 2: device name ───────────────────────────────────────────────────────


def _step_device_name(conn: JetsonConn) -> str:
    console.rule("[bold]Step 2 — Device Name")
    _, current, _ = conn.run("hostname")
    current = current.strip()
    if current:
        console.print(f"  Current hostname: [bold]{current}[/bold]")
    name = Prompt.ask("  Device name", default=current or _DEFAULT_DEVICE_NAME)
    if name == current:
        _ok(f"Hostname unchanged: '{name}'")
        return name
    with console.status(f"  Setting hostname to '{name}'…"):
        rc, _, err = conn.sudo(f"hostnamectl set-hostname {name}")
    if rc != 0:
        _fail(f"Failed to set hostname: {err.strip()}")
    else:
        conn.sudo(f"sed -i 's/^127\\.0\\.1\\.1.*/127.0.1.1\\t{name}/' /etc/hosts")
        _ok(f"Hostname set to '{name}'")
    return name


# ── step 3: SSH keypair ───────────────────────────────────────────────────────


def _step_ssh_keypair(conn: JetsonConn, name: str) -> Path:
    console.rule("[bold]Step 3 — SSH Keypair")
    key_dir = Path.home() / ".psilia" / "keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    key_path = key_dir / name

    with console.status("  Generating RSA-4096 keypair…"):
        key = paramiko.RSAKey.generate(4096)
        key.write_private_key_file(str(key_path))
        key_path.chmod(0o600)

    pubkey_str = f"ssh-rsa {key.get_base64()} psilia-{name}"
    with console.status("  Installing pubkey on Jetson…"):
        conn.run("mkdir -p ~/.ssh && chmod 700 ~/.ssh")
        conn.run(
            f"echo '{pubkey_str}' >> ~/.ssh/authorized_keys"
            f" && chmod 600 ~/.ssh/authorized_keys"
        )
    _ok(f"Keypair saved to {key_path}")
    return key_path


# ── step 4: network ───────────────────────────────────────────────────────────


_DEFAULT_HOTSPOT_PASSWORD = "psilia1234"


def _step_network(conn: JetsonConn, name: str) -> str:
    console.rule("[bold]Step 4 — Network Setup")
    console.print(
        "  Configures a wifi hotspot on the Jetson (USB dongle preferred)\n"
        "  so you can reach it in the field without a router."
    )
    ssid = Prompt.ask("  Hotspot SSID", default=f"{name}-ap")
    password = Prompt.ask("  Hotspot password", default=_DEFAULT_HOTSPOT_PASSWORD)
    console.print("\n  [dim]Will configure:[/dim]")
    console.print(f"    SSID:     [bold]{ssid}[/bold]")
    console.print(f"    Password: [bold]{password}[/bold]")
    console.print("    IP:       [bold]10.42.0.1[/bold] (fixed, Jetson side)")
    _stub("nmcli hotspot + wifi client setup over SSH")
    return ssid


# ── step 5: SSD ───────────────────────────────────────────────────────────────


def _step_ssd(conn: JetsonConn) -> str:
    console.rule("[bold]Step 5 — Storage / SSD")
    console.print("  Detects available drives and configures the data directory.")
    _stub("detect SSD, confirm mount point, configure /etc/fstab")
    mount = "/ssd/"
    console.print(f"  [dim]Defaulting to mount point:[/dim] [bold]{mount}[/bold]")
    console.print(f"  [dim]Data will be stored at:[/dim]   [bold]{mount}psilia/data/[/bold]")
    return mount


# ── step 6: create dirs ───────────────────────────────────────────────────────


_JETSON_DIRS = [
    "/opt/psilia",               # eMMC — config only (read at boot before SSD mounts)
    "/ssd/psilia/ros/src",       # colcon workspace
    "/ssd/psilia/data/recordings",  # MCAP recordings
]


def _step_create_dirs(conn: JetsonConn) -> None:
    console.rule("[bold]Step 6 — Directory Structure")
    for d in _JETSON_DIRS:
        console.print(f"  [dim]→[/dim] {d}")
    with console.status("  Creating directories…"):
        rc, _, err = conn.sudo(f"mkdir -p {' '.join(_JETSON_DIRS)}")
    if rc != 0:
        _fail(f"mkdir failed: {err.strip()}")
        return
    # sudo mkdir creates dirs owned by root; chown /ssd/psilia so the
    # logged-in user can write directly (SFTP uploads, pip installs, recordings).
    with console.status("  Setting ownership…"):
        rc, _, err = conn.sudo(f"chown -R {conn.user} /ssd/psilia")
    if rc != 0:
        _fail(f"chown failed: {err.strip()}")
    else:
        _ok("Directories created")


# ── step 7: clone repo ────────────────────────────────────────────────────────


def _step_clone(conn: JetsonConn) -> None:
    console.rule("[bold]Step 7 — Clone psilia-edge")
    creds_path = Path.home() / ".git-credentials"

    if creds_path.exists():
        with console.status("  Copying git credentials…"):
            conn.put(creds_path, "/tmp/.git-credentials")
        conn.run(
            "git config --global credential.helper "
            "'store --file /tmp/.git-credentials'"
        )

    with console.status(f"  Cloning psilia-edge ({_PSILIA_REPO_BRANCH})…"):
        rc, _, err = conn.run(
            f"test -d /ssd/psilia/psilia-edge/.git"
            f" || git clone --branch {_PSILIA_REPO_BRANCH} {_PSILIA_REPO_URL} /ssd/psilia/psilia-edge"
        )
    if rc != 0:
        _fail(f"Clone failed: {err.strip()}")
    else:
        _ok("Repository ready at /ssd/psilia/psilia-edge")
        # TODO: install into a venv at /ssd/psilia/.venv instead of system Python.
        # The Jetson's system Python is shared with ROS 2, so a global pip install
        # risks conflicts. A venv also gives systemd a fixed binary path:
        #   /ssd/psilia/.venv/bin/psilia
        # For now we install globally; this is fine for early development.
        with console.status("  Running pip install -e .…"):
            rc2, _, err2 = conn.run("pip install -e /ssd/psilia/psilia-edge")
        if rc2 != 0:
            _fail(f"pip install failed: {err2.strip()}")
        else:
            _ok("pip install -e . done")

    if creds_path.exists():
        conn.run("rm -f /tmp/.git-credentials")
        conn.run("git config --global --unset credential.helper || true")


# ── step 8: copy ROS package ──────────────────────────────────────────────────


def _step_copy_ros(conn: JetsonConn) -> None:
    console.rule("[bold]Step 8 — ROS Package")
    # __file__ = .../psilia-edge/src/psilia_edge/init/__init__.py
    # repo_root = 4 levels up: init/ -> psilia_edge/ -> src/ -> psilia-edge/
    repo_root = Path(__file__).parent.parent.parent.parent
    local_ros = repo_root / "ros" / "psilia_runtime"

    if not local_ros.exists():
        _fail(f"Local psilia_runtime not found at {local_ros}")
        return

    with console.status("  Uploading psilia_runtime…"):
        conn.put_dir(local_ros, "/ssd/psilia/ros/src/psilia_runtime")
    _ok("psilia_runtime copied to /ssd/psilia/ros/src/psilia_runtime")


# ── step 9: Docker ────────────────────────────────────────────────────────────


def _step_docker(conn: JetsonConn) -> None:
    console.rule("[bold]Step 9 — Docker")
    with console.status("  Checking Docker…"):
        rc, _, _ = conn.run("docker --version")
    if rc == 0:
        _ok("Docker already installed")
        return

    console.print("  Docker not found — installing…")
    with console.status("  Installing Docker (this may take a while)…"):
        rc, _, err = conn.run("curl -fsSL https://get.docker.com | sudo -S sh",
                              stdin_data=(conn._password or "") + "\n")
    if rc != 0:
        _fail(f"Docker install failed: {err.strip()}")
        return

    conn.sudo(f"usermod -aG docker {conn.user}")
    _ok("Docker installed")


# ── step 10: build Docker image ───────────────────────────────────────────────


def _step_build_image(conn: JetsonConn) -> None:
    console.rule("[bold]Step 10 — Build Docker Image")
    console.print(
        "  Builds [bold]psilia/runtime:latest[/bold] on the Jetson.\n"
        "  Source: [dim]/ssd/psilia/psilia-edge/ros/Dockerfile[/dim]\n"
        "  This step will take 10–20 minutes on first run."
    )
    _stub("docker build -t psilia/runtime:latest /ssd/psilia/psilia-edge/ros")


# ── step 11: camera ───────────────────────────────────────────────────────────


def _step_camera(conn: JetsonConn) -> None:
    console.rule("[bold]Step 11 — Camera (optional)")
    if not Confirm.ask("  Detect and configure connected camera now?", default=False):
        console.print(
            "  [dim]Skipped — configure later with 'psilia config camera'.[/dim]"
        )
        return
    _stub("detect USB stereo camera on Jetson")


# ── step 12: systemd ──────────────────────────────────────────────────────────


def _step_systemd(conn: JetsonConn) -> bool:
    console.rule("[bold]Step 12 — Autostart")
    console.print(
        "  Installs a systemd service ([bold]psilia.service[/bold]) on the Jetson\n"
        "  so the runtime starts automatically on boot."
    )
    _stub("install /etc/systemd/system/psilia.service and reload daemon")
    autostart = Confirm.ask("  Enable autostart on boot?", default=True)
    if autostart:
        _stub("systemctl enable psilia")
        _ok("Autostart enabled — runtime will start on next boot")
    else:
        console.print("  [dim]Autostart disabled — start manually with:[/dim] psilia start")
    return autostart


# ── step 13: write SSH config ─────────────────────────────────────────────────


def _remove_device_hosts(section: str, name: str) -> str:
    """Remove Host blocks for `name` and `name-hotspot` from a config section."""
    parts = re.split(r"(?=^Host )", section, flags=re.MULTILINE)
    kept = [
        p
        for p in parts
        if not re.match(rf"^Host {re.escape(name)}(-hotspot)?\s*$", p.split("\n")[0])
    ]
    return "".join(kept).strip()


def _step_write_ssh_config(name: str, key_path: Path, user: str) -> None:
    console.rule("[bold]Step 13 — SSH Config")

    new_block = (
        f"Host {name}\n"
        f"    HostName {name}.local\n"
        f"    User {user}\n"
        f"    IdentityFile {key_path}\n"
        f"\n"
        f"Host {name}-hotspot\n"
        f"    HostName 10.42.0.1\n"
        f"    User {user}\n"
        f"    IdentityFile {key_path}"
    )

    _SSH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = _SSH_CONFIG_PATH.read_text() if _SSH_CONFIG_PATH.exists() else ""

    if _SSH_SECTION_START in existing:
        start_idx = existing.index(_SSH_SECTION_START)
        inner_start = start_idx + len(_SSH_SECTION_START)
        end_idx = existing.index(_SSH_SECTION_END)
        inner = existing[inner_start:end_idx].strip("\n")

        cleaned = _remove_device_hosts(inner, name)
        new_inner = (cleaned.rstrip("\n") + "\n\n" + new_block) if cleaned else new_block

        before = existing[:start_idx]
        after = existing[end_idx + len(_SSH_SECTION_END):]
        new_file = (
            before
            + _SSH_SECTION_START + "\n"
            + new_inner + "\n"
            + _SSH_SECTION_END
            + after
        )
    else:
        sep = "\n" if existing and not existing.endswith("\n") else ""
        new_file = (
            existing + sep + "\n"
            + _SSH_SECTION_START + "\n"
            + new_block + "\n"
            + _SSH_SECTION_END + "\n"
        )

    _SSH_CONFIG_PATH.write_text(new_file)
    _ok(f"SSH config updated ({_SSH_CONFIG_PATH})")
    console.print(f"  [dim]Connect with: ssh {name}[/dim]")


# ── step 14: write laptop config ─────────────────────────────────────────────


def _step_write_laptop_config(
    name: str,
    user: str,
    key_path: Path,
    hotspot_ssid: str,
    camera: str | None,
) -> None:
    console.rule("[bold]Step 14 — Laptop Config")
    _PSILIA_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    config: dict = {}
    if _PSILIA_CONFIG_PATH.exists():
        try:
            config = yaml.safe_load(_PSILIA_CONFIG_PATH.read_text()) or {}
        except yaml.YAMLError:
            config = {}

    config.setdefault("devices", {})[name] = {
        "host": f"{name}.local",
        "user": user,
        "key": str(key_path),
        "data_path": "/ssd/psilia/data/recordings",
        "hotspot_ssid": hotspot_ssid,
        "camera": camera,
    }
    config.setdefault("defaults", {}).setdefault(
        "pull_to", str(Path.home() / "psilia-data")
    )

    _PSILIA_CONFIG_PATH.write_text(yaml.dump(config, default_flow_style=False))
    _ok(f"Laptop config written to {_PSILIA_CONFIG_PATH}")


# ── step 15: write Jetson config ─────────────────────────────────────────────


def _step_write_jetson_config(
    conn: JetsonConn, mount: str, autostart: bool, camera: str | None
) -> None:
    console.rule("[bold]Step 15 — Jetson Config")
    jetson_config = {
        "storage": {
            "mount": mount,
            "data_path": "/ssd/psilia/data/",
        },
        "runtime": {
            "image": "psilia/runtime:latest",
            "ros_workspace": "/ssd/psilia/ros/",
            "autostart": autostart,
        },
        "camera": {
            "type": camera,
        },
    }
    config_yaml = yaml.dump(jetson_config, default_flow_style=False)
    with console.status("  Writing Jetson config…"):
        rc, _, err = conn.sudo("mkdir -p /opt/psilia")
    if rc == 0:
        rc, _, err = conn.run(
            f"echo {shlex.quote(config_yaml)} | sudo -S tee /opt/psilia/config.yaml > /dev/null",
            stdin_data=(conn._password or "") + "\n",
        )
    if rc != 0:
        _fail(f"Failed to write Jetson config: {err.strip()}")
    else:
        _ok("Jetson config written to /opt/psilia/config.yaml")


# ── entry point ───────────────────────────────────────────────────────────────


def run_init_wizard() -> None:
    console.print(
        Panel(
            "[bold]Psilia Edge[/bold] — Device Init Wizard\n"
            "[dim]Sets up a fresh Jetson for spatial perception.[/dim]",
            expand=False,
            border_style="cyan",
        )
    )

    # Step 1 — connect (Path A or B)
    conn = _step_connect()
    if conn is None:
        console.print("\n[yellow]Aborted — could not connect.[/yellow]")
        return

    with conn:
        # Step 2 — device name (needed before keypair for file naming)
        name = _step_device_name(conn)

        # Step 3 — SSH keypair
        key_path = _step_ssh_keypair(conn, name)

        # Step 4 — network (stub) → returns hotspot SSID
        hotspot_ssid = _step_network(conn, name)

        # Step 5 — SSD (stub) → returns mount point
        mount = _step_ssd(conn)

        # Step 6 — create dirs
        _step_create_dirs(conn)

        # Step 7 — clone repo
        _step_clone(conn)

        # Step 8 — copy ROS package
        _step_copy_ros(conn)

        # Step 9 — Docker
        _step_docker(conn)

        # Step 10 — build image (stub)
        _step_build_image(conn)

        # Step 11 — camera (stub)
        _step_camera(conn)

        # Step 12 — systemd (stub) → returns autostart bool
        autostart = _step_systemd(conn)

        # Step 13 — write SSH config
        _step_write_ssh_config(name, key_path, conn.user)

        # Step 14 — write laptop config
        _step_write_laptop_config(name, conn.user, key_path, hotspot_ssid, camera=None)

        # Step 15 — write Jetson config
        _step_write_jetson_config(conn, mount, autostart, camera=None)

    console.print()
    console.rule("[bold]Done")
    console.print(
        f"\n  Device [bold]{name}[/bold] registered."
        f"\n  Run [bold]psilia start[/bold] to launch the spatial runtime."
    )
