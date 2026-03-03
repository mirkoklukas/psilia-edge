import typer

app = typer.Typer(help="Psilia Edge — spatial perception runtime for edge devices")
base_app = typer.Typer(help="Manage the base layer (daemon + web server)")
spatial_app = typer.Typer(help="Manage the Spatial Runtime (ROS nodes)")

app.add_typer(base_app, name="base")
app.add_typer(spatial_app, name="spatial")


@app.command()
def init(host: str = typer.Option(None, "--host", help="Skip discovery and connect to this IP or hostname directly.")):
    """Initialize a Jetson device."""
    from psilia_edge.init import run_init_wizard
    run_init_wizard(host=host)


@app.command()
def start():
    """Start the base layer and Spatial Runtime. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@app.command()
def stop():
    """Stop the base layer and Spatial Runtime. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@app.command()
def pull(device: str = typer.Argument(None, help="Target device name")):
    """Pull recordings from Jetson to laptop. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@app.command()
def push():
    """Push recordings from laptop to cloud. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@app.command()
def sync(device: str = typer.Argument(None, help="Target device name")):
    """Pull from Jetson then push to cloud. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@base_app.command("start")
def base_start():
    """Start the base layer only. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@base_app.command("stop")
def base_stop():
    """Stop the base layer only. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@spatial_app.command("start")
def spatial_start():
    """Start the Spatial Runtime (ROS layer) only. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError


@spatial_app.command("stop")
def spatial_stop():
    """Stop the Spatial Runtime (ROS layer) only. [dim](not yet implemented)[/dim]"""
    raise NotImplementedError
