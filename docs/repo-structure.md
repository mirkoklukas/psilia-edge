# Repo Structure

> Rough overview of how the `psilia-edge` repository is organized.

```
psilia-edge/
  src/psilia/           Python packages (psilia.edge, psilia.core)
  ros/                  ROS 2 package and Docker setup
  web/                  Browser UI (served by base layer)
  scripts/              Bootstrap scripts for Jetson setup
  docs/                 Documentation
  assets/               Logo files, ASCII art
```

## `src/psilia/` — Python Packages

The `psilia` namespace contains two subpackages:

- **`psilia.edge`** — CLI, runtime lifecycle, device management. Provides the `psilia` CLI entry point.
- **`psilia.core`** — Inference engine (WIP).

```
psilia/
  edge/
    cli.py                Top-level CLI (typer) — runtime, sensor, data sub-apps
    ui.py                 Rich-based terminal output helpers
    runtime/              Runtime lifecycle (the core product)
      sensor.py           Sensor registration and calibration management
    device_manager/       Laptop-side device and data management
    network/              Network/connectivity helpers
    mcap/                 MCAP recording utilities (WIP)
  core/                   Inference engine (WIP)
```


## `ros/` — ROS 2 Package & Docker

Contains the ROS 2 colcon workspace and the Docker setup that runs it.

```
ros/
  docker/               Dockerfile and container scripts
  psilia_runtime/       ROS 2 package (mounted into container)
    psilia_runtime/
      nodes/              Psilia's ROS nodes
      ...                 Python package files
```


## `web/` — Browser UI

Static HTML/CSS/JS served by the FastAPI base layer from `{repo_dir}/web/`.
Pages for runtime status, recording control, config display, and dev tools.
