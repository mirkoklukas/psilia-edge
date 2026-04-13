"""Tests for runtime/config.py.

Run:
    python -m pytest -s tests/runtime -v
"""

from __future__ import annotations

import importlib

import pytest
import yaml
from rich.console import Console

console = Console()

@pytest.fixture(autouse=True)
def reload_config(runtime_env):
    """Reload runtime.config after env vars are set so module-level constants pick them up."""
    import psilia_edge.runtime.config as cfg

    importlib.reload(cfg)
    yield cfg
    importlib.reload(cfg)


def test_paths_respect_env_vars(runtime_env, reload_config):
    console.print(f"\nruntime_env: {runtime_env.keys()}")
    cfg = reload_config
    assert str(cfg.CONFIG_DIR) == str(runtime_env["config_dir"])
    assert str(cfg.RUN_DIR) == str(runtime_env["run_dir"])
    assert str(cfg.LOG_DIR) == str(runtime_env["log_dir"])
    assert cfg.DEVICE_CONFIG_PATH == runtime_env["config_path"]


def test_read_device_config_missing(runtime_env, reload_config):
    cfg = reload_config
    runtime_env["config_path"].unlink()
    assert cfg.read_device_config() == {}


def test_read_device_config(runtime_env, reload_config):
    cfg = reload_config
    data = {"runtime": {
        "base_dir": "/ssd/psilia",
        "ros_dir": "/ssd/psilia/ros",
        "data_dir": "/ssd/psilia/data"}
    }
    runtime_env["config_path"].write_text(yaml.dump(data))
    assert cfg.read_device_config() == data


def test_write_device_config(runtime_env, reload_config):
    cfg = reload_config
    data = {"runtime": {"base_dir": "/ssd/psilia"}}
    cfg.write_device_config(data)
    assert yaml.safe_load(runtime_env["config_path"].read_text()) == data


def test_get_dirs(runtime_env, reload_config):
    cfg = reload_config
    assert cfg.get_base_dir() == runtime_env["base_dir"]
    assert cfg.get_ros_dir() == runtime_env["ros_dir"]
    assert cfg.get_data_dir() == runtime_env["data_dir"]
