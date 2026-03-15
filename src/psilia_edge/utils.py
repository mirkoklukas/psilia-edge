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
    path.write_text(yaml.dump(dict(**data), default_flow_style=False))


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
        check = subprocess.run("sudo -n true", shell=True, capture_output=True)
        if check.returncode != 0:
            from psilia_edge.ui import ask

            password = ask("sudo password", password=True)

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


def ssh_run(client: paramiko.SSHClient, cmd: str) -> tuple[int, str, str]:
    _, stdout, stderr = client.exec_command(cmd)
    rc = stdout.channel.recv_exit_status()
    return rc, stdout.read().decode(), stderr.read().decode()


def run_on_device(device: str, cmd: str, replace_process: bool = False) -> int:
    """Run a command on a registered device over SSH. That means the device
    must already be paired and have an SSH config entry.

    If replace_process=True, replaces the current process via execvp (use for
    attach so the TTY stays live). Otherwise runs as a subprocess and returns
    its exit code.

    -t allocates a pseudo-TTY on the remote side so Rich renders styled output.
    """
    ssh_argv = ["ssh", "-t", device, "bash", "-lc", f"'{cmd}'"]

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
