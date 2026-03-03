"""SSH connection wrapper for Jetson communication."""

from __future__ import annotations

import socket
from pathlib import Path

import paramiko


class SSHError(Exception):
    pass


class JetsonConn:
    """Thin wrapper around a paramiko SSHClient."""

    def __init__(self, client: paramiko.SSHClient, host: str, user: str) -> None:
        self._client = client
        self.host = host
        self.user = user

    def run(self, cmd: str) -> tuple[int, str, str]:
        """Execute a command. Returns (returncode, stdout, stderr)."""
        _, stdout, stderr = self._client.exec_command(cmd)
        exit_code = stdout.channel.recv_exit_status()
        return exit_code, stdout.read().decode(), stderr.read().decode()

    def put(self, local: str | Path, remote: str) -> None:
        """Upload a local file to the remote path."""
        sftp = self._client.open_sftp()
        try:
            sftp.put(str(local), remote)
        finally:
            sftp.close()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> JetsonConn:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def connect(
    host: str,
    user: str = "nvidia",
    password: str | None = None,
    key: str | Path | None = None,
    timeout: float = 10.0,
) -> JetsonConn:
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

    return JetsonConn(client, host=host, user=user)
