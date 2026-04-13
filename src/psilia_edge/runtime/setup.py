"""Psilia Edge — Jetson-side setup wizard.

Entry point (called by scripts/bootstrap.sh):
    psilia setup
"""

from __future__ import annotations

import shutil
from pathlib import Path

from rich.prompt import Prompt

from psilia_edge.utils import (
    run,
    run_streamed,
    run_with_spinner,
    sudo_streamed,
    sudo,
    prompt_sudo_password,
)
from psilia_edge import ui
from psilia_edge.ui import console
from psilia_edge.runtime.config import (
    CONFIG_PATH,
    RUNTIME_DIRS,
    get_repo_dir,
    get_docker_dir,
    get_dockerfile,
    get_ros_dir,
    get_docker_image,
    initial_config,
    initial_runime_config,
    read_config,
    write_config,
    read_runtime_config,
    write_runtime_config,
)

_DEFAULT_HOTSPOT_PASSWORD = "psilia1234"
_PSILIA_REPO_URL = "https://github.com/mirkoklukas/psilia-edge.git"
_PSILIA_REPO_BRANCH = "dev"


def run_runtime_init(
    runtime_home: Path, mkdir: bool = False, quiet: bool = False
) -> None:
    """Wizard: initialize a runtime home directory.

    Steps:
    - Write runtime.home_path to psilia.yaml and write default runtime.yaml
    - Create runtime home directory structure
    - Build Docker image
    - Copy psilia_runtime ROS package into runtime home
    """
    runtime_home = runtime_home.expanduser().resolve()

    _step_init_configs(runtime_home)
    _step_create_dirs(runtime_home, mkdir=mkdir)
    _step_build_image(
        get_docker_image(), get_docker_dir(), get_dockerfile(), quiet=quiet
    )
    _step_copy_ros()

    if not quiet:
        ui.print_tree(read_config(), label=f"'{CONFIG_PATH.name}'")
        ui.done(
            "Runtime initialized.",
            "Next: [bold]psilia runtime start[/bold]",
        )


def run_hotspot_setup() -> None:
    """Wizard: configure a WiFi hotspot (AP mode) so the Jetson is reachable in the field.

    Flow:
    - Detect all AP-capable wifi interfaces via nmcli/iw
    - Check for any active hotspots — offer to replace them
    - Prompt for SSID, password, autostart, and start_on_runtime preferences
    - Create one NM connection profile for the selected interface
    - Write network config into psilia.yaml under 'network.ap'

    TODO: client mode — connect to a phone hotspot instead of acting as AP.
    """
    from psilia_edge.network.hotspot import create_hotspot, find_active_hotspot
    from psilia_edge.network.probe import list_interfaces

    _, name, _ = run("hostname")
    name = name.strip()

    config = read_config()

    ui.title("Network Setup — AP Mode")
    ui.info("Creates a WiFi hotspot on all AP-capable interfaces so phones and laptops")
    ui.info("can connect to the Jetson in the field.")

    # --- detect AP-capable wifi interfaces ---
    with ui.status("Detecting wifi interfaces…"):
        ifaces = list_interfaces()
        ap_ifaces = [i for i in ifaces if i.is_wifi and i.supports_ap]

    if not ap_ifaces:
        ui.warn("No AP-capable wifi interfaces found — skipping network setup.")
        ui.info(
            "[dim]Connect a USB wifi dongle and re-run 'psilia runtime setup --network'.[/dim]"
        )
        return {}

    # --- pick interface ---
    if len(ap_ifaces) == 1:
        iface = ap_ifaces[0]
        itype = "USB dongle" if iface.is_usb_wifi else "built-in"
        ui.ok(f"Using {iface.name}  [dim]({itype})[/dim]")
    else:
        ui.info("AP-capable interfaces:")
        for i, iface in enumerate(ap_ifaces):
            itype = "USB dongle" if iface.is_usb_wifi else "built-in"
            ui.info(f"  [{i + 1}] {iface.name}  [dim]({itype})[/dim]")
        choice = ui.ask_int(
            "  Select interface", choices=list(range(1, len(ap_ifaces) + 1))
        )
        iface = ap_ifaces[choice - 1]
        itype = "USB dongle" if iface.is_usb_wifi else "built-in"

    # --- check for existing hotspot on the selected interface ---
    existing = find_active_hotspot(iface.name)
    if existing:
        ui.ok(f"Existing hotspot on [bold]{iface.name}[/bold]: [bold]{existing}[/bold]")
        if not ui.confirm("Replace it?", default=False):
            ui.info("[dim]Keeping existing hotspot — config unchanged.[/dim]")
            return {}

    # --- prompt for hotspot config ---
    ssid = ui.ask("  Hotspot SSID", default=f"{name}-ap")
    password = ui.ask("  Hotspot password", default=_DEFAULT_HOTSPOT_PASSWORD)
    autostart = ui.confirm("  Auto-connect when interface is available?", default=True)
    start_on_runtime = ui.confirm("  Bring up on 'psilia runtime start'?", default=True)

    ui.info("Summary:")
    ui.detail("  interface", f"[bold]{iface.name}[/bold] ({itype})")
    ui.detail("  ssid", f"[bold]{ssid}[/bold]")
    ui.detail("  password", f"[bold]{password}[/bold]")
    ui.detail("  ip", "[bold]10.42.0.1[/bold] (fixed, Jetson side)")
    ui.detail("  autostart", f"[bold]{autostart}[/bold]")
    ui.detail("  start_on_runtime", f"[bold]{start_on_runtime}[/bold]")

    # --- prompt for sudo password before spinner (prompts inside ui.status() are hidden) ---
    sudo_password = prompt_sudo_password()

    def _runner(cmd):
        return sudo(cmd, password=sudo_password)

    # --- create NM profile for the selected interface ---
    con_name = f"{ssid}-{iface.name}"
    with ui.status(f"  Creating hotspot on {iface.name}…"):
        ok_result, err = create_hotspot(
            ifname=iface.name,
            password=password,
            ssid=ssid,
            con_name=con_name,
            autoconnect=autostart,
            sudo_runner=_runner,
        )
    if ok_result:
        ui.ok(f"  Hotspot '{ssid}' is up on {iface.name}")
    else:
        ui.fail(f"  Failed on {iface.name}: {err}")
        ui.info("[dim]  Configure manually with nmcli.[/dim]")

    itype_key = "usb-dongle" if iface.is_usb_wifi else "built-in"

    # --- write config (replace legacy 'hotspot' key with 'network') ---
    config.pop("hotspot", None)
    config["network"] = {
        "mode": "ap",
        "ap": {
            "ssid": ssid,
            "password": password,
            "interfaces": [
                {
                    "name": iface.name,
                    "type": itype_key,
                    "autostart": autostart,
                    "start_on_runtime": start_on_runtime,
                }
            ],
        },
        # TODO: client mode (connect to phone hotspot instead of acting as AP)
    }

    write_config(config)
    ui.print_tree(config, label=f"'{CONFIG_PATH.name}'")
    ui.done("Hotspot configured.", "Next: [bold]psilia runtime start[/bold]")

    return config


def run_wifi_setup() -> None:
    """Wizard: connect the Jetson to a known home WiFi network via nmcli.

    The home network is not for field use — it's a known WiFi the Jetson connects
    to when available (e.g. at home base). The base layer detects if connected and
    indicates it in the Web UI.

    Flow:
    - Detect wifi interfaces not currently in AP mode
    - If multiple, let the user pick one
    - If existing NM wifi profiles exist, offer to activate one
    - Otherwise scan for visible networks and connect to a new one
    - Prompt for autoconnect and priority
    """
    from psilia_edge.network.hotspot import find_active_hotspot
    from psilia_edge.network.probe import list_interfaces
    from psilia_edge.network.wifi import (
        CLIENT_AUTOCONNECT_PRIORITY,
        activate_connection,
        connect_to_network,
        list_wifi_connections,
        scan_networks,
    )

    ui.title("WiFi Setup")
    ui.info("Connect the Jetson to a WiFi network.")

    # --- detect wifi interfaces not in AP mode ---
    with ui.status("Detecting wifi interfaces…"):
        ifaces = list_interfaces()
        client_ifaces = [
            i for i in ifaces if i.is_wifi and not find_active_hotspot(i.name)
        ]

    if not client_ifaces:
        ui.warn("No available wifi interfaces (all may be in AP mode).")
        return

    # --- pick interface ---
    if len(client_ifaces) == 1:
        iface = client_ifaces[0]
        itype = "USB dongle" if iface.is_usb_wifi else "built-in"
        ui.ok(f"Using {iface.name}  [dim]({itype})[/dim]")
    else:
        ui.info("Available wifi interfaces:")
        for i, iface in enumerate(client_ifaces):
            itype = "USB dongle" if iface.is_usb_wifi else "built-in"
            ui.info(f"  [{i + 1}] {iface.name}  [dim]({itype})[/dim]")
        choice = ui.ask_int(
            "  Select interface", choices=list(range(1, len(client_ifaces) + 1))
        )
        iface = client_ifaces[choice - 1]
        itype = "USB dongle" if iface.is_usb_wifi else "built-in"

    # --- check existing NM wifi profiles ---
    with ui.status("Checking existing WiFi connections…"):
        existing = list_wifi_connections()

    if existing:
        ui.info("Saved WiFi connections:")
        for i, conn in enumerate(existing):
            status_str = "[green]active[/green]" if conn.active else "[dim]saved[/dim]"
            ui.info(f"  [{i + 1}] {conn.name}  {status_str}")

        if ui.confirm("  Activate a saved connection?", default=True):
            choice = ui.ask_int(
                "  Select connection", choices=list(range(1, len(existing) + 1))
            )
            conn = existing[choice - 1]
            autoconnect = ui.confirm(
                "Auto-connect when interface is available?", default=True
            )
            priority = ui.ask("Priority", default=str(CLIENT_AUTOCONNECT_PRIORITY))
            try:
                priority = int(priority)
            except ValueError:
                priority = CLIENT_AUTOCONNECT_PRIORITY

            with ui.status(f"Activating '{conn.name}'…"):
                ok_result = activate_connection(
                    conn.name,
                    ifname=iface.name,
                    autoconnect=autoconnect,
                    priority=priority,
                )
            if ok_result:
                ui.ok(f"Connected via '{conn.name}'")
            else:
                ui.fail(f"Failed to activate '{conn.name}'")
            return

    # --- scan and connect to a new network ---
    with ui.status("Scanning for networks…"):
        networks = scan_networks(ifname=iface.name)

    if not networks:
        ui.warn("No networks found.")
        ssid = ui.ask("  Enter SSID manually")
    else:
        ui.info("Visible networks:")
        for i, net in enumerate(networks):
            ui.info(
                f"  [{i + 1}] {net.ssid}  [dim]{net.signal}% · {net.security}[/dim]"
            )
        ui.info(f"  [{len(networks) + 1}] Enter SSID manually")

        choice = ui.ask_int("Select network", choices=list(range(1, len(networks) + 2)))
        ssid = networks[choice - 1].ssid if choice <= len(networks) else ui.ask("SSID")

    already_connected = iface.connection == ssid
    if not already_connected:
        password = ui.ask("Password")
    autoconnect = ui.confirm("Auto-connect when interface is available?", default=True)
    priority = ui.ask("Priority", default=str(CLIENT_AUTOCONNECT_PRIORITY))
    try:
        priority = int(priority)
    except ValueError:
        priority = CLIENT_AUTOCONNECT_PRIORITY

    if already_connected:
        ui.info(f"Already connected to '{ssid}' — updating settings.")
        with ui.status(f"Updating '{ssid}'…"):
            ok_result = activate_connection(
                ssid,
                ifname=iface.name,
                autoconnect=autoconnect,
                priority=priority,
                bring_up=False,
            )
    else:
        with ui.status(f"Connecting to '{ssid}'…"):
            ok_result = connect_to_network(
                ssid,
                password,
                ifname=iface.name,
                autoconnect=autoconnect,
                priority=priority,
            )
    if ok_result:
        ui.ok(f"Connected to '{ssid}'")
    else:
        ui.fail(f"Failed to connect to '{ssid}'")

    ui.done("WiFi configured.", "Next: [bold]psilia runtime start[/bold]")


def run_update() -> None:
    """Pull latest changes and rebuild the Docker image locally (runs on the Jetson).

    - Copies the updated psilia_runtime ROS package into the runtime home
    - Clears the colcon build cache (build/, install/, log/)
    - Rebuilds the Docker image
    """

    ui.info("Updating ROS workspace ...")
    _step_copy_ros()
    ui.ok("Psilia_runtime ROS package updated")
    # Clear colcon build cache so any setup.py changes are picked up.
    # Dirs are owned by root (created inside Docker), so we clear them by running
    # a temporary container — no sudo needed on the host.
    #
    # Option (cleaner long-term): pass --user uid:gid to docker run so build
    # artifacts are owned by the calling user and can be deleted directly. Requires
    # setting HOME=/tmp inside the container since the UID has no /etc/passwd entry.
    ros_dir = get_ros_dir()
    sudo_streamed(f"rm -rf {ros_dir}/build {ros_dir}/install {ros_dir}/log")
    ui.ok("Colcon build cache cleared")
    ui.ok("ROS package updated")
    ui.info("Re-Building Docker image…")
    with ui.status("This may take a while…"):
        _step_build_image(get_docker_image(), get_docker_dir(), get_dockerfile())
        ui.ok("Docker image re-built")

    ui.done("Runtime updated.", "Next: [bold]psilia runtime start[/bold]")


def _step_init_configs(runtime_home: Path) -> None:
    # Start from initial defaults, then merge existing config on top.
    # This backfills any new keys added to the initial config
    # while preserving existing user values.
    config = initial_config()
    config.update(read_config(missing_ok=True))
    config.update({"runtime": {"home_path": str(runtime_home)}})
    write_config(config)

    runtime_config = initial_runime_config()
    runtime_config.update(read_runtime_config(missing_ok=True))
    write_runtime_config(runtime_config)
    ui.ok(f"Config written — runtime home: {runtime_home}")


def _step_create_dirs(runtime_home: Path, mkdir: bool = False) -> None:
    if not runtime_home.exists():
        if not mkdir:
            raise RuntimeError(
                f"Runtime home '{runtime_home}' does not exist. Use --mkdir to create it."
            )
        runtime_home.mkdir(parents=True, exist_ok=True)
    with ui.status("Creating directories…"):
        for d in RUNTIME_DIRS:
            (runtime_home / d).mkdir(parents=True, exist_ok=True)
    ui.ok("Directories ready")


def _step_copy_ros() -> None:
    src = get_repo_dir() / "ros/psilia_runtime"
    dst = get_ros_dir() / "src/psilia_runtime"
    if not src.exists():
        raise RuntimeError(f"psilia_runtime not found at {src} — is the repo cloned?")
    with ui.status("Copying ROS package…"):
        shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
    ui.ok("ROS package copied")


# TODO: we might want to copy the dockerfile to the ros directory so users can modify it.
def _step_build_image(
    image_name: str, docker_dir: Path, dockerfile: Path, quiet: bool = False
) -> None:
    cmd = f"docker build --network=host -f {dockerfile} -t {image_name} {docker_dir}"
    if quiet:
        rc = run_with_spinner(cmd, f"Building Docker image ({dockerfile.name})…")
    else:
        ui.info(f"Building Docker image ({dockerfile.name})…")
        rc = run_streamed(cmd)
    if rc != 0:
        raise RuntimeError(f"Docker build failed with code {rc}")
    ui.ok(f"Docker image built: {image_name}")


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Steps and Helper
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
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


def _step_pull() -> bool:
    """git pull + pip install -e. Returns True on success."""
    repo_dir = get_repo_dir()

    ui.title("Step 1 — Pull Latest")
    with ui.status("Pulling latest changes…"):
        rc, out, err = run(f"git -C {repo_dir} pull")
    if rc != 0:
        ui.fail(f"git pull failed: {err.strip()}")
        return False
    ui.ok(out.strip() or "Already up to date.")

    # with ui.status("Updating package…"):
    #     rc, _, err = run(f"pip install -e {repo_dir}")
    # if rc != 0:
    #     ui.fail(f"pip install failed: {err.strip()}")
    #     return False
    ui.ok("psilia-edge package updated")
    return True


# def _step_docker() -> None:
#     ui.title("Install Docker")
#     with ui.status("Checking Docker…"):
#         rc, ver, _ = run("docker --version")
#     if rc == 0:
#         ui.ok(f"Docker already installed ({ver.strip()})")
#         return

#     ui.info("Docker not found — installing…")
#     with ui.status("Downloading Docker install script…"):
#         rc, _, err = run("curl -fsSL https://get.docker.com -o /tmp/_get-docker.sh")
#     if rc != 0:
#         ui.fail(f"Failed to download Docker install script: {err.strip()}")
#         return
#     with ui.status("Installing Docker (this may take a while)…"):
#         rc, _, err = sudo("sh /tmp/_get-docker.sh")
#         run("rm -f /tmp/_get-docker.sh")
#     if rc != 0:
#         ui.fail(f"Docker install failed: {err.strip()}")
#         return

#     user = getpass.getuser()
#     ui.info("[dim]sudo needed to add user to docker group[/dim]")
#     sudo(f"usermod -aG docker {user}")
#     _, ver, _ = run("docker --version")
#     ui.ok(f"Docker installed ({ver.strip()})")
#     ui.ok(f"User '{user}' added to docker group")
#     return {}


# def _step_network(name: str) -> dict:


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
    autostart = ui.confirm("  Enable autostart on boot?", default=False)
    if autostart:
        ui.stub("systemctl enable psilia")
        ui.ok("Autostart enabled — runtime will start on next boot")
    else:
        ui.info("[dim]Autostart disabled — start manually with:[/dim] psilia start")
    return {"runtime": {"autostart": autostart}}


def _step_write_config(device_config: dict) -> None:
    ui.title("Device Config")
    with ui.status("Writing config…"):
        write_config(dict(**device_config))
    ui.ok(f"Config written to {CONFIG_PATH}")


# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#
#   Appendix: old code from setup.py, kept here for reference
#   during the rewrite. Not used anymore.
#
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# NOTE: unused — handled by bootstrap.sh
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
    base = Prompt.ask("  Install path")
    data_path = f"{base}/data"
    console.print()
    ui.detail("repo", f"[bold]{base}/psilia-edge[/bold]")
    ui.detail("ros", f"[bold]{base}/ros[/bold]")
    ui.detail("data", f"[bold]{data_path}/recordings[/bold]")
    return {"runtime": {"base_dir": base, "data_dir": data_path}}


# NOTE: unused — handled by bootstrap.sh
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
