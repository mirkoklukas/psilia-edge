from pathlib import Path

import yaml


def save_yaml(path: Path, data: dict, parents=True, exist_ok=True) -> None:
    path.parent.mkdir(parents=parents, exist_ok=exist_ok)

    with open(path, 'w') as outfile:
        yaml.dump(data, outfile, default_flow_style=False)


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text())
