"""Data operations — pull/push recorded MCAP data."""

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


def get_push_to() -> str:
    """Read data.push_to from psilia.yaml (host:path format).

    Raises ConfigurationError if not set — caller is responsible for prompting.
    """
    push_to = read_config().get("data", {}).get("push_to")
    if not push_to:
        raise ConfigurationError(
            "data.push_to not set. Run 'psilia data push --to <host:path>' to set it."
        )
    return push_to


def build_rsync_cmd(
    device: str,
    remote_data_dir: str,
    pull_to: Path,
    exclude: list[str] | None = None,
) -> str:
    """Build an rsync command to pull data from a remote device.

    # --archive        preserves timestamps, permissions, symlinks
    # --progress       per-file progress (\r-delimited, updated in-place by run_streamed)
    # --human-readable human-readable sizes
    """
    excludes = " ".join(f"--exclude '{f}'" for f in ["*.tmp", *(exclude or [])])
    return (
        f"rsync --archive --progress --human-readable "
        f"{excludes} "
        f"{device}:{remote_data_dir}/ "
        f"{pull_to}/"
    )


def build_push_cmd(
    source: str,
    push_to: str,
    exclude: list[str] | None = None,
) -> str:
    """Build an rsync command to push data to a remote destination."""
    excludes = " ".join(f"--exclude '{f}'" for f in ["*.tmp", *(exclude or [])])
    return (
        f"rsync --archive --progress --human-readable {excludes} {source}/ {push_to}/"
    )


def resolve_ssh_config(alias: str) -> dict[str, str]:
    """Resolve SSH config for an alias using `ssh -G`.

    Handles ~/.ssh/config includes (config.d/*), wildcards, etc.
    Returns a dict with 'hostname', 'user', and 'identityfile' keys.
    """
    import subprocess

    result = subprocess.run(["ssh", "-G", alias], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not resolve SSH host '{alias}': {result.stderr.strip()}"
        )

    config: dict[str, str] = {}
    identity_files: list[str] = []
    for line in result.stdout.splitlines():
        key, _, value = line.partition(" ")
        if key == "hostname":
            config["hostname"] = value
        elif key == "user":
            config["user"] = value
        elif key == "identityfile":
            identity_files.append(value)

    config["identity_files"] = identity_files

    if not config.get("hostname"):
        raise RuntimeError(f"Could not resolve hostname for SSH alias '{alias}'")

    return config


def resolve_ssh_host(alias: str) -> str:
    """Resolve an SSH alias to user@hostname."""
    config = resolve_ssh_config(alias)
    hostname = config["hostname"]
    user = config.get("user")
    return f"{user}@{hostname}" if user else hostname


def ensure_ssh_agent_key(alias: str) -> None:
    """Ensure the SSH key for a host alias is loaded in the agent.

    Resolves the identity file from SSH config, checks if it exists on disk,
    and runs ssh-add if needed.
    """
    import subprocess
    from pathlib import Path

    config = resolve_ssh_config(alias)
    identity_files = config.get("identity_files", [])

    for f in identity_files:
        path = Path(f).expanduser()
        if path.exists():
            subprocess.run(["ssh-add", str(path)], capture_output=True)
            return

    subprocess.run(["ssh-add"], capture_output=True)


def resolve_push_to(push_to: str) -> str:
    """Resolve a push_to destination, expanding SSH aliases in the host part.

    'mycloud:/data/psilia/' → 'user@actual.host.com:/data/psilia/'
    """
    if ":" not in push_to:
        return push_to
    host, _, path = push_to.partition(":")
    resolved_host = resolve_ssh_host(host)
    return f"{resolved_host}:{path}"


def _extract_hostname(resolved_host: str) -> str:
    """Extract hostname from 'user@hostname' or plain 'hostname'."""
    return resolved_host.split("@", 1)[-1]


def build_device_push_cmd(
    device: str,
    remote_data_dir: str,
    push_to: str,
    exclude: list[str] | None = None,
) -> str:
    """Build an SSH command that runs rsync on the device with agent forwarding.

    The laptop SSH's into the device with -A (agent forwarding), then the device
    rsyncs its data directory directly to the cloud destination. The push_to
    host is resolved on the laptop (via ssh -G) so the device doesn't need the
    alias in its own SSH config.

    Runs ssh-keyscan before rsync to ensure the cloud host is in the device's
    known_hosts (idempotent, only matters on first connection).
    """
    resolved = resolve_push_to(push_to)
    host_part = resolved.split(":")[0]
    hostname = _extract_hostname(host_part)
    keyscan = f"ssh-keyscan -H {hostname} >> ~/.ssh/known_hosts 2>/dev/null"
    rsync = build_push_cmd(remote_data_dir, resolved, exclude)
    return f"ssh -A -o LogLevel=ERROR {device} '{keyscan} && {rsync}'"
