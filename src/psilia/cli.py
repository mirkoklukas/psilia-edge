# Root CLI — the `psilia` command.
#
# This is the composition root: it owns the top-level Typer `app` and mounts
# sub-apps contributed by the subpackages. Today everything comes from
# `psilia.edge`, mounted flat (psilia runtime / sensor / data) to preserve the
# existing UX. General, non-edge commands belong here at the top level; as other
# subpackages (data, vision, …) grow a CLI surface, mount their sub-apps here.

import typer

from psilia.edge.cli import data_app, debug, sensor_app
from psilia.edge.runtime.cli import app as runtime_app

app = typer.Typer(help="Psilia — spatial perception for edge devices")

# ── edge sub-apps (mounted flat) ──────────────────────────────────────────────
app.add_typer(
    runtime_app,
    name="runtime",
    help="Commands to operate the runtime on Jetson devices",
)
app.add_typer(sensor_app, name="sensor")
app.add_typer(data_app, name="data")

# ── top-level commands ────────────────────────────────────────────────────────
app.command(hidden=True)(debug)


if __name__ == "__main__":
    app()
