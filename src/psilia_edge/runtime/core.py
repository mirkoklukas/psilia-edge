"""Runtime utilities shared across the runtime package."""

from __future__ import annotations

from pathlib import Path

RUNTIME_CONFIG_PATH = Path("/opt/psilia/runtime_config.yaml")


def is_runtime_host() -> bool:
    """Return True if this machine is a runtime host (Jetson).

    Heuristic: runtime_config.yaml only exists after `psilia setup` has run.
    """
    return RUNTIME_CONFIG_PATH.exists()
