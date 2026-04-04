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

### Depth pipeline integration with calibration

Sensor registration and calibration management is done (`psilia sensor add/list/remove/push/scan`).
Calibration files live in `~/.psilia/calibrations/`, sensor entries in `psilia.yaml` under `sensors:`.
See design.md "Sensors & Calibration" section.

What remains:
- Wire calibration resolution into the launch flow: `start_spatial_layer()` resolves
  the calibration file (via `resolve_calibration()` in `sensor.py`) and passes it
  to `launch_params.yaml`.
- Add rectify_node, depth_node, and depth_preview_node to the launch script with
  the `calibration_file` parameter.
- Backfill USB fields on label-keyed sensors when detected for the first time
  (designed but not yet implemented).

## Other

### Depth pipeline
- Replace Kalibr camchain format with our own calibration format
  (noted in rectify_node.py and depth_node.py).
- Compute and publish a confidence map alongside depth (depth_node.py).
- Optionally publish the raw disparity map on /psilia/disparity (depth_node.py).
- Generalize preview_node into a single node that accepts a list of image
  topics and frame rates, replacing both preview_node and depth_preview_node.

### Data
- Implement `psilia data pull` — pull recorded MCAP data from Jetson to laptop over SSH/rsync. Design the CLI command, naming conventions, and destination path (`data.pull_to` in `psilia.yaml`).
- Implement `psilia data push` — push recorded MCAP data from Jetson to a remote destination (laptop or cloud). Complement to `data pull`: where pull is laptop-initiated, push is Jetson-initiated. Design target configuration (cloud bucket URL or laptop address), authentication, and how the destination is stored in `psilia.yaml`.

### Runtime
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
- Structure logging across the stack and document a clear map of what writes where: daemon PID and log (`~/.psilia/run/`, `~/.psilia/log/`), ROS node logs (`{runtime_home}/log/` via `ROS_LOG_DIR`), colcon build logs (`{runtime_home}/ros/log/`), FastAPI/uvicorn logs, and `heartbeat.json`/`status.json` in `~/.psilia/run/`.
- Set up structured logging across `psilia_edge` (currently using `logging.getLogger(__name__)` in places but no root config). Warnings like rosbridge publish failures currently go nowhere.

### Config & Validation
- Add validation for config files (`psilia.yaml`, `runtime.yaml`) — schema check on read, clear error messages for missing or malformed fields.
- `runtime.yaml` should eventually have a `launch_args:` section — a user-friendly place to configure ROS node parameters (camera type, resolution, etc.). Before launch, `start_spatial_layer()` reads this section and writes a properly formatted ROS params yaml to `~/.psilia/run/` which gets passed to the nodes via `parameters=[...]`.

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
