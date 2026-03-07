"""Psilia Edge — Jetson-side setup wizard.

Entry point (called by scripts/setup.sh after bootstrap):
    python -m psilia_edge.runtime.setup --install-dir /ssd/psilia
"""

from __future__ import annotations

from pathlib import Path

import yaml
from rich.prompt import Confirm, Prompt

from psilia_edge.device_manager.ssh import JetsonConn, LocalRunner
from psilia_edge import ui
from psilia_edge.ui import console

_DEFAULT_INSTALL_DIR = "/ssd/psilia"
_DEFAULT_HOTSPOT_PASSWORD = "psilia1234"
_PSILIA_REPO_URL = "https://github.com/mirkoklukas/psilia-edge.git"
_PSILIA_REPO_BRANCH = "main"


# ── step 1: install path ──────────────────────────────────────────────────────


def _step_install_path(conn) -> dict:
    ui.section_header("Step 1 — Install Path")
    ui.info("The following will be installed under the base directory:")
    ui.item("[bold]psilia-edge/[/bold]       repo clone (~50 MB)")
    ui.item("[bold]ros/[/bold]               ROS colcon workspace + build artifacts (~500 MB)")
    ui.item("[bold]data/recordings/[/bold]   MCAP recordings (grows with use — easily +25 GB)")
    ui.info("[dim]Use a path with plenty of free space — an SSD is strongly recommended.[/dim]")
    console.print()
    base = Prompt.ask("  Install path", default=_DEFAULT_INSTALL_DIR)
    data_path = f"{base}/data"
    console.print()
    ui.detail("repo",  f"[bold]{base}/psilia-edge[/bold]")
    ui.detail("ros",   f"[bold]{base}/ros[/bold]")
    ui.detail("data",  f"[bold]{data_path}/recordings[/bold]")
    return {"storage": {"base": base, "data_path": data_path}}


# ── step 2: create dirs ───────────────────────────────────────────────────────


def _step_create_dirs(conn, base: str) -> None:
    dirs = [
        "/opt/psilia",
        f"{base}/ros/src",
        f"{base}/data/recordings",
    ]
    ui.section_header("Step 2 — Directory Structure")
    for d in dirs:
        ui.item(d)
    with console.status("  Creating directories…"):
        rc, _, err = conn.sudo(f"mkdir -p {' '.join(dirs)}")
    if rc != 0:
        ui.fail(f"mkdir failed: {err.strip()}")
        return
    with console.status("  Setting ownership…"):
        rc, _, err = conn.sudo(f"chown -R {conn.user} {base}")
    if rc != 0:
        ui.fail(f"chown failed: {err.strip()}")
    else:
        ui.ok("Directories created")


# ── step 3: clone repo ────────────────────────────────────────────────────────


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


def _step_clone(conn, base: str) -> None:
    ui.section_header("Step 3 — Clone psilia-edge")

    repo_dir = f"{base}/psilia-edge"
    pull_cmd = f"git -C {repo_dir} pull"
    clone_cmd = f"git clone --branch {_PSILIA_REPO_BRANCH} {_PSILIA_REPO_URL} {repo_dir}"

    rc_check, _, _ = conn.run(f"test -d {repo_dir}/.git")
    if rc_check == 0:
        with console.status("  Pulling latest changes…"):
            rc, _, err = conn.run(pull_cmd)
        if rc != 0:
            ui.fail(f"git pull failed: {err.strip()}")
            return
        ui.ok("Repository updated")
    else:
        with console.status(f"  Cloning psilia-edge ({_PSILIA_REPO_BRANCH})…"):
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
            auth_url = _PSILIA_REPO_URL.replace("https://", f"https://{username}:{token}@")
            with console.status("  Retrying clone with credentials…"):
                rc, _, err = conn.run(
                    f"git clone --branch {_PSILIA_REPO_BRANCH} {auth_url} {repo_dir}"
                )

        if rc != 0:
            ui.fail(f"Clone failed: {err.strip()}")
            return
        ui.ok(f"Repository cloned to {repo_dir}")

    with console.status("  Running pip install -e .…"):
        rc, _, err = conn.run(f"pip install -e {repo_dir}")
    if rc != 0:
        ui.fail(f"pip install failed: {err.strip()}")
    else:
        ui.ok("psilia-edge installed")


# ── step 4: copy ROS package ──────────────────────────────────────────────────


def _step_copy_ros(conn, base: str) -> None:
    ui.section_header("Step 4 — ROS Package")

    dst = f"{base}/ros/src/psilia_runtime"

    if isinstance(conn, LocalRunner):
        import shutil as _shutil
        src = Path(f"{base}/psilia-edge/ros/psilia_runtime")
        if not src.exists():
            ui.fail(f"psilia_runtime not found at {src} — is the repo cloned?")
            return
        with console.status("  Copying psilia_runtime…"):
            _shutil.copytree(str(src), dst, dirs_exist_ok=True)
    else:
        repo_root = Path(__file__).parent.parent.parent
        local_ros = repo_root / "ros" / "psilia_runtime"
        if not local_ros.exists():
            ui.fail(f"Local psilia_runtime not found at {local_ros}")
            return
        with console.status("  Uploading psilia_runtime…"):
            conn.put_dir(local_ros, dst)

    ui.ok(f"psilia_runtime copied to {dst}")


# ── step 5: Docker ────────────────────────────────────────────────────────────


def _step_docker(conn) -> None:
    ui.section_header("Step 5 — Docker")
    with console.status("  Checking Docker…"):
        rc, _, _ = conn.run("docker --version")
    if rc == 0:
        _, ver, _ = conn.run("docker --version")
        ui.ok(f"Docker already installed ({ver.strip()})")
        return

    ui.info("Docker not found — installing…")
    with console.status("  Downloading Docker install script…"):
        rc, _, err = conn.run("curl -fsSL https://get.docker.com -o /tmp/_get-docker.sh")
    if rc != 0:
        ui.fail(f"Failed to download Docker install script: {err.strip()}")
        return
    with console.status("  Installing Docker (this may take a while)…"):
        rc, _, err = conn.sudo("sh /tmp/_get-docker.sh")
        conn.run("rm -f /tmp/_get-docker.sh")
    if rc != 0:
        ui.fail(f"Docker install failed: {err.strip()}")
        return

    conn.sudo(f"usermod -aG docker {conn.user}")
    _, ver, _ = conn.run("docker --version")
    ui.ok(f"Docker installed ({ver.strip()})")
    ui.ok(f"User '{conn.user}' added to docker group")


# ── step 6: build Docker image ────────────────────────────────────────────────


def _step_build_image(conn, base: str) -> None:
    ui.section_header("Step 6 — Build Docker Image")
    ui.info("Building [bold]psilia/runtime:latest[/bold] — this may take a while…")
    ui.detail("source", f"{base}/psilia-edge/ros/Dockerfile")
    with console.status("  Building Docker image…"):
        rc, _, err = conn.run(
            f"docker build --network=host -t psilia/runtime:latest {base}/psilia-edge/ros"
        )
    if rc != 0:
        ui.fail(f"Docker build failed: {err.strip()}")
    else:
        ui.ok("Docker image built: psilia/runtime:latest")


# ── step 7: network ───────────────────────────────────────────────────────────


def _step_network(conn, name: str) -> dict:
    from psilia_edge.network.hotspot import create_hotspot, find_active_hotspot
    from psilia_edge.network.probe import list_interfaces

    ui.section_header("Step 7 — Network Setup")
    ui.info("Configures a wifi hotspot on the Jetson (USB dongle preferred)")
    ui.info("[dim]so you can reach it in the field without a router.[/dim]")

    runner = conn.as_runner()
    sudo_runner = conn.as_sudo_runner()

    with console.status("  Detecting wifi interfaces and existing hotspot…"):
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
        if not Confirm.ask("  Replace it?", default=False):
            console.print("  [dim]Keeping existing hotspot — config unchanged.[/dim]")
            return {}

    if iface is None:
        ui.warn("No wifi interface found — skipping network setup.")
        ui.info("[dim]Connect a USB wifi dongle and re-run 'psilia setup'.[/dim]")
        return {}
    elif iface.is_usb_wifi:
        ui.ok(f"USB wifi dongle detected: [bold]{iface.name}[/bold]")
    else:
        ui.warn(f"No USB dongle — using built-in wifi: [bold]{iface.name}[/bold]")
        ui.info("[dim]Note: built-in wifi can't act as hotspot and client simultaneously on all hardware.[/dim]")

    ssid = Prompt.ask("  Hotspot SSID", default=f"{name}-ap")
    password = Prompt.ask("  Hotspot password", default=_DEFAULT_HOTSPOT_PASSWORD)
    ui.detail("interface", f"[bold]{iface.name}[/bold]")
    ui.detail("ssid",      f"[bold]{ssid}[/bold]")
    ui.detail("password",  f"[bold]{password}[/bold]")
    ui.detail("ip",        "[bold]10.42.0.1[/bold] (fixed, Jetson side)")

    with console.status("  Creating hotspot…"):
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


# ── step 8: camera ────────────────────────────────────────────────────────────


def _step_camera(conn) -> dict:
    ui.section_header("Step 8 — Camera (optional)")
    if not Confirm.ask("  Detect and configure connected camera now?", default=False):
        ui.info("[dim]Skipped — configure later with 'psilia config camera'.[/dim]")
        return {}
    ui.stub("detect USB stereo camera on Jetson")
    return {}


# ── step 9: systemd ───────────────────────────────────────────────────────────


def _step_systemd(conn) -> bool:
    ui.section_header("Step 9 — Autostart")
    ui.info("Installs a systemd service ([bold]psilia.service[/bold]) on the Jetson")
    ui.info("[dim]so the runtime starts automatically on boot.[/dim]")
    ui.stub("install /etc/systemd/system/psilia.service and reload daemon")
    autostart = Confirm.ask("  Enable autostart on boot?", default=True)
    if autostart:
        ui.stub("systemctl enable psilia")
        ui.ok("Autostart enabled — runtime will start on next boot")
    else:
        ui.info("[dim]Autostart disabled — start manually with:[/dim] psilia start")
    return autostart


# ── step 10: write runtime config ─────────────────────────────────────────────


def _write_runtime_config(conn, runtime_config: dict) -> None:
    ui.section_header("Step 10 — Runtime Config")
    config_yaml = yaml.dump(runtime_config, default_flow_style=False)
    tmp = "/tmp/_psilia_runtime_config.yaml"

    if isinstance(conn, LocalRunner):
        with console.status("  Writing runtime config…"):
            Path(tmp).write_text(config_yaml)
            rc, _, err = conn.sudo(f"cp {tmp} /opt/psilia/runtime_config.yaml")
            conn.run(f"rm -f {tmp}")
    else:
        with console.status("  Writing runtime config…"):
            rc, _, err = conn.run(f"cat > {tmp}", stdin_data=config_yaml)
            if rc == 0:
                rc, _, err = conn.sudo(f"cp {tmp} /opt/psilia/runtime_config.yaml")
                conn.run(f"rm -f {tmp}")

    if rc != 0:
        ui.fail(f"Failed to write runtime config: {err.strip()}")
    else:
        ui.ok("Runtime config written to /opt/psilia/runtime_config.yaml")


# ── update helpers ────────────────────────────────────────────────────────────


def _step_pull(conn, base: str) -> bool:
    """git pull + pip install -e. Returns True on success."""
    repo_dir = f"{base}/psilia-edge"

    ui.section_header("Step 1 — Pull Latest")
    with console.status("  Pulling latest changes…"):
        rc, out, err = conn.run(f"git -C {repo_dir} pull")
    if rc != 0:
        ui.fail(f"git pull failed: {err.strip()}")
        return False
    ui.ok(out.strip() or "Already up to date.")

    with console.status("  Updating package…"):
        rc, _, err = conn.run(f"pip install -e {repo_dir}")
    if rc != 0:
        ui.fail(f"pip install failed: {err.strip()}")
        return False
    ui.ok("psilia-edge package updated")
    return True


# ── entry points ──────────────────────────────────────────────────────────────


def run_setup_local(base: str | None = None) -> None:
    """Run the setup wizard locally on the Jetson."""
    runner = LocalRunner()
    rc, out, _ = runner.run("hostname")
    name = out.strip() or "psilia-jetson"

    ui.header(f"psilia setup — {name}", "[dim]Bootstrapping locally[/dim]")

    runtime_config: dict = {"runtime": {"image": "psilia/runtime:latest"}}

    if base:
        runtime_config["storage"] = {"base": base, "data_path": f"{base}/data"}
        runtime_config["runtime"]["ros_workspace"] = f"{base}/ros"
        ui.section_header("Step 1 — Install Path")
        ui.detail("base", f"[bold]{base}[/bold]")
        ui.detail("ros",  f"[bold]{base}/ros[/bold]")
        ui.detail("data", f"[bold]{base}/data/recordings[/bold]")
    else:
        runtime_config |= _step_install_path(runner)
        base = runtime_config["storage"]["base"]
        runtime_config["runtime"]["ros_workspace"] = f"{base}/ros"

    _step_create_dirs(runner, base)
    _step_clone(runner, base)
    _step_copy_ros(runner, base)
    _step_docker(runner)
    _step_build_image(runner, base)
    runtime_config |= _step_network(runner, name)
    runtime_config |= _step_camera(runner)
    runtime_config["runtime"]["autostart"] = _step_systemd(runner)
    _write_runtime_config(runner, runtime_config)

    ui.done(
        f"{name} bootstrapped.",
        "Run [bold]psilia start[/bold] to launch the spatial runtime.",
    )


def run_update_local(base: str) -> None:
    """Pull latest repo and rebuild Docker image locally (runs on the Jetson)."""
    import shutil as _shutil

    runner = LocalRunner()
    rc, out, _ = runner.run("hostname")
    name = out.strip() or "psilia-jetson"

    ui.header(f"psilia update — {name}", "[dim]Updating locally[/dim]")
    if not _step_pull(runner, base):
        return
    _step_copy_ros(runner, base)

    # Clear colcon build cache so any setup.py changes are picked up
    for d in ["build", "install", "log"]:
        cache = Path(f"{base}/ros/{d}")
        if cache.exists():
            _shutil.rmtree(cache)
    ui.ok("Colcon build cache cleared")

    _step_build_image(runner, base)

    ui.done(
        f"{name} updated.",
        "Run [bold]psilia start[/bold] to restart the runtime.",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Psilia Edge — local setup wizard")
    parser.add_argument(
        "--install-dir",
        required=True,
        help="Base installation directory (e.g. /ssd/psilia)",
    )
    args = parser.parse_args()
    run_setup_local(base=args.install_dir)
