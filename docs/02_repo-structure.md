# Repo Structure

> Rough overview of how the `psilia-edge` repository is organized.

```
psilia-edge/
  src/psilia_edge/      Python package — CLI, runtime, device management
  src/psilia_core/      Python package — inference engine (WIP)
  ros/                  ROS 2 package and Docker setup
  web/                  Browser UI (served by base layer)
  scripts/              Bootstrap scripts for Jetson setup
  docs/                 Documentation, design, architecture
  assets/               Logo files, ASCII art
  tools/                Place for tools like color and theme picker.
```

## `src/psilia_edge/` — Edge Package

CLI, runtime lifecycle, and device management. Provides the `psilia` CLI entry point.

```
psilia_edge/
  cli.py                Top-level CLI (typer) — runtime, sensor, data sub-apps
  ui.py                 Rich-based terminal output helpers
  camera.py             Camera and stereo calibration classes
  runtime/              Runtime lifecycle (the core product)
    sensor.py           Sensor registration and calibration management
  device_manager/       Laptop-side device and data management
  network/              Network/connectivity helpers
  mcap/                 MCAP recording utilities (WIP)
```

## `src/psilia_core/` — Core Package

Inference engine (WIP).


## `ros/` — ROS 2 Package & Docker

Contains the ROS 2 colcon workspace and the Docker setup that runs it.

```
ros/
  docker/               Dockerfile and container scripts
  psilia_runtime/       ROS 2 package (mounted into container)
    launch/             Launch files
    psilia_runtime/
      nodes/            Psilia's ROS nodes
      ...               Python package files
```


## `web/` — Browser UI

Static HTML/CSS/JS served by the FastAPI base layer from `{repo_dir}/web/`.
Pages for runtime status, recording control, config display, and dev tools.
