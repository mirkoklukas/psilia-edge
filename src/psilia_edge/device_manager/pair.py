"""psilia pair — interactive Jetson pairing wizard.

Developer note: be explicit at every step about what gets written or changed —
on the Jetson, on the laptop, or in config files. This can be tightened later
once the UX is proven, but err on the side of too much information for now.
"""

from __future__ import annotations

import os
from pathlib import Path

import paramiko
from rich.prompt import Prompt

from psilia_edge import ui
from psilia_edge.device_manager.config import KEYS_DIR
from psilia_edge.ui import console
from psilia_edge.utils import SSHError, connect, ssh_run


_SSH_CONFIG_PATH = Path(
    os.environ.get("PSILIA_SSH_CONFIG_PATH", "~/.ssh/config")
).expanduser()
_SSH_SECTION_START = "# >>> psilia-edge (managed by psilia — do not edit manually)"
_SSH_SECTION_END = "# <<< psilia-edge"


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Entrypoint
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def run_pair_wizard() -> None:
    ui.header(
        ["Runtime Manager", "Pair Wizard"],
        "Connects to a Jetson and registers it on this laptop.",
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
        _step_register_device(name, user, key_path)
        _step_sync_ssh_config(name)

    ui.done(
        f"{name} paired.",
        f"Run [bold]`psilia boostrap {name}`[/bold] to bootstrap the device.",
    )


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Steps
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
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
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    key_path = KEYS_DIR / name

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


# ── step 4: register device ───────────────────────────────────────────────────


def _step_register_device(name: str, user: str, key_path: Path) -> None:
    ui.title("Register Device")
    from psilia_edge.device_manager.config import register_device
    from psilia_edge.runtime.config import CONFIG_PATH

    register_device(name=name, host=f"{name}.local", user=user, key_path=key_path)

    ui.ok(f"Device registered in {CONFIG_PATH}")
    ui.detail("name", name)
    ui.detail("host", f"{name}.local")
    ui.detail("user", user)
    ui.detail("key", str(key_path))


# ── step 5: sync SSH config ───────────────────────────────────────────────────


def _step_sync_ssh_config(name: str) -> None:
    ui.title("Write SSH Config")
    sync_ssh_config()
    ui.ok(f"SSH config updated ({_SSH_CONFIG_PATH})")
    ui.detail("connect with", f"ssh {name}")


def _render_ssh_block(devices: dict) -> str:
    """Render all registered devices into SSH Host blocks."""
    blocks = []
    for name, dev in devices.items():
        block = (
            f"Host {name}\n"
            f"    HostName {dev['host']}\n"
            f"    User {dev['user']}\n"
            f"    IdentityFile {dev['key']}"
        )
        blocks.append(block)

        if hotspot_ip := dev.get("hotspot_ip"):
            hotspot_block = (
                f"Host {name}-hotspot\n"
                f"    HostName {hotspot_ip}\n"
                f"    User {dev['user']}\n"
                f"    IdentityFile {dev['key']}"
            )
            blocks.append(hotspot_block)

    return "\n\n".join(blocks)


def sync_ssh_config() -> None:
    """Re-render the psilia section in ~/.ssh/config from registered_devices in psilia.yaml."""
    from psilia_edge.runtime.config import read_config

    devices = read_config().get("registered_devices", {})
    rendered = _render_ssh_block(devices)

    _SSH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = _SSH_CONFIG_PATH.read_text() if _SSH_CONFIG_PATH.exists() else ""

    new_section = f"{_SSH_SECTION_START}\n{rendered}\n{_SSH_SECTION_END}"

    if _SSH_SECTION_START in existing:
        start_idx = existing.index(_SSH_SECTION_START)
        end_idx = existing.index(_SSH_SECTION_END) + len(_SSH_SECTION_END)
        new_file = existing[:start_idx] + new_section + existing[end_idx:]
    else:
        sep = "\n" if existing and not existing.endswith("\n") else ""
        new_file = existing + sep + "\n" + new_section + "\n"

    _SSH_CONFIG_PATH.write_text(new_file)
