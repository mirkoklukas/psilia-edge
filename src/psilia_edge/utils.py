from __future__ import annotations

import os
import socket
import subprocess
from pathlib import Path

import paramiko

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


def run(cmd: str, stdin_data: str | None = None) -> tuple[int, str, str]:
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, input=stdin_data)
    return result.returncode, result.stdout, result.stderr


def sudo(cmd: str, stdin_data: str | None = None) -> tuple[int, str, str]:
    result = subprocess.run(f"sudo {cmd}", shell=True, capture_output=True, text=True, input=stdin_data)
    return result.returncode, result.stdout, result.stderr


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