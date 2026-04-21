"""Psilia Runtime TUI — Textual-based terminal app.

TODO: Use roslibpy (Python rosbridge client) to subscribe to ROS topics
directly via WebSocket (ws://localhost:9090), same protocol the web UI uses.
Would enable live heartbeat, recording control, and image preview without
file polling. Use file-based approach as fallback when rosbridge is down.
"""

from __future__ import annotations

import json
import socket
import time

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.reactive import reactive
from textual.theme import Theme
from textual.widgets import Footer, Header, Log, Static, TabbedContent, TabPane

PSILIA_THEME = Theme(
    name="psilia",
    primary="#4ecca3",
    secondary="#009dff",
    accent="#9c27b0",
    foreground="#e0e0e0",
    background="#1a1a2e",
    success="#4ecca3",
    warning="#f0c040",
    error="#e05555",
    surface="#16213e",
    panel="#16213e",
    dark=True,
    variables={
        "footer-key-foreground": "#4ecca3",
        "footer-description-foreground": "#3392db",
    },
)


class BaseLayerPanel(Static):
    """Base layer status: daemon, container, URL."""

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh_status)

    def refresh_status(self) -> None:
        self.update(self._build())

    def _build(self) -> str:
        from psilia_edge.runtime.daemon import is_running as is_daemon_running
        from psilia_edge.runtime.docker import check_container_status

        lines = []

        daemon_running = is_daemon_running()
        daemon = "[green]running[/]" if daemon_running else "[red]stopped[/]"
        if daemon_running:
            from psilia_edge.runtime.config import get_api_port

            port = get_api_port()
            hostname = socket.gethostname().split(".")[0]
            daemon += f"  [dim]http://{hostname}.local:{port}[/]"
        lines.append(f"daemon:      {daemon}")

        container = check_container_status()
        if container == "running":
            container_text = "[green]running[/]"
        elif container == "exited":
            container_text = "[red]exited[/]"
        else:
            container_text = "[dim]absent[/]"
        lines.append(f"container:   {container_text}")

        return "\n".join(lines)


class SpatialLayerPanel(Static):
    """Spatial layer status: heartbeat, Hz table, preflight checks."""

    checks: reactive[dict] = reactive({})
    force_mode: reactive[bool] = reactive(True)

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh_status)

    def refresh_status(self) -> None:
        self.update(self._build())

    def _build(self) -> str:
        from psilia_edge.runtime.config import RUN_DIR

        lines = []

        # ── Spatial status ────────────────────────────────────
        from psilia_edge.runtime.docker import (
            is_container_running,
            is_ros_launch_running,
        )

        if not is_container_running():
            spatial = "[dim]not running[/]"
        elif not is_ros_launch_running():
            spatial = "[dim]stopped[/]"
        else:
            hb_file = RUN_DIR / "heartbeat.json"
            hb = _read_json(hb_file)
            if hb:
                try:
                    age = time.time() - hb_file.stat().st_mtime
                except OSError:
                    age = 999
                if age < 5:
                    spatial = f"[green]running[/]  [dim]heartbeat {age:.1f}s ago[/]"
                else:
                    spatial = f"[yellow]stale[/]  [dim]heartbeat {age:.0f}s ago[/]"
            else:
                spatial = "[yellow]waiting for heartbeat[/]"
        lines.append(f"status:  {spatial}")

        # ── Force mode ───────────────────────────────────────
        force_label = "[green]on[/]" if self.force_mode else "[dim]off[/]"
        lines.append(f"force:   {force_label}")

        # ── Preflight checks ────────────────────────────────
        if self.checks:
            lines.append("")
            lines.append("[bold]preflight checks[/]")
            for key, info in self.checks.items():
                ok = info["ok"]
                detail = info.get("detail", "")
                symbol = "[green]✓[/]" if ok else "[red]✗[/]"
                name = key if ok else f"[bold]{key}[/]"
                detail_text = f"  [dim]{detail}[/]" if detail else ""
                lines.append(f"  {symbol} {name}{detail_text}")

        # ── Hz table ─────────────────────────────────────────
        hz_file = RUN_DIR / "hz.json"
        hz = _read_json(hz_file)
        if hz:
            try:
                hz_age = time.time() - hz_file.stat().st_mtime
            except OSError:
                hz_age = 999
            hz_live = hz_age < 3
            lines.append("")
            lines.append("[bold]topics[/]")
            for topic, info in hz.items():
                rate_val = info.get("hz", 0)
                if hz_live and rate_val > 0:
                    rate = f"[cyan]{rate_val:.1f} Hz[/]"
                else:
                    rate = "[dim]—[/]"
                lines.append(f"  {topic:<40s} {rate}")

        return "\n".join(lines)


class LogPanel(Log):
    """Tails the ROS log file."""

    def on_mount(self) -> None:
        self._last_size = 0
        self.set_interval(1.0, self.poll_log)

    def poll_log(self) -> None:
        from psilia_edge.runtime.docker import get_ros_log_path

        log_path = get_ros_log_path()
        try:
            size = log_path.stat().st_size
        except OSError:
            return

        if size > self._last_size:
            with open(log_path, errors="replace") as f:
                f.seek(self._last_size)
                new_text = f.read()
            if new_text:
                self.write(new_text)
            self._last_size = size
        elif size < self._last_size:
            self.clear()
            self._last_size = 0


class PsiliaApp(App):
    """Psilia Runtime TUI."""

    TITLE = "Psilia Edge"
    CSS = """
    #base-panel {
        height: auto;
        border: solid $surface;
        border-title-color: $secondary;
        padding: 1;
    }
    #spatial-panel {
        height: auto;
        border: solid $surface;
        border-title-color: $secondary;
        padding: 1;
    }
    #log-panel {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("s", "start_spatial", "Start"),
        Binding("x", "stop_spatial", "Stop"),
        Binding("f", "toggle_force", "Force"),
        Binding("r", "refresh_checks", "Checks"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent("Status", "Logs"):
            with TabPane("Status", id="tab-status"):
                with Vertical():
                    yield BaseLayerPanel(id="base-panel")
                    yield SpatialLayerPanel(id="spatial-panel")
            with TabPane("Logs", id="tab-logs"):
                yield LogPanel(id="log-panel")
        yield Footer()

    def on_mount(self) -> None:
        self.register_theme(PSILIA_THEME)
        self.theme = "psilia"
        self.sub_title = socket.gethostname().split(".")[0]
        self.query_one("#base-panel").border_title = "Base Layer"
        self.query_one("#spatial-panel").border_title = "Spatial Layer"
        self._load_initial_log()
        self.action_refresh_checks()

    def _load_initial_log(self) -> None:
        from psilia_edge.runtime.docker import get_ros_log_path

        log_path = get_ros_log_path()
        try:
            lines = log_path.read_text(errors="replace").splitlines()
            tail = lines[-50:]
            log_panel = self.query_one("#log-panel", LogPanel)
            log_panel.write("\n".join(tail))
            log_panel._last_size = log_path.stat().st_size
        except OSError:
            pass

    def action_start_spatial(self) -> None:
        self.notify("Starting spatial layer...", severity="information")
        self.run_worker(self._start_spatial, thread=True)

    def action_stop_spatial(self) -> None:
        self.notify("Stopping spatial layer...", severity="information")
        self.run_worker(self._stop_spatial, thread=True)

    def action_toggle_force(self) -> None:
        panel = self.query_one("#spatial-panel", SpatialLayerPanel)
        panel.force_mode = not panel.force_mode
        label = "on" if panel.force_mode else "off"
        self.notify(f"Force mode: {label}", severity="information")

    def action_refresh_checks(self) -> None:
        self.run_worker(self._refresh_checks, thread=True)

    async def _start_spatial(self) -> None:
        from psilia_edge.runtime.core import (
            SpatialRequirementsError,
            start_spatial_layer,
        )

        panel = self.query_one("#spatial-panel", SpatialLayerPanel)
        try:
            start_spatial_layer(force=panel.force_mode)
            self.notify("Spatial layer started", severity="information")
        except SpatialRequirementsError as e:
            panel.checks = e.result.to_dict()
            failed = [k for k, v in panel.checks.items() if not v["ok"]]
            self.notify(f"Failed: {', '.join(failed)}", severity="error")
        except Exception as e:
            self.notify(f"Start failed: {e}", severity="error")

    async def _stop_spatial(self) -> None:
        from psilia_edge.runtime.core import stop_spatial_layer

        try:
            stop_spatial_layer()
            self.notify("Spatial layer stopped", severity="information")
        except Exception as e:
            self.notify(f"Stop failed: {e}", severity="error")

    async def _refresh_checks(self) -> None:
        from psilia_edge.runtime.core import check_spatial_requirements

        try:
            ctx = check_spatial_requirements()
            panel = self.query_one("#spatial-panel", SpatialLayerPanel)
            panel.checks = ctx.to_dict()
        except Exception as e:
            self.notify(f"Check error: {e}", severity="error")


def _read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def run() -> None:
    app = PsiliaApp()
    app.run()
