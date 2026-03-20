"""Data operations — pull recorded MCAP data from a remote device."""

from __future__ import annotations

from pathlib import Path


def resolve_pull_to(pull_to_override: Path | None = None) -> Path:
    """Resolve the local destination directory for pulled data.

    Resolution order:
      1. pull_to_override if provided (not saved to config)
      2. data.pull_to from psilia.yaml
      3. Prompt the user and save the answer to psilia.yaml

    # TODO: Consider a pattern where CLI flags can opt-in to being persisted
    # to config (e.g. --to --save), rather than always prompting.
    """
    if pull_to_override is not None:
        return Path(pull_to_override).expanduser().resolve()

    from psilia_edge.runtime.config import read_config

    pull_to = read_config().get("data", {}).get("pull_to")
    if pull_to:
        return Path(pull_to).expanduser().resolve()

    from psilia_edge import ui
    from psilia_edge.device_manager.config import write_pull_to

    raw = ui.ask("Local directory to pull data into")
    path = Path(raw).expanduser().resolve()
    write_pull_to(path)
    return path


def pull_from_device(device: str, pull_to: Path) -> int:
    """Pull MCAP recordings from a registered device via rsync.

    Uses the SSH config entry for the device (set up during pairing).
    Returns the rsync exit code.

    # TODO: Skip in-progress recordings. The recording node knows which file
    # is actively being written — query it via ROS service or topic once
    # recording control is wired into the web UI.
    """
    from psilia_edge.utils import run_quiet, run_streamed

    # Step 1: resolve the data directory on the remote device.
    rc, stdout, _ = run_quiet(f"ssh {device} psilia runtime config --data-dir")
    if rc != 0:
        raise RuntimeError(f"Could not get data dir from {device} (exit {rc})")
    remote_data_dir = stdout.strip()

    pull_to.mkdir(parents=True, exist_ok=True)

    # Step 2: rsync from the resolved remote path.
    # --archive        preserves timestamps, permissions, symlinks
    # --progress       shows per-file progress
    # --human-readable human-readable sizes
    # --exclude '*.tmp' exclude any temp files
    cmd = (
        f"rsync --archive --progress --human-readable "
        f"--exclude '*.tmp' "
        f"{device}:{remote_data_dir}/ "
        f"{pull_to}/"
    )
    return run_streamed(cmd)
