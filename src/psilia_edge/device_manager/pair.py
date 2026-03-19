"""psilia pair — interactive Jetson pairing wizard.

Developer note: be explicit at every step about what gets written or changed —
on the Jetson, on the laptop, or in config files. This can be tightened later
once the UX is proven, but err on the side of too much information for now.
"""

from __future__ import annotations

from pathlib import Path

import paramiko

from psilia_edge import ui
from psilia_edge.device_manager.config import (
    KEYS_DIR,
    _SSH_CONFIG_PATH,
    add_device_entry,
    sync_ssh_config,
    write_pull_to,
)
from psilia_edge.utils import SSHError, connect, ssh_run


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

    client, user = _step_connect()
    if client is None:
        ui.warn("Aborted — could not connect.")
        return

    with client:
        _, name, _ = ssh_run(client, "hostname")
        name = name.strip()
        key_path = _step_ssh_keypair(client, name)
        _step_add_device_entry(name, user, key_path)
        _step_sync_ssh_config(name)

    _ = _step_pull_to()

    ui.done(
        f"{name} paired.",
        f"Next: [bold]psilia runtime bootstrap {name}[/bold]",
    )


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Steps
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def _step_connect() -> tuple[paramiko.SSHClient | None, str]:
    ui.title("Connect")

    target_ip = ui.ask("Host (IP or hostname)")
    user = ui.ask("Username")
    password = ui.ask("Password", password=True)

    ui.info(f"Connecting as [bold]{user}@{target_ip}[/bold]…")
    try:
        with ui.status("Connecting over SSH…"):
            client = connect(target_ip, user=user, password=password or None)
        ui.ok(f"Connected to {target_ip}")
        return client, user
    except SSHError as exc:
        ui.fail(str(exc))
        return None, user


def _step_ssh_keypair(client: paramiko.SSHClient, name: str) -> Path:
    ui.title("SSH Keypair")
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    key_path = KEYS_DIR / name

    with ui.status("Generating RSA-4096 keypair…"):
        key = paramiko.RSAKey.generate(4096)
        key.write_private_key_file(str(key_path))
        key_path.chmod(0o600)

    pubkey_str = f"ssh-rsa {key.get_base64()} psilia-{name}"
    with ui.status("Installing pubkey on Jetson…"):
        ssh_run(client, "mkdir -p ~/.ssh && chmod 700 ~/.ssh")
        ssh_run(
            client,
            f"echo '{pubkey_str}' >> ~/.ssh/authorized_keys"
            f" && chmod 600 ~/.ssh/authorized_keys",
        )
    ui.ok(f"Keypair saved to {key_path}")
    ui.ok("Public key installed on Jetson (~/.ssh/authorized_keys)")
    return key_path


def _step_add_device_entry(name: str, user: str, key_path: Path) -> None:
    ui.title("Register Device")
    from psilia_edge.runtime.config import CONFIG_PATH

    add_device_entry(name=name, host=f"{name}.local", user=user, key_path=key_path)
    ui.ok(f"Device registered in {CONFIG_PATH}")


def _step_sync_ssh_config(name: str) -> None:
    ui.title("Write SSH Config")
    sync_ssh_config()
    ui.ok(f"SSH config updated ({_SSH_CONFIG_PATH})")
    ui.detail("connect with", f"ssh {name}")


def _step_pull_to() -> Path:
    ui.title("Data Pull Directory")
    path = Path(
        ui.ask("Where should pulled data be stored?", default="~/psilia-fetched")
    )
    with ui.status(f"Creating {path}…"):
        write_pull_to(path)
    ui.ok(f"Pull directory set to {path.expanduser().resolve()}")
    return path
