# Todos

## Next Session

### Logging: dual output (terminal + file) for CLI and daemon

Currently `logging.basicConfig` in `__init__.py` uses a single `RichHandler` (writes
to stdout). This works for the CLI (terminal) and the daemon (stdout redirected to
`~/.psilia/log/psilia-edge.log`), but:
- CLI logs don't persist to the log file.
- Daemon logs contain Rich markup in the file (messy).
- `start_spatial_layer()` can be called from either context — calibration resolution
  warnings should show in the terminal AND persist to the log file.

Need: detect context (CLI vs daemon) and configure handlers accordingly:
- CLI: `RichHandler` → terminal + plain `FileHandler` → log file
- Daemon: plain `FileHandler` → log file only (no `RichHandler`, no terminal)

This also ties into the broader "structure logging across the stack" TODO under
Status & Logging.

### Calibration classes (`src/psilia_edge/camera.py`)

- Test `CameraCalibration` and `StereoCalibration` for correctness:
  round-trip save/load, `from_kalibr`, `from_camera_info`, `rescale`,
  extrinsics inference from rectified projection, and stereo `rectify()`
  (verify P_rect matches OpenCV's output, remap tables produce aligned rows).
- Add an illustration/diagram showing the different maps and transforms:
  K, [R|t], R_rect, P_rect, and how they compose (raw → undistorted →
  rectified → projected). Clarify which properties return which matrix.

### Calibration — remaining items

Sensor registration, calibration resolution, and depth pipeline wiring are done.
See design.md "Sensors & Calibration" section.

What remains:
- Backfill USB fields on label-keyed sensors when detected for the first time
  (designed but not yet implemented).
- Support explicit calibration file path in `runtime.yaml` (`camera.calibration`)
  as a bypass that skips sensor registry lookup (TODO in `sensor.py`).
- Make resolution strategy configurable via `runtime.yaml` (e.g.
  `camera.resolution_strategy: smallest_compatible | calibration_match`).
  Currently hardcoded to `smallest_compatible` in `_configure_camera_resolution`.
- Investigate non-uniform calibration rescaling for cameras with different aspect
  ratios at different resolutions. Currently `is_calibration_compatible` requires
  uniform scaling (same factor in x and y). Non-uniform scaling is mathematically
  valid for pinhole intrinsics, but only correct if the camera uses binning (not
  cropping) across resolution modes. To verify:
  1. Quick test: capture a checkerboard at each resolution, overlay the images
     scaled to the same size — if the field of view matches, it's binning.
  2. Eye test: record short clips at each resolution, let the user visually
     compare FOV and distortion to confirm the sensor readout mode.
  If confirmed, relax `is_calibration_compatible` to allow non-uniform scaling
  and update `CameraCalibration.rescale` to accept separate x/y factors.

## Other

### Docker image: shared Python package
Figure out what to install in the Docker image so the ROS nodes and the host
CLI share the same code without duplication. Options: install full `psilia-edge`,
a minimal `psilia-core` package, or a new lightweight shared package. Currently
`camera.py` is copied into both `psilia_edge` and `psilia_runtime` — this is a
stopgap until a proper shared package strategy is in place.

### ROS nodes: remove unused camera_left/camera_right params
The `camera_left` / `camera_right` ROS parameters in depth_node, depth_cuda_node,
rectify_node, and camera_node are now unused — `StereoCalibration.load` always
uses cam0/cam1. Remove the params and update launch configs accordingly.

### Isaac ROS / ESS stereo depth
- Explore NVIDIA's `isaac_ros_common` workflow (`run_dev.sh`, `docker_deploy.sh`,
  Isaac ROS CLI) and evaluate whether it offers benefits over our standalone
  Dockerfile approach. Currently we bypass it in favor of a simpler
  `dustynv/ros` base + `apt-get install` for Isaac ROS packages.
- Understand how NVIDIA versions and distributes Isaac ROS Docker images via NGC
  (`nvcr.io`), including auth requirements and EULA implications for ESS models.

### Depth pipeline
- GPU acceleration for rectify and depth nodes on Jetson. Currently rectify
  uses ~250% CPU (`cv2.remap` x2) and depth ~113% CPU (`StereoSGBM`) at
  1280x720, starving other nodes. Use `cv2.cuda.remap` for rectification
  and explore CUDA stereo matching (`cv2.cuda.StereoSGBM` or
  `cv2.cuda.StereoBM`) for depth. This would free most of the CPU budget.
- Compute and publish a confidence map alongside depth (depth_node.py).
- Optionally publish the raw disparity map on /psilia/disparity (depth_node.py).
- Generalize preview_node into a single node that accepts a list of image
  topics and frame rates, replacing both preview_node and depth_preview_node.

### Data
- Implement `psilia data pull` — pull recorded MCAP data from Jetson to laptop over SSH/rsync. Design the CLI command, naming conventions, and destination path (`data.pull_to` in `psilia.yaml`).
- Implement `psilia data push` — push recorded MCAP data from Jetson to a remote destination (laptop or cloud). Complement to `data pull`: where pull is laptop-initiated, push is Jetson-initiated. Design target configuration (cloud bucket URL or laptop address), authentication, and how the destination is stored in `psilia.yaml`.

### Runtime
- Establish a return-type pattern for layer status checks. `is_running()` (daemon)
  and `is_container_running()` (docker) return `bool`, but spatial layer status has
  four states: `stopped`, `running`, `stale`, `crashed`. Decide on a convention
  (e.g. `bool | str`, enum, named tuple) and add `is_spatial_layer_running()` in
  `status.py` or `core.py`. See `start_spatial_layer()` docstring for the
  `launch_id` protocol and state table.
- Finish runtime refactoring — review any remaining loose ends from the two-layer runtime redesign (base layer owns container, spatial layer via docker exec).
- Fix `device_decorator` to forward flags to the remote command. Currently it only forwards `psilia runtime {func_name}` with no arguments, so any decorated command that also takes flags (e.g. `psilia runtime config --data-dir -d my-jetson`) silently drops those flags when run with `-d`. Fix by reconstructing the full CLI invocation from `sys.argv`, stripping `--device`/`-d` and its value, before passing to `run_on_device`.
- Fix `psilia runtime stop` behavior when spatial layer is already stopped — currently shows `spatial.status: error` even when spatial was never running. Should show a neutral/not-running status instead of an error.
- `run_streamed` and any `docker run` calls should avoid the `-t` (pseudo-TTY) flag when not running interactively — `-t` causes the container to emit `\r\n` line endings, which produce staircase rendering in Rich when piped.

### Network
- Revisit the network setup step (`_step_network`). Currently it looks for a USB WiFi dongle, but we should enumerate all interfaces that support AP mode and let the user choose. Show clearly which are USB dongles vs. built-in PCIe (e.g. via `wlx` prefix and `lsusb` cross-reference). Also handle hotspot autostart via NetworkManager during setup so the hotspot comes up on boot without manual intervention.
- Implement home network detection in the base layer: check whether the Jetson is connected to the WiFi SSID declared under `network.home` in `psilia.yaml` (e.g. via `nmcli -t -f active,ssid dev wifi`) and expose the result in `/api/status`. Indicate home network connectivity in the Web UI.

### Camera
- Camera support: scanning for connected cameras is roughly done (`hotplug.py`). Next step is a ROS node that reads from different camera types (USB, ZED, OAK-D, RealSense, etc.) and publishes on the stable `/psilia/image` interface. The node should be configurable (camera type and parameters from `runtime.yaml`) and handle device detection at startup.
- Write tests for camera device opening — validate that `cv2.VideoCapture` works with string device paths (`/dev/video0`) and integer indices across OpenCV versions. Had a regression where explicit `cv2.CAP_V4L2` + string path stopped working; see TODO in `camera_stream.py`.

### Status & Logging
- Check Runtime status reliability: `status.json` and `heartbeat.json` are ephemeral (cleared on container start), and `_read_heartbeat()` now checks file mtime to detect stale data. But `_read_ros_status()` still depends on the rosbridge WebSocket publish succeeding — if that fails, `status.json` won't be refreshed and the ros section will be missing. Needs a reliable trigger mechanism (WebSocket, ROS topic, or direct container exec).
- Add a `psilia runtime status --reliable` (or `--slow`) mode that fetches ROS nodes and topics directly via `docker exec ros2 node list` / `ros2 topic list` — slower but ground-truth, doesn't depend on rosbridge or status.json.
- `psilia runtime status` should never show stale state from a previous session. Any data sourced from files (`heartbeat.json`, `status.json`) must either pass a freshness check or be shown as unavailable.
- Show logs in live view, ros2 logs and so on.
- Add log source cycling to `psilia runtime attach`: a key (e.g. `[n]`) to
  cycle the log panel between `ros.log`, `psilia-edge.log` (daemon), and
  per-node ROS logs. The Rich `Live` + key handling infrastructure is already
  in place (`_run_attach` in `cli.py`). Also add a `--source` flag to
  `psilia runtime logs` for non-interactive use.
- Structure logging across the stack and document a clear map of what writes where: daemon PID and log (`~/.psilia/run/`, `~/.psilia/log/`), ROS node logs (`{runtime_home}/log/` via `ROS_LOG_DIR`), colcon build logs (`{runtime_home}/ros/log/`), FastAPI/uvicorn logs, and `heartbeat.json`/`status.json` in `~/.psilia/run/`.
- Set up structured logging across `psilia_edge` (currently using `logging.getLogger(__name__)` in places but no root config). Warnings like rosbridge publish failures currently go nowhere.

### Config & Validation
- Add validation for config files (`psilia.yaml`, `runtime.yaml`) — schema check on read, clear error messages for missing or malformed fields.
- `runtime.yaml` should eventually have a `launch_args:` section — a user-friendly place to configure ROS node parameters (camera type, resolution, etc.). Before launch, `start_spatial_layer()` reads this section and writes a properly formatted ROS params yaml to `~/.psilia/run/` which gets passed to the nodes via `parameters=[...]`.
- Add user-facing node control in `runtime.yaml` — either a positive `ros.nodes` list
  (explicit "run these") or a negative `ros.disabled_nodes` list ("skip these").
  `start_spatial_layer()` would apply this before writing `launch_params.yaml`.
  Decide which route to take when implementing.

### Hotplug
- Implement `hotplug` in the daemon: use `pyudev` to watch for USB device events (cameras, network dongles) and react — update `psilia.yaml`, notify the UI. Replaces the current "written once, may go stale" camera/hotspot detection.

### /psilia/interface — keeping it honest
The static info topic currently hardcodes the list of topics Psilia publishes.
This is a promise to other nodes — but if a node isn't running (e.g. depth_node
disabled, camera not connected), the promise is broken.

Directions worth exploring:
- Have each node register itself at startup (e.g. publish to a /psilia/registry
  topic or write to a shared state). The status node aggregates and re-broadcasts.
- Introspect the ROS graph at startup (ros2 topic list) and filter for /psilia/*
  topics that have active publishers before broadcasting /psilia/info.
- Delay the /psilia/info broadcast slightly to let all nodes come up, then
  discover what's actually live before publishing.
- Treat /psilia/info as dynamic (re-publish periodically) rather than truly static,
  so it reflects the current state of the graph.
