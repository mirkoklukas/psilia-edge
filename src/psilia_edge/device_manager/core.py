"""Foundational constants and paths for the device manager (laptop side)."""

from __future__ import annotations

from pathlib import Path

CONFIG_PATH = Path.home() / ".psilia" / "config.yaml"
KEYS_DIR = Path.home() / ".psilia" / "keys"
DATA_DIR = Path.home() / "psilia-data"
