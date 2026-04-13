from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

import paramiko
import psilia_edge.ui as ui
import yaml


def write_yaml(path: Path, data: dict, parents=True, exist_ok=True) -> None:
    path.parent.mkdir(parents=parents, exist_ok=exist_ok)

    with open(path, "w") as outfile:
        yaml.safe_dump(dict(**data), outfile, default_flow_style=False)


def read_yaml(path: Path) -> dict:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text())


load_yaml = read_yaml
save_yaml = write_yaml


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Terminal and SSH Utils
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
class SSHError(Exception):
    pass


def connect(
    host: str,
    user: str,
    password: str | None = None,
    key: str | Path | None = None,
    timeout: float = 10.0,
) -> paramiko.SSHClient:
    """Open an SSH connection to a Jetson.

    Tries key auth first if `key` is provided, then falls back to password.
    For initial bootstrap (fresh JetPack) use password='nvidia'.
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: dict = {
        "hostname": host,
        "username": user,
        "timeout": timeout,
    }

    if key is not None:
        connect_kwargs["key_filename"] = str(key)
    if password is not None:
        connect_kwargs["password"] = password

    try:
        client.connect(**connect_kwargs)
    except (
        paramiko.AuthenticationException,
        paramiko.SSHException,
        socket.error,
    ) as exc:
        client.close()
        raise SSHError(f"Could not connect to {user}@{host}: {exc}") from exc

    return client


def run(cmd: str | list[str], stdin_data: str | None = None) -> tuple[int, str, str]:
    return _run_subprocess(cmd, input=stdin_data)


def prompt_sudo_password() -> str | None:
    """Prompt for sudo password if passwordless sudo is not available.

    Call this before entering a ui.status() spinner — prompts inside spinners
    are hidden and will hang indefinitely waiting for input.

    Returns the password string, or None if sudo -n succeeds (no password needed).
    """
    check = subprocess.run("sudo -n true", shell=True, capture_output=True)
    if check.returncode != 0:
        from psilia_edge.ui import ask

        return ask("sudo password", password=True)
    return None


def sudo(cmd: str | list[str], password: str | None = None) -> tuple[int, str, str]:
    if password is None:
        password = prompt_sudo_password()

    if password is not None:
        full_cmd = ["sudo", "-S"] + cmd if isinstance(cmd, list) else f"sudo -S {cmd}"
        return _run_subprocess(full_cmd, input=password + "\n")
    else:
        full_cmd = ["sudo"] + cmd if isinstance(cmd, list) else f"sudo {cmd}"
        return _run_subprocess(full_cmd)


def _run_subprocess(
    cmd: str | list[str], input: str | None = None
) -> tuple[int, str, str]:
    result = subprocess.run(
        cmd, shell=isinstance(cmd, str), capture_output=True, text=True, input=input
    )
    return result.returncode, result.stdout, result.stderr


def run_with_spinner(cmd: str, msg: str, tail: int = 3) -> int:
    """Run a command with a spinner, showing the last `tail` lines of output.

    On failure, prints the full captured output for debugging. Returns the exit code.
    """
    from collections import deque
    from rich.live import Live
    from rich.padding import Padding
    from rich.spinner import Spinner
    from rich.console import Group

    lines: list[str] = []
    recent: deque[str] = deque(maxlen=tail)

    process = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    def _renderable():
        tail_text = "\n".join(f"[dim]{ln}[/dim]" for ln in recent)
        spinner = Spinner("dots", text=msg, style="bright_magenta")
        parts = [spinner]
        if tail_text:
            parts.append(ui.Text(tail_text))
        return Padding(Group(*parts), (0, ui.PADDING_LEFT), expand=False)

    with Live(
        _renderable(), console=ui.console, transient=True, refresh_per_second=8
    ) as live:
        for line in process.stdout:
            line = line.rstrip()
            lines.append(line)
            recent.append(line)
            live.update(_renderable())

    process.wait()

    if process.returncode != 0:
        ui.warn("Command output:")
        for line in lines:
            ui.print_line(f"[dim]{line}[/dim]", highlight=False)

    return process.returncode


def run_streamed(cmd: str, prefix: str = "") -> int:
    """Run a command and stream output live to the terminal via Rich.

    Each output line is printed with the given prefix. Returns the exit code.
    stdout and stderr are merged into a single stream.
    """
    process = subprocess.Popen(
        cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    for line in process.stdout:
        line = line.rstrip()
        ui.print_line(f"[dim]{prefix}{line}[/dim]", highlight=False)

    process.wait()
    return process.returncode


def sudo_streamed(cmd: str, password: str | None = None, prefix: str = "") -> int:
    """Run a command under sudo, streaming output live to the terminal via Rich.

    Prompts for the sudo password if not provided. Returns the exit code.
    """
    if password is None:
        password = prompt_sudo_password()

    sudo_cmd = f"sudo -S {cmd}" if password else f"sudo {cmd}"
    process = subprocess.Popen(
        sudo_cmd,
        shell=True,
        stdin=subprocess.PIPE if password else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if password:
        process.stdin.write(password + "\n")
        process.stdin.close()

    for line in process.stdout:
        line = line.rstrip()
        ui.print_line(f"[dim]{prefix}{line}[/dim]", highlight=False)

    process.wait()
    return process.returncode


def ssh_run(client: paramiko.SSHClient, cmd: str) -> tuple[int, str, str]:
    _, stdout, stderr = client.exec_command(cmd)
    rc = stdout.channel.recv_exit_status()
    return rc, stdout.read().decode(), stderr.read().decode()


def run_on_device_capture(device: str, cmd: str) -> tuple[int, str, str]:
    """Run a command on a registered device over SSH and capture its output.

    No TTY — use this for API/script calls where stdout needs to be read.
    Returns (exit_code, stdout, stderr).
    """
    ssh_argv = ["ssh", "-o", "LogLevel=ERROR", device, "bash", "-lc", f"'{cmd}'"]
    result = subprocess.run(ssh_argv, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def run_on_device(device: str, cmd: str, replace_process: bool = False) -> int:
    """Run a command on a registered device over SSH. That means the device
    must already be paired and have an SSH config entry.

    If replace_process=True, replaces the current process via execvp (use for
    attach so the TTY stays live). Otherwise runs as a subprocess and returns
    its exit code.

    -t allocates a pseudo-TTY on the remote side so Rich renders styled output.
    """
    # -o LogLevel=ERROR suppresses SSH's own informational messages (e.g.
    # "Connection to <host> closed.") that -t triggers at session end.
    ssh_argv = ["ssh", "-t", "-o", "LogLevel=ERROR", device, "bash", "-lc", f"'{cmd}'"]

    if replace_process:
        os.execvp("ssh", ssh_argv)

    result = subprocess.run(ssh_argv)
    return result.returncode


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Nested dict update utility (used in config)
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def deep_update(base: dict, update: dict, *, strict: bool = False) -> dict:
    """Recursively update `base` with `update`, merging nested dicts.

    If `strict`, the update may only fill in existing keys with matching types.
    New keys, missing keys, and type mismatches raise an error.
    """
    for key, value in update.items():
        if strict and key not in base:
            raise KeyError(f"Key {key!r} not found in base dict")
        base_value = base.get(key)
        if isinstance(value, dict) and isinstance(base_value, dict):
            deep_update(base_value, value, strict=strict)
        elif strict and key in base and type(value) is not type(base_value):
            raise TypeError(
                f"Type mismatch for key {key!r}: "
                f"base has {type(base_value).__name__}, "
                f"update has {type(value).__name__}"
            )
        else:
            base[key] = value
    return base


class NestedDict(dict):
    def update(self, other=dict):
        deep_update(self, other)

    def __ior__(self, other):
        self.update(other)
        return self
