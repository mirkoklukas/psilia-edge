"""Fixtures for runtime tests.

Sets PSILIA_CONFIG_DIR, PSILIA_RUN_DIR, and PSILIA_LOG_DIR to tmp_path
subdirectories so all runtime code operates in an isolated sandbox.
"""

from __future__ import annotations

import yaml
import pytest


@pytest.fixture
def runtime_env(tmp_path, monkeypatch):
    """Isolated runtime environment with fake system directories."""
    config_dir = tmp_path / "etc" / "psilia"
    run_dir = tmp_path / "run" / "psilia"
    log_dir = tmp_path / "var" / "log" / "psilia"
    base_dir = tmp_path / "psilia"
    ros_dir = base_dir / "ros"
    data_dir = base_dir / "data"

    config_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    base_dir.mkdir(parents=True)
    ros_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)

    monkeypatch.setenv("PSILIA_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("PSILIA_RUN_DIR", str(run_dir))
    monkeypatch.setenv("PSILIA_LOG_DIR", str(log_dir))

    config_path = config_dir / "runtime_config.yaml"
    config_path.write_text(yaml.dump({
        "runtime": {
            "base_dir": str(base_dir),
            "ros_dir": str(ros_dir),
            "data_dir": str(data_dir),
        }
    }))

    return {
        "config_dir": config_dir,
        "run_dir": run_dir,
        "log_dir": log_dir,
        "config_path": config_path,
        "base_dir": base_dir,
        "ros_dir": ros_dir,
        "data_dir": data_dir,
    }
