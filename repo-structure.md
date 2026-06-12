# Repo Structure

> Rough overview of how the `psilia-edge` repository is organized.

```
psilia-edge/
  src/psilia/           Python package
    cli.py              Root CLI — `psilia` entry point, composition root
    edge/               Runtime, device management, edge sub-apps
    vision/             Camera, stereo, calibration
    transforms/         SE3 / transform trees
    data/               Recorded-data IO (mcap reader/parsers)
    utils.py            Shared dep-light helpers (yaml, console, paths)
  ros/                  ROS 2 package and Docker setup
  web/                  Browser UI (served by base layer)
  scripts/              Bootstrap scripts for Jetson setup
  docs/                 Documentation, design, architecture
  assets/               Logo files, ASCII art
  tools/                Place for tools like color and theme picker.
```

## `src/psilia/cli.py` — Root CLI

Composition root for the `psilia` command (entry point `psilia.cli:app`). Owns
the top-level Typer `app`, mounts the edge sub-apps flat (`psilia runtime` /
`sensor` / `data`), and is where general, non-edge top-level commands go. As
other subpackages grow a CLI surface, their sub-apps get mounted here.

## `src/psilia/edge/` — Edge Subpackage

Runtime lifecycle and device management. `cli.py` here exposes the edge sub-apps
(runtime, sensor, data) and the `debug` command — the root CLI composes them.

```
psilia/edge/
  cli.py                Edge sub-apps (runtime, sensor, data) + `debug`
  ui.py                 Rich-based terminal output helpers
  runtime/              Runtime lifecycle (the core product)
    sensor.py           Sensor registration and calibration management
  device_manager/       Laptop-side device and data management
  network/              Network/connectivity helpers
```

## `src/psilia/vision/` — Vision Subpackage

Camera calibration, stereo geometry, and camera streaming.

```
psilia/vision/
  camera_calibration.py   CameraCalibration / StereoCalibration classes
  camera_stream.py        Camera capture / streaming helpers
```

## `src/psilia/data/` — Data Subpackage

Recorded-data IO for exploring spatial data offline (no ROS, no runtime).
`data/mcap/` holds the MCAP reader/parsers; the package leaves room for other
formats later.

## `src/psilia/utils.py` — Shared Helpers

Dependency-light helpers used across subpackages (YAML load/save, `console`,
path/root resolution). Top-level module rather than a folder — kept dep-light
so it imports cleanly on the Jetson. If a real shared layer or the inference
engine lands later, promote to a `core/` package with an explicit import rule.


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
