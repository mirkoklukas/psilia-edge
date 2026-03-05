"""LocalRunner — same interface as JetsonConn but runs commands locally via subprocess."""

from __future__ import annotations

import getpass
import shutil
import subprocess
from pathlib import Path


class LocalRunner:
    """Run commands locally with the same interface as JetsonConn."""

    def __init__(self) -> None:
        self.user = getpass.getuser()
        self._password = ""  # unused locally, kept for interface compat

    def run(self, cmd: str, stdin_data: str | None = None) -> tuple[int, str, str]:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            input=stdin_data,
        )
        return result.returncode, result.stdout, result.stderr

    def sudo(self, cmd: str) -> tuple[int, str, str]:
        result = subprocess.run(
            f"sudo {cmd}",
            shell=True,
            capture_output=True,
            text=True,
        )
        return result.returncode, result.stdout, result.stderr

    def put(self, local: str | Path, remote: str) -> None:
        shutil.copy2(str(local), remote)

    def put_dir(self, local: str | Path, remote: str) -> None:
        shutil.copytree(str(local), remote, dirs_exist_ok=True)
