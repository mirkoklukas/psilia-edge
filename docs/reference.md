# Psilia Edge — Reference

Core capabilities of the system. Source for `reference.html`.

---

## Device Management

### `psilia pair`
> Pair a Jetson over SSH #CLI

Interactive wizard that connects to a Jetson on the local network, generates a dedicated SSH keypair, adds a managed section to ~/.ssh/config, and registers the device in ~/.psilia/psilia.yaml.

### `psilia bootstrap <device>`
> Bootstrap a Jetson over SSH #CLI

Copies the bootstrap script to a paired device and runs it remotely. Clones the repo, installs the CLI, and sets up the runtime home directory. Requires psilia pair first.

### `psilia devices`
> List registered devices #CLI

Shows all Jetson devices registered in ~/.psilia/psilia.yaml with their SSH host and key paths.

---

## Sensors & Calibration

### `psilia sensor scan`
> Detect connected cameras and USB devices #CLI

Enumerates connected USB cameras and devices. On Linux uses v4l2 and sysfs, on macOS uses system_profiler. Groups stereo cameras (dual /dev/video nodes) into a single physical device.

### `psilia sensor add`
> Register a sensor and associate a calibration file #CLI

Interactive wizard that detects connected cameras, prompts for a calibration file and label, and writes the sensor entry to ~/.psilia/psilia.yaml. Calibration files are copied to ~/.psilia/calibrations/. Also supports non-interactive mode via --key and --raw flags.

### `psilia sensor remove <key>`
> Unregister a sensor #CLI

Removes a sensor entry from ~/.psilia/psilia.yaml by its key (label or UID). Optionally deletes the associated calibration file with --delete-calibration.

### `psilia sensor list`
> Show registered sensors #CLI

Displays all sensors in ~/.psilia/psilia.yaml with their UID, label, and calibrated resolutions. Supports --json for machine-readable output and -d <device> to query a remote device.

### `psilia sensor push <device>`
> Push sensor entries and calibrations to a remote device #CLI

Copies sensor entries and calibration files to a registered Jetson over SSH. By default pushes all sensors; use --key for a specific one. Skips sensors already registered on the device unless --overwrite is set.

---

## Runtime Lifecycle

### `psilia runtime init [path]`
> Create runtime home, Docker image, ROS workspace #CLI

Sets up the runtime home directory structure (ros/, data/, log/, conf/), copies the ROS package, builds the Docker image, and writes a default runtime.yaml. Path defaults to the current directory.

### `psilia runtime setup`
> Interactive setup (init + hotspot + WiFi) #CLI

Runs runtime init plus optional network configuration steps — AP hotspot setup for a USB WiFi dongle and home WiFi credentials. Use --all to run everything, or --hotspot / --wifi individually.

### `psilia runtime start --base`
> Start base layer (FastAPI + Docker container) #CLI

Starts the always-on base layer — a FastAPI web server serving the Web UI and REST API, and the Docker container. The container runs colcon build on startup (incremental, fast after first build).

### `psilia runtime start --spatial`
> Start spatial layer (ROS nodes) #CLI #WebUI

Launches ROS nodes inside the already-running container. Runs requirement checks (container, camera, calibration, resolution, hotspot) before launch and writes launch_params.yaml. Use --force to start with partial requirements.

### `psilia runtime stop`
> Stop spatial and base layers #CLI #WebUI

Stops the spatial layer (ROS nodes) and then the base layer (FastAPI server + Docker container). Use --spatial or --base to stop a single layer.

### `psilia runtime attach`
> Live TUI — heartbeat, topic Hz, start/stop spatial #CLI

Live terminal view refreshing at 1 Hz. Shows base and spatial layer status, heartbeat age, topic frequencies, and preflight checks. Keyboard shortcuts: [s] start, [x] stop, [f] toggle force, [r] refresh checks, [l] logs.

### `psilia runtime status`
> Status snapshot (base, spatial, docker, storage, etc.) #CLI

One-shot status of the runtime. Use flags to select sections — --base, --spatial, --docker, --ros, --storage, --hotspot, --recording. Supports --json for machine-readable output.

### `psilia runtime config [keys...]`
> Query runtime config values #CLI

Prints static config values, one per line. Available keys — home-dir, data-dir, ros-dir, log-dir, repo-dir, api-port, rosbridge-port. Designed for scripting via $(psilia runtime config home-dir).

---

## Data Operations

### `psilia data pull [device]`
> Pull MCAP recordings from device to laptop #CLI

Rsyncs the device's data directory to the laptop. Excludes any actively recording file. Without a device argument, pulls from all registered devices. Destination is configured via data.pull_to in psilia.yaml (prompted on first use).

### `psilia data push [device]`
> Push data to cloud (direct or via laptop) #CLI

With a device — SSH into the device with agent forwarding and rsync directly to the cloud (private key never leaves the laptop). Without a device — pushes the local pull_to directory. Destination is configured via data.push_to in psilia.yaml.

---

## Services

### `recording`
> Start/stop MCAP recording of ROS topics #WebUI #ROS

Managed by recording_node inside the Docker container. Controlled via ROS topics from the Web UI. Recordings are saved to {runtime_home}/data/ as {device}_{session}_{counter}_{time}.mcap. Publish to /psilia/web/recording/start (std_msgs/String) with JSON payload {session, topics[]}. Publish to /psilia/web/recording/stop to stop. Status published at 1 Hz on /psilia/recording/status (std_msgs/Bool).

### `preview`
> Live image previews for the Web UI #WebUI #ROS

Downsampled, low-bandwidth image streams for live monitoring. Image — /psilia/preview/image/compressed (CompressedImage, JPEG, 5 Hz). Depth — /psilia/preview/depth/compressed (CompressedImage, JPEG, 5 Hz), colormapped with Plasma, clamped to max_depth (default 3.0 m). Rectified — /psilia/preview/rectified/compressed (CompressedImage, JPEG, 5 Hz). Point cloud — /psilia/preview/pointcloud (PointCloud2, 2 Hz), XYZRGB back-projected from depth + rectified image.
