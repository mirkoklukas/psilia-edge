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
    """
    import json
    from psilia_edge.utils import run_on_device_capture, run_streamed

    # Step 1: resolve the data directory on the remote device.
    rc, stdout, _ = run_on_device_capture(device, "psilia runtime config data-dir")
    if rc != 0:
        raise RuntimeError(f"Could not get data dir from {device} (exit {rc})")
    remote_data_dir = stdout.strip()

    # Step 2: check for an in-progress recording to exclude.
    exclude = []
    rc, stdout, _ = run_on_device_capture(
        device, "psilia runtime status --recording --json"
    )
    if rc == 0:
        recording = json.loads(stdout.strip())
        if recording.get("recording") and (active_file := recording.get("file")):
            exclude.append(active_file)

    pull_to.mkdir(parents=True, exist_ok=True)

    # Step 3: rsync from the resolved remote path.
    # --archive        preserves timestamps, permissions, symlinks
    # --progress       shows per-file progress
    # --human-readable human-readable sizes
    excludes = " ".join(f"--exclude '{f}'" for f in ["*.tmp", *exclude])
    cmd = (
        f"rsync --archive --progress --human-readable "
        f"{excludes} "
        f"{device}:{remote_data_dir}/ "
        f"{pull_to}/"
    )
    return run_streamed(cmd)
