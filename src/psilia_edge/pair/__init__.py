"""psilia pair — interactive Jetson pairing wizard.

Developer note: be explicit at every step about what gets written or changed —
on the Jetson, on the laptop, or in config files. This can be tightened later
once the UX is proven, but err on the side of too much information for now.
"""

from __future__ import annotations

import re
from pathlib import Path

import paramiko
from rich.prompt import Prompt

from psilia_edge.ssh import JetsonConn, SSHError, connect
from psilia_edge.ui import _fail, _ok, _header, console


_DEFAULT_DEVICE_NAME = "psilia-jetson"
_SSH_CONFIG_PATH = Path.home() / ".ssh" / "config"
_SSH_SECTION_START = "# >>> psilia-edge (managed by psilia — do not edit manually)"
_SSH_SECTION_END = "# <<< psilia-edge"


# ── step 1: connect (Path A / Path B) ────────────────────────────────────────


def _step_connect() -> JetsonConn | None:
    console.rule("[bold]Step 1 — Connect")

    target_ip = Prompt.ask("  Host (IP or hostname)")
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
    console.print("  [dim]Changing the name will update the Jetson hostname and /etc/hosts.[/dim]")
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
    _ok(f"Public key installed on Jetson (~/.ssh/authorized_keys)")
    return key_path


# ── step 4: write SSH config ──────────────────────────────────────────────────


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
    console.rule("[bold]Step 4 — SSH Config")

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
    console.print(f"  [dim]Added entries:[/dim]")
    console.print(f"    [dim]Host {name}         → {name}.local[/dim]")
    console.print(f"    [dim]Host {name}-hotspot  → 10.42.0.1[/dim]")
    console.print(f"  [dim]Connect with: ssh {name}[/dim]")


# ── step 5: register device ───────────────────────────────────────────────────


def _step_register_device(name: str, user: str, key_path: Path) -> None:
    console.rule("[bold]Step 5 — Register Device")
    from psilia_edge.config import register_device

    register_device(name=name, host=f"{name}.local", user=user, key_path=key_path)

    from psilia_edge.config import LAPTOP_CONFIG_PATH
    _ok(f"Device registered in {LAPTOP_CONFIG_PATH}")
    console.print(f"  [dim]  name: {name}[/dim]")
    console.print(f"  [dim]  host: {name}.local[/dim]")
    console.print(f"  [dim]  user: {user}[/dim]")
    console.print(f"  [dim]  key:  {key_path}[/dim]")


# ── entry point ───────────────────────────────────────────────────────────────


def run_pair_wizard() -> None:
    _header(
        "Pair Wizard", 
        "[dim]Connects to a Jetson and registers it on this laptop.[/dim]")

    # Step 1 — connect (Path A or B)
    conn = _step_connect()
    if conn is None:
        console.print("\n[yellow]Aborted — could not connect.[/yellow]")
        return

    with conn:
        # Step 2 — device name
        name = _step_device_name(conn)

        # Step 3 — SSH keypair
        key_path = _step_ssh_keypair(conn, name)

        # Step 4 — write SSH config (~/.ssh/config)
        _step_write_ssh_config(name, key_path, conn.user)

        # Step 5 — register device (~/.psilia/config.yaml, connection info only)
        _step_register_device(name, conn.user, key_path)

    console.print()
    console.rule("[bold]Done")
    console.print(
        f"\n  Device [bold]{name}[/bold] paired."
        f"\n  Run [bold]psilia setup {name}[/bold] to bootstrap the device."
    )
