"""Data operations — pull recorded MCAP data from a remote device."""

from __future__ import annotations

from pathlib import Path

from psilia_edge.runtime.config import ConfigurationError, read_config


def get_pull_to() -> Path:
    """Read data.pull_to from psilia.yaml.

    Raises ConfigurationError if not set — caller is responsible for prompting.
    """
    pull_to = read_config().get("data", {}).get("pull_to")
    if not pull_to:
        raise ConfigurationError(
            "data.pull_to not set. Run 'psilia data pull --to <dir>' to set it."
        )
    return Path(pull_to).expanduser().resolve()


def get_remote_data_dir(device: str) -> str:
    """Get the data directory path from a remote device.

    Raises RuntimeError if the query fails.
    """
    from psilia_edge.utils import run_on_device_capture

    rc, stdout, _ = run_on_device_capture(device, "psilia runtime config data-dir")
    if rc != 0:
        raise RuntimeError(f"Could not get data dir from {device} (exit {rc})")
    return stdout.strip()


def get_active_recording(device: str) -> str | None:
    """Get the path of the file actively being recorded on a device, or None.

    Returns None if not recording or if the query fails.
    """
    import json

    from psilia_edge.utils import run_on_device_capture

    rc, stdout, _ = run_on_device_capture(
        device, "psilia runtime status --recording --json"
    )
    if rc != 0:
        return None
    try:
        recording = json.loads(stdout.strip())
        if recording.get("recording") and (active_file := recording.get("file")):
            return active_file
    except (json.JSONDecodeError, AttributeError):
        pass
    return None


def build_rsync_cmd(
    device: str,
    remote_data_dir: str,
    pull_to: Path,
    exclude: list[str] | None = None,
) -> str:
    """Build an rsync command to pull data from a remote device.

    # --archive         preserves timestamps, permissions, symlinks
    # --info=progress2  single overall progress line (updated in-place via \r)
    # --human-readable  human-readable sizes
    """
    excludes = " ".join(f"--exclude '{f}'" for f in ["*.tmp", *(exclude or [])])
    return (
        f"rsync --archive --info=progress2 --human-readable "
        f"{excludes} "
        f"{device}:{remote_data_dir}/ "
        f"{pull_to}/"
    )
