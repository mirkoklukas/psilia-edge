#!/usr/bin/env python3
"""Psilia Edge — Bootstrap

Clones psilia-edge onto this machine and installs the psilia CLI.
Run this once on a fresh Jetson (or laptop for dev).

    python bootstrap.py [DIR]

After bootstrapping, hands off to `psilia runtime init` to set up
the runtime home directory (dirs, ROS package, Docker image, config).

Examples:
    # Standard install on Jetson (clone into /ssd):
    python bootstrap.py /ssd

    # Dev install on laptop (clone into home dir):
    python bootstrap.py ~

    # Skip runtime init (set up manually later):
    python bootstrap.py /ssd --no-init
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/mirkoklukas/psilia-edge.git"
REPO_BRANCH = "dev"
DEFAULT_INSTALL_DIR = Path("/ssd")


# ── output helpers ────────────────────────────────────────────────────────────

def ok(msg: str)    -> None: print(f"  ✓ {msg}")
def info(msg: str)  -> None: print(f"    {msg}")
def title(msg: str) -> None: print(f"\n  ⏵⏵ {msg}")


def fail(msg: str) -> None:
    print(f"  ✗ {msg}", file=sys.stderr)
    sys.exit(1)


def header(install_dir: Path) -> None:
    print(f"\n  Ψ Psilia Edge → Bootstrap")
    print(f"    Install directory: {install_dir}")

# ── steps ─────────────────────────────────────────────────────────────────────

def _run(cmd: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _find_editable_repo_dir() -> Path | None:
    """Return the repo dir if psilia-edge is already pip-installed as editable, else None."""
    try:
        from importlib.metadata import distribution
        dist = distribution("psilia-edge")
        direct_url = dist.read_text("direct_url.json")
        if direct_url:
            data = json.loads(direct_url)
            if data.get("dir_info", {}).get("editable"):
                return Path(data["url"].removeprefix("file://"))
    except Exception:
        pass
    return None


def step_preflight() -> None:
    title("Preflight")
    for cmd in ["git", "pip"]:
        if shutil.which(cmd) is None:
            fail(f"{cmd} not found — install it and retry.")
    ok("git, pip available")


def step_install_or_existing(install_dir: Path) -> Path:
    """Clone the repo or use existing editable install. Returns the repo dir."""
    title("Repository")

    if existing := _find_editable_repo_dir():
        info(f"psilia-edge already installed (editable) at {existing}")
        ok("Using existing install — skipping clone")
        return existing

    repo_dir = install_dir / "psilia-edge"
    info(f"Cloning psilia-edge ({REPO_BRANCH}) → {repo_dir} …")
    rc, _, err = _run(["git", "clone", "--branch", REPO_BRANCH, REPO_URL, str(repo_dir)])
    if rc != 0:
        fail(f"git clone failed: {err}")
    ok(f"Cloned to {repo_dir}")

    title("Install psilia-edge")
    info("Running pip install -e . …")
    rc, _, err = _run(["pip", "install", "-e", str(repo_dir), "--quiet"])
    if rc != 0:
        fail(f"pip install failed: {err}")
    ok("psilia-edge installed — 'psilia' CLI now available")

    return repo_dir


# ── main ──────────────────────────────────────────────────────────────────────

def main(install_dir: Path) -> None:
    install_dir = install_dir.expanduser().resolve()
    if not install_dir.exists():
        fail(f"Install directory does not exist: {install_dir}")

    header(install_dir)
    step_preflight()
    step_install_or_existing(install_dir)
    runtime_home = install_dir / "psilia-runtime-home"

    ok("Core bootstrap done — handing off to `psilia runtime init`…")
    rc = subprocess.run(["psilia", "runtime", "init", str(runtime_home), "--mkdir", "--quiet"]).returncode
    sys.exit(rc)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Bootstrap Psilia Edge: clone repo and install the psilia CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "install_dir",
        type=Path,
        nargs="?",
        default="./",
        metavar="DIR",
        help=f"Directory to clone psilia-edge into",
    )
    args = parser.parse_args()
    main(args.install_dir)
