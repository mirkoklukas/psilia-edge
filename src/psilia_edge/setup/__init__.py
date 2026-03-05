"""psilia setup — bootstrap a Jetson device (runs over SSH or locally)."""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import yaml
from rich.console import Console
from rich.prompt import Confirm, Prompt

from psilia_edge.init.ssh import JetsonConn
from psilia_edge.setup.runner import LocalRunner

console = Console()

_DEFAULT_HOTSPOT_PASSWORD = "psilia1234"
_PSILIA_REPO_URL = "https://github.com/mirkoklukas/psilia-edge.git"
_PSILIA_REPO_BRANCH = "dev"
_JETSON_DIRS = [
    "/opt/psilia",               # eMMC — config only (read at boot before SSD mounts)
    "/ssd/psilia/ros/src",       # colcon workspace
    "/ssd/psilia/data/recordings",  # MCAP recordings
]


# ── helpers ───────────────────────────────────────────────────────────────────


def _ok(msg: str) -> None:
    console.print(f"  [green]✓[/green] {msg}")


def _fail(msg: str) -> None:
    console.print(f"  [red]✗[/red] {msg}")


def _stub(msg: str = "not yet implemented") -> None:
    console.print(f"  [dim]({msg})[/dim]")


def _ssh_runner(conn: JetsonConn):
    """Return a runner compatible with psilia_edge.network.* that runs commands over SSH."""
    def runner(cmd: list[str], capture_output: bool = False, text: bool = False, **_):
        shell_cmd = " ".join(shlex.quote(str(c)) for c in cmd)
        rc, stdout, _ = conn.run(shell_cmd)
        return subprocess.CompletedProcess(cmd, rc, stdout=stdout)
    return runner


def _ssh_sudo_runner(conn: JetsonConn):
    """Like _ssh_runner but runs each command under sudo -S."""
    def runner(cmd: list[str], capture_output: bool = False, text: bool = False, **_):
        shell_cmd = "sudo -S " + " ".join(shlex.quote(str(c)) for c in cmd)
        rc, stdout, _ = conn.run(shell_cmd, stdin_data=(conn._password or "") + "\n")
        return subprocess.CompletedProcess(cmd, rc, stdout=stdout)
    return runner


def _local_runner():
    """Return a runner compatible with psilia_edge.network.* that runs commands locally."""
    def runner(cmd: list[str], capture_output: bool = False, text: bool = False, **_):
        return subprocess.run(cmd, capture_output=True, text=True)
    return runner


def _local_sudo_runner():
    """Like _local_runner but prepends sudo."""
    def runner(cmd: list[str], capture_output: bool = False, text: bool = False, **_):
        return subprocess.run(["sudo"] + list(cmd), capture_output=True, text=True)
    return runner


# ── step 4: network ───────────────────────────────────────────────────────────


def _step_network(conn: JetsonConn | LocalRunner, name: str) -> tuple[str, str]:
    from psilia_edge.network.hotspot import create_hotspot, find_active_hotspot
    from psilia_edge.network.probe import list_interfaces

    console.rule("[bold]Step 4 — Network Setup")
    console.print(
        "  Configures a wifi hotspot on the Jetson (USB dongle preferred)\n"
        "  so you can reach it in the field without a router."
    )

    if isinstance(conn, LocalRunner):
        runner = _local_runner()
        sudo_runner = _local_sudo_runner()
    else:
        runner = _ssh_runner(conn)
        sudo_runner = _ssh_sudo_runner(conn)

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
            console.print("  [dim]Keeping existing hotspot.[/dim]")
            return existing_hotspot, ""

    if iface is None:
        console.print("  [yellow]⚠[/yellow]  No wifi interface found — skipping network setup.")
        console.print("  [dim]Connect a USB wifi dongle and re-run 'psilia setup'.[/dim]")
        return f"{name}-ap", ""
    elif iface.is_usb_wifi:
        _ok(f"USB wifi dongle detected: [bold]{iface.name}[/bold]")
    else:
        console.print(f"  [yellow]⚠[/yellow]  No USB dongle — using built-in wifi: [bold]{iface.name}[/bold]")
        console.print("  [dim]Note: built-in wifi can't act as hotspot and client simultaneously on all hardware.[/dim]")

    ssid = Prompt.ask("  Hotspot SSID", default=f"{name}-ap")
    password = Prompt.ask("  Hotspot password", default=_DEFAULT_HOTSPOT_PASSWORD)
    console.print("\n  [dim]Will configure:[/dim]")
    console.print(f"    Interface: [bold]{iface.name}[/bold]")
    console.print(f"    SSID:      [bold]{ssid}[/bold]")
    console.print(f"    Password:  [bold]{password}[/bold]")
    console.print("    IP:        [bold]10.42.0.1[/bold] (fixed, Jetson side)")

    with console.status("  Creating hotspot…"):
        ok = create_hotspot(
            ifname=iface.name,
            password=password,
            ssid=ssid,
            con_name=f"{ssid}-Hotspot",
            runner=sudo_runner,
        )
    if ok:
        _ok(f"Hotspot '{ssid}' is up")
    else:
        _fail("Failed to create hotspot — configure manually with nmcli")

    return ssid, password


# ── step 5: SSD ───────────────────────────────────────────────────────────────


def _step_ssd(conn: JetsonConn | LocalRunner) -> str:
    console.rule("[bold]Step 5 — Storage / SSD")
    console.print("  Detects available drives and configures the data directory.")
    _stub("detect SSD, confirm mount point, configure /etc/fstab")
    mount = "/ssd/"
    console.print(f"  [dim]Defaulting to mount point:[/dim] [bold]{mount}[/bold]")
    console.print(f"  [dim]Data will be stored at:[/dim]   [bold]{mount}psilia/data/[/bold]")
    return mount


# ── step 6: create dirs ───────────────────────────────────────────────────────


def _step_create_dirs(conn: JetsonConn | LocalRunner) -> None:
    console.rule("[bold]Step 6 — Directory Structure")
    for d in _JETSON_DIRS:
        console.print(f"  [dim]→[/dim] {d}")
    with console.status("  Creating directories…"):
        rc, _, err = conn.sudo(f"mkdir -p {' '.join(_JETSON_DIRS)}")
    if rc != 0:
        _fail(f"mkdir failed: {err.strip()}")
        return
    with console.status("  Setting ownership…"):
        rc, _, err = conn.sudo(f"chown -R {conn.user} /ssd/psilia")
    if rc != 0:
        _fail(f"chown failed: {err.strip()}")
    else:
        _ok("Directories created")


# ── step 7: clone repo ────────────────────────────────────────────────────────


def _step_clone(conn: JetsonConn | LocalRunner) -> None:
    console.rule("[bold]Step 7 — Clone psilia-edge")

    already_cloned = f"test -d /ssd/psilia/psilia-edge/.git"
    clone_cmd = f"git clone --branch {_PSILIA_REPO_BRANCH} {_PSILIA_REPO_URL} /ssd/psilia/psilia-edge"

    if isinstance(conn, LocalRunner):
        # Local: try public URL first; prompt for token if clone fails
        with console.status(f"  Cloning psilia-edge ({_PSILIA_REPO_BRANCH})…"):
            rc, _, err = conn.run(f"{already_cloned} || {clone_cmd}")
        if rc != 0:
            console.print(f"  [yellow]Clone failed:[/yellow] {err.strip()}")
            username = Prompt.ask("  GitHub username")
            token = Prompt.ask("  GitHub token/password", password=True)
            auth_url = _PSILIA_REPO_URL.replace("https://", f"https://{username}:{token}@")
            auth_clone = f"git clone --branch {_PSILIA_REPO_BRANCH} {auth_url} /ssd/psilia/psilia-edge"
            with console.status("  Retrying clone with credentials…"):
                rc, _, err = conn.run(f"{already_cloned} || {auth_clone}")
    else:
        # Remote: copy git credentials from laptop if available
        creds_path = Path.home() / ".git-credentials"
        if creds_path.exists():
            with console.status("  Copying git credentials…"):
                conn.put(creds_path, "/tmp/.git-credentials")
            conn.run(
                "git config --global credential.helper "
                "'store --file /tmp/.git-credentials'"
            )
        with console.status(f"  Cloning psilia-edge ({_PSILIA_REPO_BRANCH})…"):
            rc, _, err = conn.run(f"{already_cloned} || {clone_cmd}")
        if creds_path.exists():
            conn.run("rm -f /tmp/.git-credentials")
            conn.run("git config --global --unset credential.helper || true")

    if rc != 0:
        _fail(f"Clone failed: {err.strip()}")
        return

    _ok("Repository ready at /ssd/psilia/psilia-edge")
    # TODO: install into a venv at /ssd/psilia/.venv instead of system Python.
    with console.status("  Running pip install -e .…"):
        rc2, _, err2 = conn.run("pip install -e /ssd/psilia/psilia-edge")
    if rc2 != 0:
        _fail(f"pip install failed: {err2.strip()}")
    else:
        _ok("pip install -e . done")


# ── step 8: copy ROS package ──────────────────────────────────────────────────


def _step_copy_ros(conn: JetsonConn | LocalRunner) -> None:
    console.rule("[bold]Step 8 — ROS Package")

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
        # __file__ = .../psilia-edge/src/psilia_edge/setup/__init__.py
        # repo_root = 4 levels up
        repo_root = Path(__file__).parent.parent.parent.parent
        local_ros = repo_root / "ros" / "psilia_runtime"
        if not local_ros.exists():
            _fail(f"Local psilia_runtime not found at {local_ros}")
            return
        with console.status("  Uploading psilia_runtime…"):
            conn.put_dir(local_ros, "/ssd/psilia/ros/src/psilia_runtime")

    _ok("psilia_runtime copied to /ssd/psilia/ros/src/psilia_runtime")


# ── step 9: Docker ────────────────────────────────────────────────────────────


def _step_docker(conn: JetsonConn | LocalRunner) -> None:
    console.rule("[bold]Step 9 — Docker")
    with console.status("  Checking Docker…"):
        rc, _, _ = conn.run("docker --version")
    if rc == 0:
        _ok("Docker already installed")
        return

    console.print("  Docker not found — installing…")
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
    _ok("Docker installed")


# ── step 10: build Docker image ───────────────────────────────────────────────


def _step_build_image(conn: JetsonConn | LocalRunner) -> None:
    console.rule("[bold]Step 10 — Build Docker Image")
    console.print(
        "  Builds [bold]psilia/runtime:latest[/bold] on the Jetson.\n"
        "  Source: [dim]/ssd/psilia/psilia-edge/ros/Dockerfile[/dim]\n"
        "  This step will take 10–20 minutes on first run."
    )
    _stub("docker build -t psilia/runtime:latest /ssd/psilia/psilia-edge/ros")


# ── step 11: camera ───────────────────────────────────────────────────────────


def _step_camera(conn: JetsonConn | LocalRunner) -> None:
    console.rule("[bold]Step 11 — Camera (optional)")
    if not Confirm.ask("  Detect and configure connected camera now?", default=False):
        console.print(
            "  [dim]Skipped — configure later with 'psilia config camera'.[/dim]"
        )
        return
    _stub("detect USB stereo camera on Jetson")


# ── step 12: systemd ──────────────────────────────────────────────────────────


def _step_systemd(conn: JetsonConn | LocalRunner) -> bool:
    console.rule("[bold]Step 12 — Autostart")
    console.print(
        "  Installs a systemd service ([bold]psilia.service[/bold]) on the Jetson\n"
        "  so the runtime starts automatically on boot."
    )
    _stub("install /etc/systemd/system/psilia.service and reload daemon")
    autostart = Confirm.ask("  Enable autostart on boot?", default=True)
    if autostart:
        _stub("systemctl enable psilia")
        _ok("Autostart enabled — runtime will start on next boot")
    else:
        console.print("  [dim]Autostart disabled — start manually with:[/dim] psilia start")
    return autostart


# ── step 15: write Jetson config ─────────────────────────────────────────────


def _step_write_jetson_config(
    conn: JetsonConn | LocalRunner,
    mount: str,
    autostart: bool,
    hotspot_ssid: str,
    hotspot_password: str,
    camera: str | None,
) -> None:
    console.rule("[bold]Step 15 — Jetson Config")
    jetson_config = {
        "storage": {
            "mount": mount,
            "data_path": "/ssd/psilia/data/",
        },
        "runtime": {
            "image": "psilia/runtime:latest",
            "ros_workspace": "/ssd/psilia/ros/",
            "autostart": autostart,
        },
        "camera": {
            "type": camera,
        },
        "hotspot": {
            "ssid": hotspot_ssid,
            "password": hotspot_password,
        },
    }
    config_yaml = yaml.dump(jetson_config, default_flow_style=False)
    tmp = "/tmp/_psilia_jetson_config.yaml"

    if isinstance(conn, LocalRunner):
        with console.status("  Writing Jetson config…"):
            Path(tmp).write_text(config_yaml)
            rc, _, err = conn.sudo(f"mkdir -p /opt/psilia && cp {tmp} /opt/psilia/config.yaml")
            conn.run(f"rm -f {tmp}")
    else:
        with console.status("  Writing Jetson config…"):
            # Write to /tmp as current user (no sudo), then sudo-copy to /opt/psilia/
            rc, _, err = conn.run(f"cat > {tmp}", stdin_data=config_yaml)
            if rc == 0:
                rc, _, err = conn.sudo(f"cp {tmp} /opt/psilia/config.yaml")
                conn.run(f"rm -f {tmp}")

    if rc != 0:
        _fail(f"Failed to write Jetson config: {err.strip()}")
    else:
        _ok("Jetson config written to /opt/psilia/config.yaml")


# ── entry points ──────────────────────────────────────────────────────────────


def run_setup_remote(device: str) -> None:
    """Bootstrap a registered Jetson device over SSH (runs from the laptop)."""
    from psilia_edge.config import read_laptop_config, sync_device_config
    from psilia_edge.init.ssh import SSHError, connect

    config = read_laptop_config()
    devices = config.get("devices", {})
    if device not in devices:
        console.print(f"[red]Device '{device}' not registered.[/red] Run 'psilia pair' first.")
        return

    dev = devices[device]
    host = dev["host"]
    user = dev["user"]
    key = dev.get("key")

    console.print(
        f"  Bootstrapping [bold]{device}[/bold] over SSH ([dim]{user}@{host}[/dim])…"
    )
    try:
        with console.status("  Connecting…"):
            conn = connect(host, user=user, key=key)
    except SSHError as exc:
        console.print(f"[red]SSH connection failed:[/red] {exc}")
        return

    with conn:
        hotspot_ssid, hotspot_password = _step_network(conn, device)
        mount = _step_ssd(conn)
        _step_create_dirs(conn)
        _step_clone(conn)
        _step_copy_ros(conn)
        _step_docker(conn)
        _step_build_image(conn)
        _step_camera(conn)
        autostart = _step_systemd(conn)
        _step_write_jetson_config(
            conn, mount, autostart,
            hotspot_ssid=hotspot_ssid, hotspot_password=hotspot_password, camera=None,
        )
        sync_device_config(device, conn)

    console.print()
    console.rule("[bold]Done")
    console.print(
        f"\n  Device [bold]{device}[/bold] bootstrapped."
        f"\n  Run [bold]psilia start {device}[/bold] to launch the spatial runtime."
    )


def run_setup_local() -> None:
    """Bootstrap this device locally (runs directly on the Jetson)."""
    runner = LocalRunner()

    # Use current hostname as the device name for config/hotspot SSID defaults
    rc, out, _ = runner.run("hostname")
    name = out.strip() or "psilia-jetson"

    console.print(f"  Bootstrapping [bold]{name}[/bold] locally…")

    hotspot_ssid, hotspot_password = _step_network(runner, name)
    mount = _step_ssd(runner)
    _step_create_dirs(runner)
    _step_clone(runner)
    _step_copy_ros(runner)
    _step_docker(runner)
    _step_build_image(runner)
    _step_camera(runner)
    autostart = _step_systemd(runner)
    _step_write_jetson_config(
        runner, mount, autostart,
        hotspot_ssid=hotspot_ssid, hotspot_password=hotspot_password, camera=None,
    )

    console.print()
    console.rule("[bold]Done")
    console.print(
        f"\n  Device [bold]{name}[/bold] bootstrapped."
        f"\n  Run [bold]psilia start[/bold] to launch the spatial runtime."
    )
