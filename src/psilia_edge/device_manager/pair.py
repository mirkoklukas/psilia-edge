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

from psilia_edge import ui
from psilia_edge.ui import console
from psilia_edge.utils import SSHError, connect, ssh_run


_SSH_CONFIG_PATH = Path.home() / ".ssh" / "config"
_SSH_SECTION_START = "# >>> psilia-edge (managed by psilia — do not edit manually)"
_SSH_SECTION_END = "# <<< psilia-edge"


# ── step 1: connect (Path A / Path B) ────────────────────────────────────────


def _step_connect() -> tuple[paramiko.SSHClient, str] | None:
    ui.title("Connect")

    target_ip = Prompt.ask("  Host (IP or hostname)")
    user = Prompt.ask("  Username")
    password = Prompt.ask("  Password", default="", password=True)

    ui.info(f"Connecting as [bold]{user}@{target_ip}[/bold]…")
    try:
        with console.status("  Connecting over SSH…"):
            client = connect(target_ip, user=user, password=password or None)
        ui.ok(f"Connected to {target_ip}")
        return client, user
    except SSHError as exc:
        ui.fail(str(exc))
        return None


# ── step 3: SSH keypair ───────────────────────────────────────────────────────


def _step_ssh_keypair(client: paramiko.SSHClient, name: str) -> Path:
    ui.title("SSH Keypair")
    key_dir = Path.home() / ".psilia" / "keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    key_path = key_dir / name

    with console.status("  Generating RSA-4096 keypair…"):
        key = paramiko.RSAKey.generate(4096)
        key.write_private_key_file(str(key_path))
        key_path.chmod(0o600)

    pubkey_str = f"ssh-rsa {key.get_base64()} psilia-{name}"
    with console.status("  Installing pubkey on Jetson…"):
        ssh_run(client, "mkdir -p ~/.ssh && chmod 700 ~/.ssh")
        ssh_run(
            client,
            f"echo '{pubkey_str}' >> ~/.ssh/authorized_keys"
            f" && chmod 600 ~/.ssh/authorized_keys",
        )
    ui.ok(f"Keypair saved to {key_path}")
    ui.ok("Public key installed on Jetson (~/.ssh/authorized_keys)")
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
    ui.title("Write SSH Config")

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
        new_inner = (
            (cleaned.rstrip("\n") + "\n\n" + new_block) if cleaned else new_block
        )

        before = existing[:start_idx]
        after = existing[end_idx + len(_SSH_SECTION_END) :]
        new_file = (
            before
            + _SSH_SECTION_START
            + "\n"
            + new_inner
            + "\n"
            + _SSH_SECTION_END
            + after
        )
    else:
        sep = "\n" if existing and not existing.endswith("\n") else ""
        new_file = (
            existing
            + sep
            + "\n"
            + _SSH_SECTION_START
            + "\n"
            + new_block
            + "\n"
            + _SSH_SECTION_END
            + "\n"
        )

    _SSH_CONFIG_PATH.write_text(new_file)
    ui.ok(f"SSH config updated ({_SSH_CONFIG_PATH})")
    ui.item(f"Host {name}         → {name}.local")
    ui.item(f"Host {name}-hotspot  → 10.42.0.1")
    ui.detail("connect with", f"ssh {name}")


# ── step 5: register device ───────────────────────────────────────────────────


def _step_register_device(name: str, user: str, key_path: Path) -> None:
    ui.title("Register Device")
    from psilia_edge.device_manager.config import register_device

    register_device(name=name, host=f"{name}.local", user=user, key_path=key_path)

    from psilia_edge.device_manager.core import CONFIG_PATH

    ui.ok(f"Device registered in {CONFIG_PATH}")
    ui.detail("name", name)
    ui.detail("host", f"{name}.local")
    ui.detail("user", user)
    ui.detail("key", str(key_path))


# ── entry point ───────────────────────────────────────────────────────────────


def run_pair_wizard() -> None:
    ui.header(
        ["Runtime Manager", "Pair Wizard"],
        "[dim]Connects to a Jetson and registers it on this laptop.[/dim]",
    )

    # Step 1 — connect
    result = _step_connect()
    if result is None:
        ui.warn("Aborted — could not connect.")
        return
    client, user = result

    with client:
        _, name, _ = ssh_run(client, "hostname")
        name = name.strip()
        key_path = _step_ssh_keypair(client, name)
        _step_write_ssh_config(name, key_path, user)
        _step_register_device(name, user, key_path)

    ui.done(
        f"{name} paired.",
        f"Run [bold]`psilia boostrap {name}`[/bold] to bootstrap the device.",
    )
