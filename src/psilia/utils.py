from __future__ import annotations

from pathlib import Path

import yaml
from rich.console import Console

console = Console()


class _NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def write_yaml(path: Path, data: dict, parents=True, exist_ok=True) -> None:
    path.parent.mkdir(parents=parents, exist_ok=exist_ok)

    with open(path, "w") as outfile:
        yaml.dump(
            dict(**data), outfile, Dumper=_NoAliasDumper, default_flow_style=False
        )


def read_yaml(path: Path) -> dict:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text())


load_yaml = read_yaml
save_yaml = write_yaml


def get_root_dir() -> Path:
    """Return the repo root (the directory containing pyproject.toml)."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError(
        "Could not locate repo root (no pyproject.toml found above this file)"
    )
