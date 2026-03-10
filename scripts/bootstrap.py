#!/usr/bin/env python3
"""Psilia Edge — Bootstrap (Python)

Run from the directory where you want psilia installed:

    cd /ssd
    python bootstrap.py .

Use a local mock system dir (for testing) and skip the setup:

    # For instance from the root of the psilia-edge repo
    mkdir -p tests/_tmp/
    python scripts/bootstrap.py tests/_tmp/ --system-dir tests/_tmp/system --no-setup

"""

from __future__ import annotations

import grp
import json
import os
import pwd
import shutil
import subprocess
import sys
from importlib.metadata import distribution
from pathlib import Path

REPO_URL = "https://github.com/mirkoklukas/psilia-edge.git"
REPO_BRANCH = "dev"

DEFAULT_CONFIG_DIR = Path("/etc/psilia")
DEFAULT_RUN_DIR    = Path("/run/psilia")
DEFAULT_LOG_DIR    = Path("/var/log/psilia")

# ── helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _sudo(cmd: list[str]) -> tuple[int, str, str]:
    return _run(["sudo"] + cmd)


def _find_editable_repo_dir() -> Path | None:
    """Return the repo dir if psilia-edge is already pip-installed as editable, else None."""
    try:
        dist = distribution("psilia-edge")
        direct_url = dist.read_text("direct_url.json")
        if direct_url:
            data = json.loads(direct_url)
            if data.get("dir_info", {}).get("editable"):
                return Path(data["url"].removeprefix("file://"))
    except Exception:
        pass
    return None


def ok(msg: str)   -> None: print(f"✓ {msg}")
def info(msg: str) -> None: print(f"  {msg}")
def title(msg: str)-> None: print(f"\nBootstrap → {msg}")


def fail(msg: str) -> None:
    # TODO: raise an exception instead of sys.exit so individual steps are testable
    print(f"✗ {msg}", file=sys.stderr)
    sys.exit(1)


def header(base_dir: Path) -> None:
    print(f"""
    ▄
  ▚ █ ▞   Psilia Edge → BOOTSTRAP
    █     Install directory: {base_dir.parent}
    ▀
""")

# ── steps ─────────────────────────────────────────────────────────────────────

# TODO: When printing directory names, print them relative to cwd for readability.

def step_preflight() -> None:
    title("Preflight")
    for cmd in ["git", "pip", "sudo"]:
        if shutil.which(cmd) is None:
            fail(f"{cmd} not found — install it and retry.")
    ok("git, pip, sudo available")


def step_runtime_dirs(dirs) -> None:
    title("Directory structure")
    for d in dirs:
        if d.exists():
            info(f"{d} already exists — skipping")
        else:
            d.mkdir(parents=True, exist_ok=True)
            info(str(d))
    ok("Directories ready")


def step_install_or_existing(base_dir: Path) -> Path:
    """Clone the repo or use existing. Returns the repo dir."""
    title("Repository")

    if existing := _find_editable_repo_dir():
        info(f"psilia-edge already installed at {existing} — skipping clone")
        ok(f"Using existing repo {existing}")
        return existing

    repo_dir = base_dir / "psilia-edge"
    info(f"Cloning psilia-edge ({REPO_BRANCH}) to {repo_dir} …")
    rc, _, err = _run(["git", "clone", "--branch", REPO_BRANCH, REPO_URL, str(repo_dir)])
    if rc != 0:
        fail(f"git clone failed: {err}")
    ok(f"Repository cloned to {repo_dir}")

    title("Install psilia-edge")
    rc, _, err = _run(["pip", "install", "-e", str(repo_dir), "--quiet"])
    if rc != 0:
        fail(f"pip install failed: {err}")
    ok("psilia-edge installed — 'psilia' command now available")

    return repo_dir


def step_copy_ros(repo_dir: Path, base_dir: Path) -> None:
    title("ROS workspace")
    src = repo_dir / "ros" / "psilia_runtime"
    dst = base_dir / "ros" / "src" / "psilia_runtime"
    if not src.exists():
        fail(f"psilia_runtime not found at {src} — is the repo cloned?")
    shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
    ok(f"psilia_runtime ready at {dst}")


def step_system_dirs(config_dir: Path, run_dir: Path, log_dir: Path) -> None:
    title("System directories (requires sudo)")
    for d in [config_dir, run_dir, log_dir]:
        info(f"{d} will be created")
    user = os.environ.get("SUDO_USER") or os.getlogin()
    group = grp.getgrgid(pwd.getpwnam(user).pw_gid).gr_name
    for d in [config_dir, run_dir, log_dir]:
        rc, _, err = _sudo(["mkdir", "-p", str(d)])
        if rc != 0:
            fail(f"mkdir {d} failed: {err}")
        rc, _, err = _sudo(["chown", f"{user}:{group}", str(d)])
        if rc != 0:
            fail(f"chown {d} failed: {err}")
    ok(f"System directories ready ({config_dir}, {run_dir}, {log_dir})")


def step_write_device_config(
    device_config_path: Path,
    base_dir: Path,
    ros_dir: Path,
    data_dir: Path,
    repo_dir: Path
) -> None:
    title("Device config")
    # TODO: use yaml.dump instead of raw f-string — paths with colons produce invalid YAML
    device_config_path.write_text(
        f"runtime:\n"
        f"  base_dir: {base_dir}\n"
        f"  ros_dir: {ros_dir}\n"
        f"  data_dir: {data_dir}\n"
        f"  repo_dir: {repo_dir}\n"
    )
    ok(f"{device_config_path} written")

# ── main ──────────────────────────────────────────────────────────────────────

def main(install_dir: Path, system_dir: Path | None = None) -> dict:
    """Bootstrap Psilia Edge on a Jetson.

    Creates the directory structure under `<install_dir>/psilia/`, clones the
    repo, installs the `psilia` command, copies the ROS workspace, creates
    system directories (config, run, log), and writes the initial
    `device_config.yaml`.

    Args:
        install_dir: Parent directory for the psilia install (e.g. Path("/ssd")).
                     All runtime data is placed under `<install_dir>/psilia/`.
        system_dir:  Override for system directories. When set, config/run/log
                     are created as subdirs of this path instead of the defaults
                     (/etc/psilia, /run/psilia, /var/log/psilia). Useful for
                     testing without touching system paths.

    Returns:
        A dict with two keys:
          "runtime" — resolved paths for base_dir, ros_dir, data_dir, repo_dir
          "system"  — resolved paths for config_dir, run_dir, log_dir
    """
    install_dir = install_dir.resolve()
    if not install_dir.exists():
        fail(f"Install directory does not exist: {install_dir}")
    base_dir = install_dir / "psilia"

    if system_dir is not None:
        config_dir = system_dir.resolve() / "config"
        run_dir    = system_dir.resolve() / "run"
        log_dir    = system_dir.resolve() / "log"
    else:
        config_dir = DEFAULT_CONFIG_DIR
        run_dir    = DEFAULT_RUN_DIR
        log_dir    = DEFAULT_LOG_DIR

    system_dirs = {
        "config_dir": config_dir,
        "log_dir": log_dir,
        "run_dir": run_dir,
    }

    device_config_path = config_dir / "device_config.yaml"

    header(base_dir)
    repo_dir = step_install_or_existing(base_dir)

    ros_dir  = base_dir / "ros"
    data_dir = base_dir / "data"
    runtime_dirs = {
            "base_dir": base_dir,
            "ros_dir": ros_dir,
            "data_dir": data_dir,
            "repo_dir": repo_dir,
    }

    step_preflight()
    step_runtime_dirs(runtime_dirs.values())
    step_copy_ros(repo_dir, base_dir)
    step_system_dirs(**system_dirs)
    step_write_device_config(device_config_path, **runtime_dirs)

    return {
        "runtime": runtime_dirs,
        "system":  system_dirs,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description=(
            "Bootstrap Psilia Edge on a Jetson.\n\n"
            "Creates the directory structure, clones the psilia-edge repo, installs\n"
            "the `psilia` CLI, copies the ROS workspace, and writes the initial\n"
            "device config. By default, hands off to `psilia runtime setup` when done.\n\n"
            "Examples:\n"
            "  # Standard install onto an SSD:\n"
            "  python bootstrap.py /ssd\n\n"
            "  # Use a local mock system dir (for testing):\n"
            "  python bootstrap.py /tmp/test-install --system-dir /tmp/test-system --no-setup\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "install_dir",
        type=Path,
        metavar="DIR",
        help="Install directory to set up psilia within (e.g. /ssd)",
    )
    parser.add_argument(
        "--system-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="Mock system config directory instead of /etc/psilia, /run/psilia, /var/log/psilia (default: None)",
    )
    parser.add_argument(
        "--no-setup",
        action="store_true",
        help="Skip the setup wizard after bootstrapping.",
    )
    args = parser.parse_args()
    main(args.install_dir, args.system_dir)
    print("\nBootstrap complete. Not set up yet though.\n")
    if not args.no_setup:
        print("Calling setup wizard…")
        os.execvp("psilia", ["psilia", "runtime", "setup"])
