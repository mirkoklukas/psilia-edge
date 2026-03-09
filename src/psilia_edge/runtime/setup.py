"""Psilia Edge — Jetson-side setup wizard.

Entry point (called by scripts/bootstrap.sh):
    psilia setup
"""

from __future__ import annotations

import getpass
import shutil
import subprocess
from pathlib import Path

from rich.prompt import Prompt

from psilia_edge.utils import run, run_streamed, sudo
from psilia_edge import ui
from psilia_edge.ui import console

_DEFAULT_INSTALL_DIR = "/ssd/psilia"
_DEFAULT_HOTSPOT_PASSWORD = "psilia1234"
_PSILIA_REPO_URL = "https://github.com/mirkoklukas/psilia-edge.git"
_PSILIA_REPO_BRANCH = "dev"


def _read_git_credentials(host: str) -> tuple[str, str] | None:
    creds_path = Path.home() / ".git-credentials"
    if not creds_path.exists():
        return None
    for line in creds_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            from urllib.parse import urlparse

            parsed = urlparse(line)
            if parsed.hostname == host and parsed.username and parsed.password:
                return parsed.username, parsed.password
        except Exception:
            continue
    return None


def _step_copy_ros(base: str) -> None:
    ui.title("Step 4 — ROS Package")

    src = Path(f"{base}/psilia-edge/ros/psilia_runtime")
    dst = f"{base}/ros/src/psilia_runtime"

    if not src.exists():
        ui.fail(f"psilia_runtime not found at {src} — is the repo cloned?")
        return

    with ui.status("Copying psilia_runtime…"):
        shutil.copytree(str(src), dst, dirs_exist_ok=True)

    ui.ok(f"psilia_runtime copied to {dst}")


def _step_docker() -> None:
    ui.title("Step 5 — Docker")
    with ui.status("Checking Docker…"):
        rc, ver, _ = run("docker --version")
    if rc == 0:
        ui.ok(f"Docker already installed ({ver.strip()})")
        return

    ui.info("Docker not found — installing…")
    with ui.status("Downloading Docker install script…"):
        rc, _, err = run("curl -fsSL https://get.docker.com -o /tmp/_get-docker.sh")
    if rc != 0:
        ui.fail(f"Failed to download Docker install script: {err.strip()}")
        return
    with ui.status("Installing Docker (this may take a while)…"):
        rc, _, err = sudo("sh /tmp/_get-docker.sh")
        run("rm -f /tmp/_get-docker.sh")
    if rc != 0:
        ui.fail(f"Docker install failed: {err.strip()}")
        return

    user = getpass.getuser()
    ui.info("[dim]sudo needed to add user to docker group[/dim]")
    sudo(f"usermod -aG docker {user}")
    _, ver, _ = run("docker --version")
    ui.ok(f"Docker installed ({ver.strip()})")
    ui.ok(f"User '{user}' added to docker group")


def _step_build_image(base: str) -> None:
    ui.title("Step 6 — Build Docker Image")
    ui.info("Building [bold]psilia/runtime:latest[/bold] — this may take a while…")
    ui.detail("source", f"{base}/psilia-edge/ros/Dockerfile")
    rc = run_streamed(
        f"docker build --network=host -t psilia/runtime:latest {base}/psilia-edge/ros"
    )
    if rc != 0:
        ui.fail("Docker build failed.")
    else:
        ui.ok("Docker image built: psilia/runtime:latest")


def _step_network(name: str) -> dict:
    from psilia_edge.network.hotspot import create_hotspot, find_active_hotspot
    from psilia_edge.network.probe import list_interfaces

    ui.title("Step 7 — Network Setup")
    ui.info("Configures a wifi hotspot on the Jetson (USB dongle preferred)")
    ui.info("[dim]so you can reach it in the field without a router.[/dim]")

    def runner(cmd: list[str], **_) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True)

    def sudo_runner(cmd: list[str], **_) -> subprocess.CompletedProcess:
        return subprocess.run(["sudo"] + list(cmd), capture_output=True, text=True)

    with ui.status("Detecting wifi interfaces and existing hotspot…"):
        ifaces = list_interfaces(runner)
        wifi_ifaces = [i for i in ifaces if i.is_wifi]
        existing_hotspot = None
        for wi in wifi_ifaces:
            existing_hotspot = find_active_hotspot(wi.name, runner)
            if existing_hotspot:
                break

    usb = [i for i in wifi_ifaces if i.is_usb_wifi]
    candidates = usb or wifi_ifaces
    ap_capable = [i for i in candidates if i.supports_ap] or candidates
    iface = ap_capable[0] if ap_capable else None

    if existing_hotspot:
        ui.ok(f"Existing hotspot found: [bold]{existing_hotspot}[/bold]")
        if not ui.confirm("Replace it?", default=False):
            ui.info("[dim]Keeping existing hotspot — config unchanged.[/dim]")
            return {}

    if iface is None:
        ui.warn("No wifi interface found — skipping network setup.")
        ui.info("[dim]Connect a USB wifi dongle and re-run 'psilia setup'.[/dim]")
        return {}
    elif iface.is_usb_wifi:
        ui.ok(f"USB wifi dongle detected: [bold]{iface.name}[/bold]")
    else:
        ui.warn(f"No USB dongle — using built-in wifi: [bold]{iface.name}[/bold]")
        ui.info(
            "[dim]Note: built-in wifi can't act as hotspot and client simultaneously on all hardware.[/dim]"
        )

    ssid = ui.ask("  Hotspot SSID", default=f"{name}-ap")
    password = ui.ask("  Hotspot password", default=_DEFAULT_HOTSPOT_PASSWORD)
    ui.detail("interface", f"[bold]{iface.name}[/bold]")
    ui.detail("ssid", f"[bold]{ssid}[/bold]")
    ui.detail("password", f"[bold]{password}[/bold]")
    ui.detail("ip", "[bold]10.42.0.1[/bold] (fixed, Jetson side)")

    with ui.status("  Creating hotspot…"):
        ok_result, err = create_hotspot(
            ifname=iface.name,
            password=password,
            ssid=ssid,
            con_name=f"{ssid}-Hotspot",
            runner=sudo_runner,
        )
    if ok_result:
        ui.ok(f"Hotspot '{ssid}' is up")
    else:
        ui.fail(f"Failed to create hotspot: {err}")
        ui.info("[dim]Configure manually with nmcli.[/dim]")

    return {"hotspot": {"ssid": ssid, "password": password}}


# TODO: implement this...
def _step_camera() -> dict:
    ui.title("Step 8 — Camera (optional)")
    if not ui.confirm("  Detect and configure connected camera now?", default=False):
        ui.info("[dim]Skipped — configure later with 'psilia config camera'.[/dim]")
        return {}
    ui.stub("detect USB stereo camera on Jetson")
    return {}


# TODO: implement this...
def _step_systemd() -> bool:
    ui.title("Step 9 — Autostart")
    ui.info("Installs a systemd service ([bold]psilia.service[/bold]) on the Jetson")
    ui.info("[dim]so the runtime starts automatically on boot.[/dim]")
    ui.stub("install /etc/systemd/system/psilia.service and reload daemon")
    autostart = ui.confirm("  Enable autostart on boot?", default=True)
    if autostart:
        ui.stub("systemctl enable psilia")
        ui.ok("Autostart enabled — runtime will start on next boot")
    else:
        ui.info("[dim]Autostart disabled — start manually with:[/dim] psilia start")
    return autostart


def _step_write_runtime_config(runtime_config: dict) -> None:
    from psilia_edge.runtime.config import RUNTIME_CONFIG_PATH, write_runtime_config

    ui.title("Runtime Config")
    with ui.status("Writing runtime config…"):
        write_runtime_config(runtime_config)
    ui.ok(f"Runtime config written to {RUNTIME_CONFIG_PATH}")


def _step_pull(base: str) -> bool:
    """git pull + pip install -e. Returns True on success."""
    repo_dir = f"{base}/psilia-edge"

    ui.title("Step 1 — Pull Latest")
    with ui.status("Pulling latest changes…"):
        rc, out, err = run(f"git -C {repo_dir} pull")
    if rc != 0:
        ui.fail(f"git pull failed: {err.strip()}")
        return False
    ui.ok(out.strip() or "Already up to date.")

    with ui.status("Updating package…"):
        rc, _, err = run(f"pip install -e {repo_dir}")
    if rc != 0:
        ui.fail(f"pip install failed: {err.strip()}")
        return False
    ui.ok("psilia-edge package updated")
    return True


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Entry points
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
def run_setup() -> None:
    """Run the setup wizard locally on the Jetson.

    Reads install paths from /opt/psilia/runtime_config.yaml, which is written
    by scripts/bootstrap.sh before this wizard is invoked.
    """
    _, name, _ = run("hostname")
    name = name.strip()

    ui.header(
        ["Runtime", "Setup"],
        "[dim]Starting fresh and setting up {name}. This includes ...[/dim]",
    )

    from psilia_edge.runtime.config import read_runtime_config

    runtime_config = read_runtime_config()
    base = runtime_config.get("runtime", {}).get("base_dir", _DEFAULT_INSTALL_DIR)
    runtime_config.setdefault("runtime", {})["image"] = "psilia/runtime:latest"

    _step_docker()
    _step_build_image(base)
    runtime_config |= _step_network(name)
    runtime_config |= _step_camera()
    runtime_config["runtime"]["autostart"] = _step_systemd()
    _step_write_runtime_config(runtime_config)

    ui.done(
        f"{name} set up.",
        "Run [bold]psilia runtime start[/bold] to launch the spatial runtime.",
    )


def run_update() -> None:
    """Pull latest repo and rebuild Docker image locally (runs on the Jetson)."""

    _, name, _ = run("hostname")
    name = name.strip()
    ui.header(["Runtime", "Update {name}"])

    from psilia_edge.runtime.config import read_runtime_config

    runtime_config = read_runtime_config()
    base = runtime_config.get("runtime", {}).get("base_dir", _DEFAULT_INSTALL_DIR)

    if not _step_pull(base):
        return
    _step_copy_ros(base)

    # Clear colcon build cache so any setup.py changes are picked up
    # (dirs are owned by root because they were created inside Docker)
    ui.fyi("sudo needed to remove Docker-owned build cache")
    for d in ["build", "install", "log"]:
        sudo(f"rm -rf {base}/ros/{d}")
    ui.ok("Colcon build cache cleared")
    _step_build_image(base)

    ui.done(
        f"{name} is up to date.",
        "Run [bold]psilia runtime start[/bold] to launch the spatial runtime.",
    )


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Appendix: old code from setup.py, kept here for reference
#   during the rewrite. Not used anymore.
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# NOTE: unused — handled by bootstrap.sh)
def _step_install_path(conn) -> dict:
    ui.title("Step 1 — Install Path")
    ui.info("The following will be installed under the base directory:")
    ui.item("[bold]psilia-edge/[/bold]       repo clone (~50 MB)")
    ui.item(
        "[bold]ros/[/bold]               ROS colcon workspace + build artifacts (~500 MB)"
    )
    ui.item(
        "[bold]data/recordings/[/bold]   MCAP recordings (grows with use — easily +25 GB)"
    )
    ui.info(
        "[dim]Use a path with plenty of free space — an SSD is strongly recommended.[/dim]"
    )
    console.print()
    base = Prompt.ask("  Install path", default=_DEFAULT_INSTALL_DIR)
    data_path = f"{base}/data"
    console.print()
    ui.detail("repo", f"[bold]{base}/psilia-edge[/bold]")
    ui.detail("ros", f"[bold]{base}/ros[/bold]")
    ui.detail("data", f"[bold]{data_path}/recordings[/bold]")
    return {"runtime": {"base_dir": base, "data_dir": data_path}}


# NOTE: unused — handled by bootstrap.sh)
def _step_create_dirs(conn, base: str) -> None:
    dirs = [
        "/opt/psilia",
        f"{base}/ros/src",
        f"{base}/data/recordings",
    ]
    ui.title("Step 2 — Directory Structure")
    for d in dirs:
        ui.item(d)
    ui.fyi("sudo needed to create system directories (/opt/psilia)")
    with ui.status("Creating directories…"):
        rc, _, err = conn.sudo(f"mkdir -p {' '.join(dirs)}")
    if rc != 0:
        ui.fail(f"mkdir failed: {err.strip()}")
        return
    with ui.status("Setting ownership…"):
        rc, _, err = conn.sudo(f"chown -R {conn.user} {base}")
    if rc != 0:
        ui.fail(f"chown failed: {err.strip()}")
    else:
        ui.ok("Directories created")


# NOTE: unused — handled by bootstrap.sh)
def _step_clone(conn, base: str) -> None:
    ui.title("Step 3 — Clone psilia-edge")

    repo_dir = f"{base}/psilia-edge"
    pull_cmd = f"git -C {repo_dir} pull"
    clone_cmd = (
        f"git clone --branch {_PSILIA_REPO_BRANCH} {_PSILIA_REPO_URL} {repo_dir}"
    )

    rc_check, _, _ = conn.run(f"test -d {repo_dir}/.git")
    if rc_check == 0:
        with ui.status("Pulling latest changes…"):
            rc, _, err = conn.run(pull_cmd)
        if rc != 0:
            ui.fail(f"git pull failed: {err.strip()}")
            return
        ui.ok("Repository updated")
    else:
        with ui.status(f"Cloning psilia-edge ({_PSILIA_REPO_BRANCH})…"):
            rc, _, err = conn.run(clone_cmd)

        if rc != 0:
            ui.warn(f"Clone failed: {err.strip()}")
            creds = _read_git_credentials("github.com")
            if creds:
                username, token = creds
                ui.info("[dim]Using credentials from ~/.git-credentials[/dim]")
            else:
                username = Prompt.ask("  GitHub username")
                token = Prompt.ask("  GitHub token/password", password=True)
            auth_url = _PSILIA_REPO_URL.replace(
                "https://", f"https://{username}:{token}@"
            )
            with ui.status("Retrying clone with credentials…"):
                rc, _, err = conn.run(
                    f"git clone --branch {_PSILIA_REPO_BRANCH} {auth_url} {repo_dir}"
                )

        if rc != 0:
            ui.fail(f"Clone failed: {err.strip()}")
            return
        ui.ok(f"Repository cloned to {repo_dir}")

    with ui.status("Running pip install -e .…"):
        rc, _, err = conn.run(f"pip install -e {repo_dir}")
    if rc != 0:
        ui.fail(f"pip install failed: {err.strip()}")
    else:
        ui.ok("psilia-edge installed")
