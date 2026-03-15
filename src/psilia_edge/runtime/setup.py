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
    get_ros_dir,
    get_docker_image,
    read_config,
    write_config,
    read_runtime_config,
    write_runtime_config,
    get_runtime_config_path,
)

_DEFAULT_HOTSPOT_PASSWORD = "psilia1234"
_PSILIA_REPO_URL = "https://github.com/mirkoklukas/psilia-edge.git"
_PSILIA_REPO_BRANCH = "dev"


# TODO: What is a cool pattern, for running steps, printing to ui what has been done, and returning a config.
#   and keeping the cli command and the work separated. Like which function should have ui calls, and
#   which should just return dicts that the cli command can print?
def runtime_home_init(runtime_home: Path, mkdir: bool = False) -> None:
    """Initialize the runtime home directory.

    - Creates psilia.yaml if it doesn't exist (with runtime.home_path set to runtime_home)
    - Creates the runtime home directory structure
    - Copies the psilia_runtime ROS package into the runtime home
    - Builds the Docker image
    - Writes runtime home path into psilia.yaml
    - Writes a default runtime.yaml
    """
    # TODO: Requires docker for instance. Should have a check whether all
    #   dependencies are met before we run through init?

    if not runtime_home.exists() and not mkdir:
        raise RuntimeError(
            f"Runtime home directory '{runtime_home}' does not exist."
            f"Run with --create (-c) to create it."
        )

    runtime_home = runtime_home.expanduser().resolve()

    config = read_config(missing_ok=True)
    config.update({"runtime": {"home_path": str(runtime_home)}})
    write_config(config)

    runtime_config = read_runtime_config(missing_ok=True)
    write_runtime_config(runtime_config)

    ui.status("Creating directories")
    _step_create_dirs(runtime_home)
    ui.ok("Directories ready")

    ui.info("Building Docker image…")
    with ui.status("This may take a while…"):
        _step_build_image(get_docker_image(), get_docker_dir())
        ui.ok("Docker image built")

    # Depends on runtime home being set in config,
    # and directories being created since it copies into the ros dir.
    _step_copy_ros()
    ui.ok("ROS package copied")

    ui.print_tree(config, label=f"'{CONFIG_PATH.name}'")
    ui.print_tree(runtime_config, label=f"'{get_runtime_config_path().name}'")

    return config, runtime_config


def run_setup(runtime_home: Path, skip_init=False) -> None:
    """Run the full setup wizard locally on the Jetson.

    Reads install paths from ~/.psilia/psilia.yaml, which is written
    by scripts/bootstrap.sh before this wizard is invoked.

    - Creates the runtime home directory
    - Runs runtime_home_init (dirs, ROS package, Docker image, configs)
    - Configures the wifi hotspot
    - Writes the final psilia.yaml
    """

    if not skip_init:
        runtime_home_init(runtime_home, mkdir=True)

    _, name, _ = run("hostname")
    name = name.strip()

    config = read_config()
    config |= _step_network(name)
    # config |= _step_camera()
    # config |= _step_systemd()
    write_config(config)
    ui.print_tree(config, label=f"'{CONFIG_PATH.name}'")

    return config


def runtime_home_update() -> None:
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
        _step_build_image(get_docker_image(), get_docker_dir())
        ui.ok("Docker image re-built")


def _step_create_dirs(runtime_home: Path) -> None:
    for d in RUNTIME_DIRS:
        dir_path = runtime_home / d
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
    return {}


def _step_copy_ros() -> None:
    src = get_repo_dir() / "ros/psilia_runtime"
    dst = get_ros_dir() / "src/psilia_runtime"

    if not src.exists():
        raise RuntimeError(f"psilia_runtime not found at {src} — is the repo cloned?")

    shutil.copytree(str(src), str(dst), dirs_exist_ok=True)

    return {}


# TODO: we might want to copy the docker file to the ros directory.
#   And use that to build the image, so that users can modify it if needed.
#   But for now we can just point to the one in the repo.
def _step_build_image(image_name, docker_dir) -> None:
    # TODO: path to docker file should be a configurable? not hardcoded?

    rc = run_streamed(f"docker build --network=host -t {image_name} {docker_dir}")
    if rc != 0:
        raise RuntimeError(f"Docker build failed with code {rc}")

    return {"runtime": {"image": image_name}}


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


def _step_network(name: str) -> dict:
    """Configure a wifi hotspot on the Jetson so it is reachable in the field.

    Flow:
    - Detect all wifi interfaces via nmcli
    - Check if an active hotspot already exists — offer to replace it
    - Pick the best interface: USB dongle > built-in wifi, AP-capable preferred
    - Prompt for SSID and password
    - Create and bring up the hotspot via nmcli (requires sudo)
    - Write ssid and password into psilia.yaml under 'hotspot'
    """
    from psilia_edge.network.hotspot import create_hotspot, find_active_hotspot
    from psilia_edge.network.probe import list_interfaces

    ui.title("Network Setup")
    ui.info("Configures a wifi hotspot on the Jetson (USB dongle preferred)")
    ui.info("[dim]So you can reach it in the field without a router.[/dim]")

    # --- detect wifi interfaces and any existing hotspot ---
    with ui.status("Detecting wifi interfaces and existing hotspot…"):
        ifaces = list_interfaces()
        wifi_ifaces = [i for i in ifaces if i.is_wifi]
        existing_hotspot = None
        for wi in wifi_ifaces:
            existing_hotspot = find_active_hotspot(wi.name)
            if existing_hotspot:
                break

    # --- pick best interface: USB dongle preferred, AP-capable preferred ---
    usb = [i for i in wifi_ifaces if i.is_usb_wifi]
    candidates = usb or wifi_ifaces
    ap_capable = [i for i in candidates if i.supports_ap] or candidates
    iface = ap_capable[0] if ap_capable else None

    # --- handle existing hotspot ---
    if existing_hotspot:
        ui.ok(f"Existing hotspot found: [bold]{existing_hotspot}[/bold]")
        if not ui.confirm("Replace it?", default=False):
            ui.info("[dim]Keeping existing hotspot — config unchanged.[/dim]")
            return {}

    # --- bail if no usable interface found ---
    if iface is None:
        ui.warn("No wifi interface found — skipping network setup.")
        ui.info(
            "[dim]Connect a USB wifi dongle and re-run 'psilia runtime setup'.[/dim]"
        )
        return {}
    elif iface.is_usb_wifi:
        ui.ok(f"USB wifi dongle detected: [bold]{iface.name}[/bold]")
    else:
        ui.warn(f"No USB dongle — using built-in wifi: [bold]{iface.name}[/bold]")
        ui.info(
            "[dim]Note: built-in wifi can't act as hotspot and client simultaneously on all hardware.[/dim]"
        )

    # --- prompt for hotspot config ---
    ssid = ui.ask("  Hotspot SSID", default=f"{name}-ap")
    password = ui.ask("  Hotspot password", default=_DEFAULT_HOTSPOT_PASSWORD)
    ui.detail("interface", f"[bold]{iface.name}[/bold]")
    ui.detail("ssid", f"[bold]{ssid}[/bold]")
    ui.detail("password", f"[bold]{password}[/bold]")
    ui.detail("ip", "[bold]10.42.0.1[/bold] (fixed, Jetson side)")

    # --- prompt for sudo password before spinner (prompts inside ui.status() are hidden) ---
    # TODO: ui.status() (Rich Live spinner) blocks interactive prompts — any code path
    #   that may need user input must prompt *before* entering the spinner context.
    sudo_password = prompt_sudo_password()

    def _runner(cmd):
        return sudo(cmd, password=sudo_password)

    # --- create and bring up the hotspot ---
    with ui.status("  Creating hotspot…"):
        ok_result, err = create_hotspot(
            ifname=iface.name,
            password=password,
            ssid=ssid,
            con_name=f"{ssid}-Hotspot",
            sudo_runner=_runner,
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
