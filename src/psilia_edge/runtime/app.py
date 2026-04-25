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
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.reactive import reactive
from textual.theme import Theme
from textual.widgets import (
    Footer,
    Header,
    Log,
    Static,
    Tab,
    Tabs,
    TabbedContent,
    TabPane,
)

_THEME_FILE = Path(__file__).parent / "_theme.yaml"

_DEFAULT_THEME_COLORS = dict(
    primary="#8c00ff",
    secondary="#8c00ff",
    accent="#ff0000",
    foreground="#3d3d3d",
    background="#ffffff",
    success="#108448",
    warning="#f0c040",
    error="#f53d00",
    surface="#e3e3e3",
    panel="#e3e3e3",
    variables={
        "footer-key-foreground": "#8c00ff",
        "footer-description-foreground": "#684d80",
        "tab-foreground": "#684d80",
        "tab-active-foreground": "#8c00ff",
    },
)


def _load_theme() -> Theme:
    colors = _DEFAULT_THEME_COLORS.copy()
    if _THEME_FILE.exists():
        import yaml

        with open(_THEME_FILE) as f:
            overrides = yaml.safe_load(f) or {}
        colors.update(overrides)
    return Theme(name="psilia", dark=True, **colors)


def _theme_colors() -> dict[str, str]:
    """Return current theme color map for use in Rich markup."""
    theme = _load_theme()
    return {
        "success": theme.success,
        "warning": theme.warning,
        "error": theme.error,
        "primary": theme.primary,
        "secondary": theme.secondary,
        "accent": theme.accent,
        "foreground": theme.foreground,
        "background": theme.background,
        "surface": theme.surface,
        "panel": theme.panel,
    }


def _get_psilia_config_path():
    from psilia_edge.runtime.config import CONFIG_PATH

    return CONFIG_PATH


def _get_runtime_config_path():
    from psilia_edge.runtime.config import get_runtime_config_path

    return get_runtime_config_path(missing_ok=True)


class BaseLayerPanel(Static):
    """Base layer status: daemon, container, URL."""

    can_focus = True

    BINDINGS = [
        Binding("s", "app.start_base", "Start"),
        Binding("x", "app.stop_base", "Stop"),
    ]

    def on_mount(self) -> None:
        self.refresh_status()

    def refresh_status(self) -> None:
        self.update(self._build())

    def _build(self) -> str:
        from psilia_edge.runtime.daemon import is_running as is_daemon_running
        from psilia_edge.runtime.docker import check_container_status

        c = _theme_colors()
        lines = [f"[bold {c['primary']}]Base Layer[/]"]

        daemon_running = is_daemon_running()
        daemon = (
            f"[{c['success']}]running[/]"
            if daemon_running
            else f"[{c['error']}]stopped[/]"
        )
        if daemon_running:
            from psilia_edge.runtime.config import get_api_port

            port = get_api_port()
            hostname = socket.gethostname().split(".")[0]
            daemon += f"  [dim]http://{hostname}.local:{port}[/]"
        lines.append(f"daemon:      {daemon}")

        container = check_container_status()
        if container == "running":
            container_text = f"[{c['success']}]running[/]"
        elif container == "exited":
            container_text = f"[{c['error']}]exited[/]"
        else:
            container_text = "[dim]absent[/]"
        lines.append(f"container:   {container_text}")

        return "\n".join(lines)


class SpatialLayerPanel(Static):
    """Spatial layer status: heartbeat, Hz table, preflight checks."""

    can_focus = True

    BINDINGS = [
        Binding("s", "app.start_spatial", "Start"),
        Binding("x", "app.stop_spatial", "Stop"),
        Binding("f", "app.toggle_force", "Force"),
    ]

    checks: reactive[dict] = reactive({})
    force_mode: reactive[bool] = reactive(True)
    _ros_nodes: list[str] | None = None

    def on_mount(self) -> None:
        self.refresh_status()
        self.set_interval(2.0, self.refresh_status)

    def refresh_status(self) -> None:
        self.update(self._build())

    def refresh_nodes(self) -> None:
        from psilia_edge.runtime.docker import list_ros_nodes

        self._ros_nodes = list_ros_nodes()
        self.update(self._build())

    def _build(self) -> str:
        from psilia_edge.runtime.config import RUN_DIR

        c = _theme_colors()
        lines = [f"[bold {c['primary']}]Spatial Layer[/]"]

        # ── Spatial status ────────────────────────────────────
        from psilia_edge.runtime.core import check_spatial_layer_status

        status = check_spatial_layer_status()
        state = status["state"]
        detail = status.get("detail", "")

        _STATE_STYLE = {
            "stopped": "[dim]stopped[/]",
            "starting": f"[{c['warning']}]starting[/]",
            "running": f"[{c['success']}]running[/]",
            "stale": f"[{c['warning']}]stale[/]",
            "crashed": f"[{c['error']}]crashed[/]",
        }
        spatial = _STATE_STYLE.get(state, f"[dim]{state}[/]")
        if detail:
            spatial += f"  [dim]{detail}[/]"
        lines.append(f"status:  {spatial}")

        # ── Preflight checks ────────────────────────────────
        if self.checks:
            force_label = f"[{c['success']}]on[/]" if self.force_mode else "[dim]off[/]"
            lines.append("")
            lines.append(f"[bold]preflight checks[/]  [dim]force:[/] {force_label}")
            for key, info in self.checks.items():
                ok = info["ok"]
                detail = info.get("detail", "")
                symbol = f"[{c['success']}]✓[/]" if ok else f"[{c['error']}]✗[/]"
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
            lines.append("[bold]diagnostics[/]")
            for topic, info in hz.items():
                rate_val = info.get("hz", 0)
                if hz_live and rate_val > 0:
                    rate = f"[{c['secondary']}]{rate_val:.1f} Hz[/]"
                else:
                    rate = "[dim]—[/]"
                lines.append(f"  {topic:<40s} {rate}")

        # ── Nodes ────────────────────────────────────────────
        if self._ros_nodes is not None:
            lines.append("")
            lines.append("[bold]nodes[/]")
            for node in self._ros_nodes:
                lines.append(f"  [dim]{node}[/]")

        return "\n".join(lines)


class ConfigPanel(VerticalScroll):
    """Displays a YAML config file. Collapses when not focused."""

    can_focus = True
    collapsed: reactive[bool] = reactive(False)

    def __init__(
        self,
        file_label: str,
        file_path_getter,
        collapsed: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._file_label = file_label
        self._file_path_getter = file_path_getter
        self._init_collapsed = collapsed

    def compose(self) -> ComposeResult:
        yield Static("", classes="config-content")

    def on_mount(self) -> None:
        self.collapsed = self._init_collapsed
        self._apply_layout()
        self.refresh_content()

    def on_focus(self) -> None:
        self.collapsed = False
        for panel in self.screen.query(ConfigPanel):
            if panel is not self:
                panel.collapsed = True

    def watch_collapsed(self) -> None:
        self._apply_layout()
        self.refresh_content()

    def _apply_layout(self) -> None:
        self.styles.height = "auto" if self.collapsed else "1fr"

    def refresh_content(self) -> None:
        try:
            self.query_one(".config-content", Static).update(self._build())
        except Exception:
            pass

    def _build(self) -> str:
        arrow = "▶" if self.collapsed else "▼"
        try:
            path = self._file_path_getter()
        except Exception:
            return f"{arrow} [bold]{self._file_label}[/]  [dim](not found)[/]"

        if self.collapsed:
            return f"{arrow} [bold]{self._file_label}[/]  [dim]{path}[/]"

        try:
            content = path.read_text(errors="replace")
            return f"{arrow} [bold]{self._file_label}[/]  [dim]{path}[/]\n\n{content}"
        except Exception:
            return f"{arrow} [bold]{self._file_label}[/]  [dim](not found)[/]"


class LogPanel(Log):
    """Tails log files with cycling support."""

    follow: reactive[bool] = reactive(True)
    _log_index: int = 0

    BINDINGS = [
        Binding("f", "toggle_follow", "Follow"),
        Binding("n", "next_log", "Next"),
        Binding("N", "prev_log", "Prev"),
    ]

    def _log_sources(self) -> list[tuple[str, str]]:
        from psilia_edge.runtime.config import get_log_dir
        from psilia_edge.runtime.daemon import LOG_FILE
        from psilia_edge.runtime.docker import get_ros_log_path

        log_dir = get_log_dir()

        sources = [
            str(get_ros_log_path()),
            str(log_dir / "colcon_build.log"),
        ]

        ros_log_dir = log_dir / "ros_log"
        if ros_log_dir.is_dir():
            subdirs = sorted(
                (d for d in ros_log_dir.iterdir() if d.is_dir()),
                key=lambda d: d.stat().st_mtime,
                reverse=True,
            )
            for d in subdirs:
                launch_log = d / "launch.log"
                if launch_log.exists():
                    sources.append(str(launch_log))
                    break

        sources.append(str(LOG_FILE))

        return sources

    @property
    def _current_path(self) -> str:
        sources = self._log_sources()
        return sources[self._log_index % len(sources)]

    def _switch_log(self) -> None:
        from pathlib import Path

        self.clear()
        self._last_size = 0
        path = Path(self._current_path)
        try:
            lines = path.read_text(errors="replace").splitlines()
            tail = lines[-50:]
            if tail:
                self.write("\n".join(tail))
            self._last_size = path.stat().st_size
        except OSError:
            pass
        self._update_label()

    def action_next_log(self) -> None:
        sources = self._log_sources()
        self._log_index = (self._log_index + 1) % len(sources)
        self._switch_log()

    def action_prev_log(self) -> None:
        sources = self._log_sources()
        self._log_index = (self._log_index - 1) % len(sources)
        self._switch_log()

    def action_toggle_follow(self) -> None:
        self.follow = not self.follow
        label = "follow" if self.follow else "paused"
        self.app.notify(f"Logs: {label}", severity="information")

    def on_mount(self) -> None:
        self._last_size = 0
        self.set_interval(1.0, self.poll_log)
        self._update_label()

    def watch_follow(self) -> None:
        self.auto_scroll = self.follow
        self._update_label()
        if self.follow:
            self.scroll_end(animate=False)

    def _update_label(self) -> None:
        follow_label = "[green]follow[/]" if self.follow else "[yellow]paused[/]"
        try:
            label = self.app.query_one("#log-label", Static)
            label.update(f"[bold]{self._current_path}[/]  {follow_label}")
        except Exception:
            pass

    def poll_log(self) -> None:
        from pathlib import Path

        log_path = Path(self._current_path)
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.register_theme(_load_theme())
        self.theme = "psilia"

    TITLE = "Psilia Edge"
    CSS = """
    Tab {
        color: $tab-foreground;
    }
    Tab:hover {
        color: $foreground;
    }
    Tab.-active {
        color: $tab-active-foreground;
    }
    #base-panel, #spatial-panel {
        height: auto;
        padding: 1;
    }
    #base-panel:focus, #spatial-panel:focus, #log-panel:focus {
        background: $surface;
    }
    #log-label {
        height: 1;
        padding: 0 1;
    }
    #log-panel {
        height: 1fr;
    }
    #config-psilia, #config-runtime {
        padding: 1;
    }
    #config-psilia:focus, #config-runtime:focus {
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("shift+left", "prev_tab", "◀ Tab"),
        Binding("shift+right", "next_tab", "Tab ▶"),
        Binding("r", "refresh", "Refresh"),
        Binding("T", "reload_theme", "Theme"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent("Status", "Logs", "Config"):
            with TabPane("Status", id="tab-status"):
                yield BaseLayerPanel(id="base-panel")
                yield SpatialLayerPanel(id="spatial-panel")
            with TabPane("Logs", id="tab-logs"):
                yield Static("", id="log-label")
                yield LogPanel(id="log-panel")
            with TabPane("Config", id="tab-config"):
                yield ConfigPanel(
                    "psilia.yaml", _get_psilia_config_path, id="config-psilia"
                )
                yield ConfigPanel(
                    "runtime.yaml",
                    _get_runtime_config_path,
                    collapsed=True,
                    id="config-runtime",
                )
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = socket.gethostname().split(".")[0]
        for widget in self.query(Tabs):
            widget.can_focus = False
        for widget in self.query(Tab):
            widget.can_focus = False
        self._load_initial_log()
        self.action_refresh()

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        if event.pane.id == "tab-status":
            self.query_one("#base-panel", BaseLayerPanel).focus()
        elif event.pane.id == "tab-logs":
            self.query_one("#log-panel", LogPanel).focus()
        elif event.pane.id == "tab-config":
            self.query_one("#config-psilia", ConfigPanel).focus()

    def _load_initial_log(self) -> None:
        self.query_one("#log-panel", LogPanel)._switch_log()

    def action_start_base(self) -> None:
        self.notify("Starting base layer...", severity="information")
        self.run_worker(self._start_base, thread=True)

    def action_stop_base(self) -> None:
        self.notify("Stopping base layer...", severity="information")
        self.run_worker(self._stop_base, thread=True)

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

    def action_prev_tab(self) -> None:
        self.query_one(Tabs).action_previous_tab()

    def action_next_tab(self) -> None:
        self.query_one(Tabs).action_next_tab()

    def action_reload_theme(self) -> None:
        self.register_theme(_load_theme())
        self._watch_theme(self.theme)
        self.notify("Theme reloaded", severity="information")

    def action_refresh(self) -> None:
        self.query_one("#base-panel", BaseLayerPanel).refresh_status()
        self.query_one("#spatial-panel", SpatialLayerPanel).refresh_status()
        self.run_worker(self._refresh_checks, thread=True)
        self.run_worker(self._refresh_nodes, thread=True)

    async def _start_base(self) -> None:
        from psilia_edge.runtime.core import start_base_layer

        try:
            start_base_layer()
            self.notify("Base layer started", severity="information")
        except Exception as e:
            self.notify(f"Start failed: {e}", severity="error")
        self.query_one("#base-panel", BaseLayerPanel).refresh_status()

    async def _stop_base(self) -> None:
        from psilia_edge.runtime.core import stop_runtime

        try:
            stop_runtime()
            self.notify("Runtime stopped", severity="information")
        except Exception as e:
            self.notify(f"Stop failed: {e}", severity="error")
        self.query_one("#base-panel", BaseLayerPanel).refresh_status()
        self.query_one("#spatial-panel", SpatialLayerPanel).refresh_status()

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

    async def _refresh_nodes(self) -> None:
        self.query_one("#spatial-panel", SpatialLayerPanel).refresh_nodes()

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
