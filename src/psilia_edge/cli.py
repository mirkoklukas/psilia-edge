# Naming convention:
#   function   — CLI command (registered with @app.command)
#   _function  — helper (returns data, wraps logic, not a command itself)
#
# When calling into runtime/cli.py:
#   no leading underscore → acts as a command (owns output, side effects)
#   leading underscore    → helper (returns a value or renderable we use here)

from pathlib import Path
from typing import Annotated, Optional

import typer

from psilia_edge import ui
from psilia_edge.runtime.cli import app as runtime_app

app = typer.Typer(help="Psilia Edge — spatial perception runtime for edge devices")

app.add_typer(
    runtime_app,
    name="runtime",
    help="Commands to operate the runtime on Jetson devices",
)

# ── sensor sub-app ───────────────────────────────────────────��───────────────
sensor_app = typer.Typer(help="Manage sensors and calibrations.")
app.add_typer(sensor_app, name="sensor")


@sensor_app.command("add")
def sensor_add(
    calibration: Annotated[
        Path,
        typer.Option(
            "--calibration",
            "-c",
            help="Path to the calibration file.",
        ),
    ] = None,
    label: Annotated[
        str,
        typer.Option("--label", "-l", help="Human-friendly sensor name."),
    ] = None,
    key: Annotated[
        str,
        typer.Option(
            "--key",
            "-k",
            help="Sensor key (UID or label). Non-interactive when provided.",
        ),
    ] = None,
    manufacturer: Annotated[
        str,
        typer.Option("--manufacturer", help="Manufacturer name."),
    ] = None,
    product: Annotated[
        str,
        typer.Option("--product", help="Product name."),
    ] = None,
) -> None:
    """Register a sensor and associate a calibration file."""
    from psilia_edge.runtime.sensor import (
        list_sensors,
        register_sensor,
    )

    # -- Non-interactive mode (--key provided) --
    if key is not None:
        if calibration is None:
            ui.fail("--calibration is required when using --key.")
            raise typer.Exit(1)
        calibration = calibration.expanduser().resolve()
        if not calibration.is_file():
            ui.fail(f"File not found: {calibration}")
            raise typer.Exit(1)

        if label is None:
            label = key

        uid = key if key != label else None
        entry: dict = {"type": "camera", "uid": uid}
        if manufacturer:
            entry["manufacturer"] = manufacturer
        if product:
            entry["product"] = product
        if label != key:
            entry["label"] = label

        register_sensor(key, entry, calibration)
        ui.ok(f"Sensor registered: [bold]{label}[/bold]")
        if key != label:
            ui.detail("uid", key)
        ui.detail("calibration", calibration.name)
        return

    # -- Interactive mode --
    import sys
    from psilia_edge.runtime.hotplug import scan_cameras
    from psilia_edge.runtime.sensor import build_sensor_id, extract_stereo_resolutions

    ui.header(["Sensor", "Add"])

    # -- detect cameras --
    if sys.platform == "linux":
        with ui.status("Scanning for cameras…"):
            groups = scan_cameras()
    else:
        groups = scan_cameras()

    # Flatten groups into a list of physical devices (one per group).
    devices = []
    for group in groups:
        cam = group[0]
        sensor_id = build_sensor_id(cam)
        product_name = cam.get("product", cam.get("name", "Unknown"))
        devices.append(
            {
                "id": sensor_id,
                "product": product_name,
                "manufacturer": cam.get("manufacturer", ""),
                "group": group,
            }
        )

    selected = None
    if devices:
        ui.info("Detected cameras:")
        for i, dev in enumerate(devices):
            ui.info(f"  [{i + 1}] {dev['product']}  [dim]({dev['id']})[/dim]")
        ui.info(f"  [{len(devices) + 1}] No camera (register by label only)")
        choice = ui.ask_int("Select", choices=list(range(1, len(devices) + 2)))
        if choice <= len(devices):
            selected = devices[choice - 1]
    else:
        ui.info("No cameras detected — registering by label only.")

    # -- resolve calibration file --
    if calibration is None:
        cal_str = ui.ask("Calibration file")
        calibration = Path(cal_str)

    calibration = calibration.expanduser().resolve()
    if not calibration.is_file():
        ui.fail(f"File not found: {calibration}")
        raise typer.Exit(1)

    # -- resolve label --
    if label is None:
        default_label = selected["product"] if selected else ""
        label = ui.ask("Label", default=default_label)

    if not label:
        ui.fail("A label is required.")
        raise typer.Exit(1)

    # Check uniqueness.
    existing = list_sensors()
    if label in existing:
        ui.fail(f"A sensor with key '{label}' already exists.")
        raise typer.Exit(1)
    if selected:
        sensor_id = selected["id"]
        if sensor_id in existing:
            ui.fail(f"A sensor with key '{sensor_id}' already exists.")
            raise typer.Exit(1)

    # -- build entry and register --
    if selected:
        _key = selected["id"]
        _entry: dict = {
            "type": "camera",
            "uid": selected["id"],
            "manufacturer": selected["manufacturer"],
            "product": selected["product"],
            "label": label,
        }
        resolutions = extract_stereo_resolutions(selected["group"])
        if resolutions:
            _entry["resolutions"] = resolutions
    else:
        _key = label
        _entry = {
            "type": "camera",
            "uid": None,
            "label": label,
        }

    register_sensor(_key, _entry, calibration)

    ui.ok(f"Sensor registered: [bold]{label}[/bold]")
    if _key != label:
        ui.detail("label", label)
        ui.detail("uid", _key)
    ui.detail("calibration", calibration.name)


@sensor_app.command("list")
def sensor_list() -> None:
    """Show registered sensors."""
    from psilia_edge.runtime.sensor import (
        list_sensors,
        get_available_calibrations,
        get_calibration_resolution,
    )

    sensors = list_sensors()
    if not sensors:
        ui.info(
            "[dim]No sensors registered. Run 'psilia sensor add' to register one.[/dim]"
        )
        return

    for key, entry in sensors.items():
        label = entry.get("label", key)
        uid = entry.get("uid")

        cal_files = get_available_calibrations(label, uid)
        cal_resolutions = []
        for f in cal_files:
            res = get_calibration_resolution(f)
            if res:
                cal_resolutions.append(list(res))
        if cal_resolutions:
            entry["calibrated_resolutions"] = cal_resolutions

    ui.print_tree(sensors, label="Sensors", collapse_flat_lists=True)


@sensor_app.command("remove")
def sensor_remove(
    key: str = typer.Argument(help="Sensor key (label or UID) to remove."),
    delete_calibration: bool = typer.Option(
        False,
        "--delete-calibration",
        help="Also delete the calibration file.",
    ),
) -> None:
    """Unregister a sensor."""
    from psilia_edge.runtime.sensor import remove_sensor

    try:
        remove_sensor(key, delete_calibration=delete_calibration)
    except KeyError as e:
        ui.fail(str(e))
        raise typer.Exit(1)
    ui.ok(f"Sensor removed: {key}")


@sensor_app.command("push")
def sensor_push(
    device: str = typer.Argument(help="Registered device name."),
    key: Optional[str] = typer.Option(
        None, "--key", "-k", help="Push only this sensor key."
    ),
) -> None:
    """Push sensor entries and calibration files to a remote device."""
    from psilia_edge.runtime.sensor import push_sensors

    ui.header(["Sensor", "Push"])

    keys = [key] if key else None
    try:
        pushed = push_sensors(device, keys=keys)
    except KeyError as e:
        ui.fail(str(e))
        raise typer.Exit(1)
    except RuntimeError as e:
        ui.fail(str(e))
        raise typer.Exit(1)

    for k in pushed:
        ui.ok(f"{k}")
    ui.ok(f"Pushed {len(pushed)} sensor(s) to {device}")


@sensor_app.command("scan")
def sensor_scan() -> None:
    """Scan for connected cameras and USB devices."""
    from psilia_edge.runtime.hotplug import scan_cameras, usb_list_devices

    ui.header(["Sensor", "Scan"], "Scanning for connected cameras…")
    groups = scan_cameras()
    if not groups:
        ui.warn("No cameras found.")
    else:
        ui.print_tree(groups, label="cameras")

    ui.print_tree(usb_list_devices(), label="USB devices")


# ── data sub-app ──────────────────────────────────────────────────────────────
data_app = typer.Typer(help="Data operations (pull, sync)")
app.add_typer(data_app, name="data")


@data_app.command()
def pull(
    device: str = typer.Argument(
        None,
        help="Registered device name. Pulls from all registered devices if not specified.",
    ),
    to: Path = typer.Option(
        None,
        "--to",
        help="Local destination directory. Overrides data.pull_to in psilia.yaml (not saved).",
    ),
) -> None:
    """Pull recorded MCAP data from a device to the local machine."""
    from psilia_edge.device_manager.config import write_pull_to
    from psilia_edge.device_manager.data import (
        build_rsync_cmd,
        get_active_recording,
        get_pull_to,
        get_remote_data_dir,
    )
    from psilia_edge.runtime.config import ConfigurationError, read_config
    from psilia_edge.utils import run_streamed

    # Resolve pull_to: flag > config > prompt
    if to is not None:
        pull_to = Path(to).expanduser().resolve()
    else:
        try:
            pull_to = get_pull_to()
        except ConfigurationError:
            raw = ui.ask("Local directory to pull data into")
            pull_to = Path(raw).expanduser().resolve()
            write_pull_to(pull_to)

    devices = (
        [device] if device else list(read_config().get("registered_devices", {}).keys())
    )

    if not devices:
        ui.warn("No registered devices. Run 'psilia runtime pair' to add one.")
        raise typer.Exit(1)

    for dev in devices:
        ui.header(["Data", "Pull"], dev)

        remote_data_dir = get_remote_data_dir(dev)

        ui.info(f"Copying Data:\n{dev}:{remote_data_dir} → {pull_to}")

        active_recording = get_active_recording(dev)
        if active_recording:
            ui.detail("excluding active recording", active_recording)

        pull_to.mkdir(parents=True, exist_ok=True)
        cmd = build_rsync_cmd(
            dev,
            remote_data_dir,
            pull_to,
            exclude=[active_recording] if active_recording else None,
        )
        rc = run_streamed(cmd)
        if rc != 0:
            ui.fail(f"pull from {dev} failed (exit {rc})")
        else:
            ui.ok("done")


# ── print helper commands ─────────────────────────────────────────────────────
def _print_section(title: str, content: str) -> None:
    ui.title(str(title))
    ui.print(content)


def _print_file(fname: str | Path) -> None:
    fname = Path(fname)
    if fname.exists():
        _print_section(fname, fname.read_text())
    else:
        _print_section(fname, f"[dim]{str(fname)} not found[/dim]")


@app.command(hidden=True)
def debug():
    """Show internal state, adapts to role (runtime host vs device manager)."""
    from psilia_edge.runtime.core import is_runtime_host

    if is_runtime_host():
        _debug_runtime_host()
    else:
        _debug_device_manager()


def _debug_runtime_host() -> None:
    from psilia_edge.runtime.config import CONFIG_PATH

    _print_file(CONFIG_PATH)


def _debug_device_manager() -> None:
    from psilia_edge.runtime.config import CONFIG_PATH
    from psilia_edge.device_manager.config import (
        _SSH_CONFIG_PATH,
        _SSH_SECTION_END,
        _SSH_SECTION_START,
    )

    _print_file(CONFIG_PATH)

    if _SSH_CONFIG_PATH.exists():
        text = _SSH_CONFIG_PATH.read_text()
        if _SSH_SECTION_START in text:
            start = text.index(_SSH_SECTION_START)
            end = text.index(_SSH_SECTION_END) + len(_SSH_SECTION_END)
            _print_section(_SSH_CONFIG_PATH, text[start:end])
        else:
            _print_section(_SSH_CONFIG_PATH, "[dim]No psilia section found[/dim]")
    else:
        _print_section(_SSH_CONFIG_PATH, f"[dim]{_SSH_CONFIG_PATH} not found[/dim]")
