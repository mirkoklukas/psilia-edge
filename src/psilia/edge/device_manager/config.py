"""Device manager config helpers — device registry and laptop-side paths."""

from __future__ import annotations

import os
from pathlib import Path

from psilia.edge.runtime.config import CONFIG_DIR, read_config, write_config

KEYS_DIR = CONFIG_DIR / "keys"
DATA_DIR = Path.home() / "psilia-data"

_SSH_CONFIG_PATH = Path(
    os.environ.get("PSILIA_SSH_CONFIG_PATH", "~/.ssh/config")
).expanduser()
_SSH_SECTION_START = "# >>> psilia-edge (managed by psilia — do not edit manually)"
_SSH_SECTION_END = "# <<< psilia-edge"


def add_device_entry(name: str, host: str, user: str, key_path: Path) -> None:
    """Write minimal device entry (connection info only).

    Merges into existing config without overwriting other devices.
    """
    config = read_config()
    config.setdefault("registered_devices", {})[name] = {
        "host": host,
        "user": user,
        "key": str(key_path),
    }
    write_config(config)


def write_pull_to(path: Path) -> None:
    """Write data.pull_to path to psilia.yaml. Creates the directory if needed."""
    path = path.expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    config = read_config()
    config.setdefault("data", {})["pull_to"] = str(path)
    write_config(config)


def write_push_to(dest: str) -> None:
    """Write data.push_to destination to psilia.yaml (host:path format)."""
    config = read_config()
    config.setdefault("data", {})["push_to"] = dest
    write_config(config)


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

    return "\n\n".join(blocks)


def sync_ssh_config() -> None:
    """Re-render the psilia section in ~/.ssh/config from registered_devices in psilia.yaml."""
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
