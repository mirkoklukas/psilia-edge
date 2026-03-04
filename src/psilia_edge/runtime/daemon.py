"""Daemon lifecycle: start, stop, PID file, log file."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from pathlib import Path


def _runtime_dir() -> Path:
    """Return a writable runtime dir for the current (real) user."""
    user = os.environ.get("SUDO_USER") or os.environ.get("USER", "root")
    d = Path(f"/tmp/psilia-edge-{user}")
    d.mkdir(exist_ok=True)
    return d


PID_FILE = _runtime_dir() / "psilia-edge.pid"
LOG_FILE = _runtime_dir() / "psilia-edge.log"


def get_pid() -> int | None:
    """Return the PID of the running daemon, or None if not running."""
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
    except ValueError:
        return None
    try:
        os.kill(pid, 0)
        return pid
    except ProcessLookupError:
        PID_FILE.unlink(missing_ok=True)
        return None


def is_running() -> bool:
    return get_pid() is not None


def start_daemon(host: str = "0.0.0.0", port: int = 8080) -> int:
    """Spawn the server as a background process detached from this terminal.

    Returns the PID of the spawned process.
    """
    if is_running():
        raise RuntimeError(f"psilia base layer is already running (PID {get_pid()})")

    entry_point = shutil.which("psilia")
    if entry_point is None:
        raise RuntimeError("psilia executable not found on PATH")

    log_fh = LOG_FILE.open("a")
    proc = subprocess.Popen(
        [entry_point, "serve", host, str(port)],
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # detach from controlling terminal
        close_fds=True,
    )
    PID_FILE.write_text(str(proc.pid))
    return proc.pid


def stop_daemon() -> bool:
    """Send SIGTERM to the daemon. Returns True if a process was stopped."""
    pid = get_pid()
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    PID_FILE.unlink(missing_ok=True)
    return True


def read_log_tail(n: int = 50) -> list[str]:
    """Return the last n lines of the log file."""
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(errors="replace").splitlines()
    return lines[-n:]
