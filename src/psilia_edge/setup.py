"""psilia setup — bootstrap a Jetson device (runs over SSH or locally).

Developer notes:
- Be explicit at every step about what gets written or changed — on the Jetson,
  on the laptop, or in config files. Tighten later once the UX is proven.
- Keep step order and numbers in sync with design-docs/design.md § psilia setup.
- Each step returns a dict with its runtime_config contribution (or {} if none).
  The runner merges all contributions and writes runtime_config.yaml at the end.
- TODO: consider splitting out a `runtime_setup` module (psilia_edge/runtime/setup.py)
  for the Jetson-side steps (dirs, clone, ROS, Docker, image, systemd, write config).
  This file would then only own the SSH orchestration and laptop-side steps (pair, sync).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from rich.prompt import Confirm, Prompt

from psilia_edge.ssh import JetsonConn, LocalRunner
from psilia_edge.ui import _fail, _ok, _warn, _stub, _info, _item, _detail, _section_header, _header, _done, console

_DEFAULT_HOTSPOT_PASSWORD = "psilia1234"
_PSILIA_REPO_URL = "https://github.com/mirkoklukas/psilia-edge.git"
_PSILIA_REPO_BRANCH = "dev"
_JETSON_DIRS = [
    "/opt/psilia",               # eMMC — config only (read at boot before SSD mounts)
    "/ssd/psilia/ros/src",       # colcon workspace
    "/ssd/psilia/data/recordings",  # MCAP recordings
]


# ── step 1: SSD ───────────────────────────────────────────────────────────────


def _step_ssd(conn: JetsonConn | LocalRunner) -> dict:
    _section_header("Step 1 — Storage / SSD")
    _info("Detects available drives and configures the data directory.")
    _stub("detect SSD, confirm mount point, configure /etc/fstab")
    mount = "/ssd/"
    _detail("mount", f"[bold]{mount}[/bold]")
    _detail("data", f"[bold]{mount}psilia/data/[/bold]")
    return {"storage": {"mount": mount, "data_path": "/ssd/psilia/data/"}}


# ── step 2: create dirs ───────────────────────────────────────────────────────


def _step_create_dirs(conn: JetsonConn | LocalRunner) -> None:
    _section_header("Step 2 — Directory Structure")
    for d in _JETSON_DIRS:
        _item(d)
    with console.status("  Creating directories on Jetson…"):
        rc, _, err = conn.sudo(f"mkdir -p {' '.join(_JETSON_DIRS)}")
    if rc != 0:
        _fail(f"mkdir failed: {err.strip()}")
        return
    with console.status("  Setting ownership…"):
        rc, _, err = conn.sudo(f"chown -R {conn.user} /ssd/psilia")
    if rc != 0:
        _fail(f"chown failed: {err.strip()}")
    else:
        _ok("Directories created on Jetson")


# ── step 3: clone repo ────────────────────────────────────────────────────────


def _read_git_credentials(host: str) -> tuple[str, str] | None:
    """Parse ~/.git-credentials and return (username, password) for the given host, or None."""
    creds_path = Path.home() / ".git-credentials"
    if not creds_path.exists():
        return None
    for line in creds_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        # Format: https://username:password@hostname
        try:
            from urllib.parse import urlparse
            parsed = urlparse(line)
            if parsed.hostname == host and parsed.username and parsed.password:
                return parsed.username, parsed.password
        except Exception:
            continue
    return None


def _step_clone(conn: JetsonConn | LocalRunner) -> None:
    _section_header("Step 3 — Clone psilia-edge")

    repo_dir = "/ssd/psilia/psilia-edge"
    clone_cmd = f"git clone --branch {_PSILIA_REPO_BRANCH} {_PSILIA_REPO_URL} {repo_dir}"
    pull_cmd = f"git -C {repo_dir} pull"

    # If already cloned, pull; otherwise clone.
    rc_check, _, _ = conn.run(f"test -d {repo_dir}/.git")
    if rc_check == 0:
        with console.status("  Pulling latest changes…"):
            rc, _, err = conn.run(pull_cmd)
        if rc != 0:
            _fail(f"git pull failed: {err.strip()}")
            return
        _ok("Repository updated")
    else:
        # Try public URL first (works if the repo is public)
        with console.status(f"  Cloning psilia-edge ({_PSILIA_REPO_BRANCH})…"):
            rc, _, err = conn.run(clone_cmd)

        if rc != 0:
            _warn(f"Clone failed: {err.strip()}")
            # Try stored credentials from ~/.git-credentials before prompting
            creds = _read_git_credentials("github.com")
            if creds:
                username, token = creds
                _info("[dim]Using credentials from ~/.git-credentials[/dim]")
            else:
                username = Prompt.ask("  GitHub username")
                token = Prompt.ask("  GitHub token/password", password=True)
            auth_url = _PSILIA_REPO_URL.replace("https://", f"https://{username}:{token}@")
            auth_clone = f"git clone --branch {_PSILIA_REPO_BRANCH} {auth_url} {repo_dir}"
            with console.status("  Retrying clone with credentials…"):
                rc, _, err = conn.run(auth_clone)

        if rc != 0:
            _fail(f"Clone failed: {err.strip()}")
            return
        _ok("Repository cloned to /ssd/psilia/psilia-edge")

    # TODO: install into a venv at /ssd/psilia/.venv instead of system Python.
    with console.status("  Running pip install -e .…"):
        rc2, _, err2 = conn.run("pip install -e /ssd/psilia/psilia-edge")
    if rc2 != 0:
        _fail(f"pip install failed: {err2.strip()}")
    else:
        _ok("psilia-edge installed — 'psilia' command now available on Jetson")


# ── step 4: copy ROS package ──────────────────────────────────────────────────


def _step_copy_ros(conn: JetsonConn | LocalRunner) -> None:
    _section_header("Step 4 — ROS Package")

    if isinstance(conn, LocalRunner):
        import shutil as _shutil
        # Repo is already cloned on the Jetson
        src = Path("/ssd/psilia/psilia-edge/ros/psilia_runtime")
        dst = "/ssd/psilia/ros/src/psilia_runtime"
        if not src.exists():
            _fail(f"psilia_runtime not found at {src} — is the repo cloned?")
            return
        with console.status("  Copying psilia_runtime…"):
            _shutil.copytree(str(src), dst, dirs_exist_ok=True)
    else:
        # Upload from the laptop repo checkout
        # __file__ = .../psilia-edge/src/psilia_edge/setup.py
        # repo_root = 3 levels up
        repo_root = Path(__file__).parent.parent.parent
        local_ros = repo_root / "ros" / "psilia_runtime"
        if not local_ros.exists():
            _fail(f"Local psilia_runtime not found at {local_ros}")
            return
        with console.status("  Uploading psilia_runtime…"):
            conn.put_dir(local_ros, "/ssd/psilia/ros/src/psilia_runtime")

    _ok("psilia_runtime copied to /ssd/psilia/ros/src/psilia_runtime")


# ── step 5: Docker ────────────────────────────────────────────────────────────


def _step_docker(conn: JetsonConn | LocalRunner) -> None:
    _section_header("Step 5 — Docker")
    with console.status("  Checking Docker…"):
        rc, _, _ = conn.run("docker --version")
    if rc == 0:
        _, ver, _ = conn.run("docker --version")
        _ok(f"Docker already installed ({ver.strip()})")
        return

    _info("Docker not found — installing…")
    with console.status("  Downloading Docker install script…"):
        rc, _, err = conn.run("curl -fsSL https://get.docker.com -o /tmp/_get-docker.sh")
    if rc != 0:
        _fail(f"Failed to download Docker install script: {err.strip()}")
        return
    with console.status("  Installing Docker (this may take a while)…"):
        rc, _, err = conn.sudo("sh /tmp/_get-docker.sh")
        conn.run("rm -f /tmp/_get-docker.sh")
    if rc != 0:
        _fail(f"Docker install failed: {err.strip()}")
        return

    conn.sudo(f"usermod -aG docker {conn.user}")
    _, ver, _ = conn.run("docker --version")
    _ok(f"Docker installed ({ver.strip()})")
    _ok(f"User '{conn.user}' added to docker group")


# ── step 6: build Docker image ───────────────────────────────────────────────


def _step_build_image(conn: JetsonConn | LocalRunner) -> None:
    _section_header("Step 6 — Build Docker Image")
    _info("Builds [bold]psilia/runtime:latest[/bold] on the Jetson.")
    _detail("source", "[dim]/ssd/psilia/psilia-edge/ros/Dockerfile[/dim]")
    _info("[dim]This step might take a while on first run.[/dim]")
    _stub("docker build -t psilia/runtime:latest /ssd/psilia/psilia-edge/ros")
    _ok("Docker image built: psilia/runtime:latest")

# ── step 7: network ───────────────────────────────────────────────────────────


def _step_network(conn: JetsonConn | LocalRunner, name: str) -> dict:
    from psilia_edge.network.hotspot import create_hotspot, find_active_hotspot
    from psilia_edge.network.probe import list_interfaces

    _section_header("Step 7 — Network Setup")
    _info("Configures a wifi hotspot on the Jetson (USB dongle preferred)")
    _info("[dim]so you can reach it in the field without a router.[/dim]")

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
        _ok(f"Existing hotspot found: [bold]{existing_hotspot}[/bold]")
        if not Confirm.ask("  Replace it?", default=False):
            console.print("  [dim]Keeping existing hotspot — config unchanged.[/dim]")
            return {}

    if iface is None:
        _warn("No wifi interface found — skipping network setup.")
        _info("[dim]Connect a USB wifi dongle and re-run 'psilia setup'.[/dim]")
        return {}
    elif iface.is_usb_wifi:
        _ok(f"USB wifi dongle detected: [bold]{iface.name}[/bold]")
    else:
        _warn(f"No USB dongle — using built-in wifi: [bold]{iface.name}[/bold]")
        _info("[dim]Note: built-in wifi can't act as hotspot and client simultaneously on all hardware.[/dim]")

    ssid = Prompt.ask("  Hotspot SSID", default=f"{name}-ap")
    password = Prompt.ask("  Hotspot password", default=_DEFAULT_HOTSPOT_PASSWORD)
    _info("[dim]Will configure:[/dim]")
    _detail("interface", f"[bold]{iface.name}[/bold]")
    _detail("ssid",      f"[bold]{ssid}[/bold]")
    _detail("password",  f"[bold]{password}[/bold]")
    _detail("ip",        "[bold]10.42.0.1[/bold] (fixed, Jetson side)")

    with console.status("  Creating hotspot…"):
        ok, err = create_hotspot(
            ifname=iface.name,
            password=password,
            ssid=ssid,
            con_name=f"{ssid}-Hotspot",
            runner=sudo_runner,
        )
    if ok:
        _ok(f"Hotspot '{ssid}' is up")
    else:
        _fail(f"Failed to create hotspot: {err}")
        _info("[dim]Configure manually with nmcli.[/dim]")

    return {"hotspot": {"ssid": ssid, "password": password}}


# ── step 8: camera ───────────────────────────────────────────────────────────


def _step_camera(conn: JetsonConn | LocalRunner) -> dict:
    _section_header("Step 8 — Camera (optional)")
    if not Confirm.ask("  Detect and configure connected camera now?", default=False):
        _info("[dim]Skipped — configure later with 'psilia config camera'.[/dim]")
        return {}
    _stub("detect USB stereo camera on Jetson")
    return {}


# ── step 9: systemd ──────────────────────────────────────────────────────────


def _step_systemd(conn: JetsonConn | LocalRunner) -> bool:
    _section_header("Step 9 — Autostart")
    _info("Installs a systemd service ([bold]psilia.service[/bold]) on the Jetson")
    _info("[dim]so the runtime starts automatically on boot.[/dim]")
    _stub("install /etc/systemd/system/psilia.service and reload daemon")
    autostart = Confirm.ask("  Enable autostart on boot?", default=True)
    if autostart:
        _stub("systemctl enable psilia")
        _ok("Autostart enabled — runtime will start on next boot")
    else:
        _info("[dim]Autostart disabled — start manually with:[/dim] psilia start")
    return autostart


# ── step 10: write runtime config ────────────────────────────────────────────


def _write_runtime_config(conn: JetsonConn | LocalRunner, runtime_config: dict) -> None:
    _section_header("Step 10 — Runtime Config")
    config_yaml = yaml.dump(runtime_config, default_flow_style=False)
    tmp = "/tmp/_psilia_runtime_config.yaml"

    if isinstance(conn, LocalRunner):
        with console.status("  Writing runtime config…"):
            Path(tmp).write_text(config_yaml)
            rc, _, err = conn.sudo(f"mkdir -p /opt/psilia && cp {tmp} /opt/psilia/runtime_config.yaml")
            conn.run(f"rm -f {tmp}")
    else:
        with console.status("  Writing runtime config…"):
            rc, _, err = conn.run(f"cat > {tmp}", stdin_data=config_yaml)
            if rc == 0:
                rc, _, err = conn.sudo(f"cp {tmp} /opt/psilia/runtime_config.yaml")
                conn.run(f"rm -f {tmp}")

    if rc != 0:
        _fail(f"Failed to write runtime config: {err.strip()}")
    else:
        _ok("Runtime config written to /opt/psilia/runtime_config.yaml")


# ── entry points ──────────────────────────────────────────────────────────────


def run_setup_remote(device: str) -> None:
    """Bootstrap a registered Jetson device over SSH (runs from the laptop)."""
    from psilia_edge.config import read_laptop_config, sync_device_config
    from psilia_edge.ssh import SSHError, connect

    config = read_laptop_config()
    devices = config.get("devices", {})
    if device not in devices:
        _fail(f"Device '{device}' not registered. Run 'psilia pair' first.")
        return

    dev = devices[device]
    host = dev["host"]
    user = dev["user"]
    key = dev.get("key")

    _header(f"psilia setup — {device}", f"[dim]Bootstrapping over SSH as {user}@{host}[/dim]")
    try:
        with console.status("  Connecting…"):
            conn = connect(host, user=user, key=key)
    except SSHError as exc:
        _fail(f"SSH connection failed: {exc}")
        return

    if not conn._password:
        conn._password = Prompt.ask("  sudo password for Jetson", password=True)

    with conn:
        runtime_config: dict = {
            "runtime": {
                "image": "psilia/runtime:latest",
                "ros_workspace": "/ssd/psilia/ros/",
            }
        }
        runtime_config |= _step_ssd(conn)
        _step_create_dirs(conn)
        _step_clone(conn)
        _step_copy_ros(conn)
        _step_docker(conn)
        _step_build_image(conn)
        runtime_config |= _step_network(conn, device)
        runtime_config |= _step_camera(conn)
        runtime_config["runtime"]["autostart"] = _step_systemd(conn)
        _write_runtime_config(conn, runtime_config)
        sync_device_config(device, conn)

    _done(
        f"{device} bootstrapped.",
        f"Run [bold]psilia start {device}[/bold] to launch the spatial runtime.",
    )


def run_setup_local() -> None:
    """Bootstrap this device locally (runs directly on the Jetson)."""
    runner = LocalRunner()

    # Use current hostname as the device name for config/hotspot SSID defaults
    rc, out, _ = runner.run("hostname")
    name = out.strip() or "psilia-jetson"

    _header(f"psilia setup — {name}", "[dim]Bootstrapping locally[/dim]")

    runtime_config: dict = {
        "runtime": {
            "image": "psilia/runtime:latest",
            "ros_workspace": "/ssd/psilia/ros/",
        }
    }
    runtime_config |= _step_ssd(runner)
    _step_create_dirs(runner)
    _step_clone(runner)
    _step_copy_ros(runner)
    _step_docker(runner)
    _step_build_image(runner)
    runtime_config |= _step_network(runner, name)
    runtime_config |= _step_camera(runner)
    runtime_config["runtime"]["autostart"] = _step_systemd(runner)
    _write_runtime_config(runner, runtime_config)

    _done(
        f"{name} bootstrapped.",
        "Run [bold]psilia start[/bold] to launch the spatial runtime.",
    )
