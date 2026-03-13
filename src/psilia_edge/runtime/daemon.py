"""Daemon lifecycle: start, stop, PID file, log file."""

from __future__ import annotations

import os
import signal
import subprocess
import sys

from psilia_edge.runtime.config import LOG_DIR, RUN_DIR

PID_FILE = RUN_DIR / "psilia-edge.pid"
LOG_FILE = LOG_DIR / "psilia-edge.log"


# TODO: `get_pid()` and `is_running()` only detect the daemon if it was started via
#   `start_daemon()` (i.e. a PID file exists). If the server was started any other way
#   (e.g. `uvicorn` directly), these return False even though the port is bound.
#   Consider falling back to a port check (see `is_port_open()` in docker.py).
#   To kill a rogue process manually: `lsof -ti :8080 | xargs kill`
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

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log_fh = LOG_FILE.open("a")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"from psilia_edge.runtime.server import serve; serve('{host}', {port})",
        ],
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,  # detach from controlling terminal
        close_fds=True,
    )
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
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
