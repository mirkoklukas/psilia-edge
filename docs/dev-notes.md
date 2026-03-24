# Dev Notes

> **Summary:** Internal working notes not intended for end users. Covers the V0 feature scope and desired experience, open TODOs with priorities, troubleshooting recipes, and longer-form design ideas (package distribution, calibration storage, camera pipeline, ring buffer).

## V0 Scope

### V0 Features and Experience

**Prerequisites**: Jetson runs, and we know how to ssh into the Jetson. Jetson is able to start a hotspot (WiFi-dongle preferred). We need a way to ssh into the Jetson from our laptop initially, so either it is on a common WiFi network, or we have a ethernet cable connecting both machines.

#### Desired Experience for V0:

- Install Psilia-Edge locally (Laptop). Clone repo and pip-install
- Pair with device
  - sets up ssh connection
- Bootstrap Device:
  - Clone repository on device, and pip-install
  - Init
- Setup device (should we call this *configure*??)
    - Network-hotspot
    - Camera (do we need that? Or are we grabing the first available camera on runtime start)
    - Future: network-cloud, direct upload to cloud from device
- (Update. Get the most recent changes: git pull, build image, copy and build ros ws)
- Start runtime base layer:
  - start webserver and server Web UI
  - start docker container without the launch script or anything else.
  - checks for cameras and if everything is ready for the spatial runtime layer
- Start spatial runtime:
  - Initial check if everything we need is in place, e.g. camera.
  - Starts the ros nodes and publishes all relevant topics.
- Record data through the Web UI.
- Pull data from device to laptop.
- Explore pulled data in a jupyter notebook on the laptop (or in the cloud).


#### Features:

(UNDER CONSTRUCTION)

- **WebUI:**
  - Camera stream, (throttled) and downsampled (configurable in RT config)
  - Spatial RT start/stop
    - Choose RT config to use on next start (options from `RT_HOME/config`)
  - Recording start/stop
    - choose which topics to record; defaults from RT config
    - easy way of nameing the recording `{device}_{session}_{counter}_{time}.mcap`; random default for sessions from a hidden configuration file (some cool names).

- **CLI** — all runtime commands are under `psilia runtime` or the shorthand `rt`:
  - `rt pair [host] [pass]`: pair a Jetson, set up SSH keypair, register device
  - `rt devices`: list registered devices
  - `rt init <path>`: initialize runtime home, dirs, entry to `psilia.yaml`, minimal setup so the runtime runs locally (dev-mode basically), but without sensors or hotspot
  - `rt setup [--network] [--camera]`: configures `psilia.yaml` and `runtime.yaml`
  - `rt start [<device>]`: start both layers; `--base-only` or `--spatial-only` to start just one
  - `rt stop [<device>]`: stop both layers; `--base-only` or `--spatial-only` to stop just one
  - `rt attach [<device>]`: live-view (primary way to monitor the runtime)
  - `rt update [<device>]`: pull latest ROS package, rebuild Docker image

- CLI nice help visualization

#### Future Versions
 - IMU and other sensors


## TODOs

(MAKE SURE THIS IS SOMEHWAT UP TO DATE)

- **[NEXT]** Implement `psilia data pull` — pull recorded MCAP data from Jetson to laptop over SSH/rsync. Design the CLI command, naming conventions, and destination path (`data.pull_to` in `psilia.yaml`).
- Implement `psilia data push` — push recorded MCAP data from Jetson to a remote destination (laptop or cloud). Complement to `data pull`: where pull is laptop-initiated, push is Jetson-initiated. Design target configuration (cloud bucket URL or laptop address), authentication, and how the destination is stored in `psilia.yaml`.
- **[NEXT]** Finish runtime refactoring — review any remaining loose ends from the two-layer runtime redesign (base layer owns container, spatial layer via docker exec).

- **[HIGH PRIORITY]** Fix `device_decorator` to forward flags to the remote command. Currently it only forwards `psilia runtime {func_name}` with no arguments, so any decorated command that also takes flags (e.g. `psilia runtime config --data-dir -d my-jetson`) silently drops those flags when run with `-d`. Fix by reconstructing the full CLI invocation from `sys.argv`, stripping `--device`/`-d` and its value, before passing to `run_on_device`.
- **[HIGH PRIORITY]** Revisit the network setup step (`_step_network`). Currently it looks for a USB WiFi dongle, but we should enumerate all interfaces that support AP mode and let the user choose. Show clearly which are USB dongles vs. built-in PCIe (e.g. via `wlx` prefix and `lsusb` cross-reference). Also handle hotspot autostart via NetworkManager during setup so the hotspot comes up on boot without manual intervention. Keep in mind that the connection needs to support live camera streaming to the web UI — low-res, low frame rate (e.g. 320x240 @ 5fps), but smooth enough to be useful for monitoring. Original full-res images are recorded separately; only downsampled versions are streamed. The hotspot interface choice and configuration should be validated against this bandwidth requirement.
- **[HIGH PRIORITY]** Camera support: scanning for connected cameras is roughly done (`hotplug.py`). Next step is a ROS node that reads from different camera types (USB, ZED, OAK-D, RealSense, etc.) and publishes on the stable `/psilia/image` interface. The node should be configurable (camera type and parameters from `runtime.yaml`) and handle device detection at startup.
- Write tests for camera device opening — validate that `cv2.VideoCapture` works with string device paths (`/dev/video0`) and integer indices across OpenCV versions. Had a regression where explicit `cv2.CAP_V4L2` + string path stopped working; see TODO in `camera_stream.py`.
- Fix `psilia runtime stop` behavior when spatial layer is already stopped — currently shows `spatial.status: error` even when spatial was never running. Should show a neutral/not-running status instead of an error when stopping something that wasn't started.
- Implement home network detection in the base layer: check whether the Jetson is connected to the WiFi SSID declared under `network.home` in `psilia.yaml` (e.g. via `nmcli -t -f active,ssid dev wifi`) and expose the result in `/api/status`. Indicate home network connectivity in the Web UI.
- show logs in live view, ros2 logs and so on
- Implement `hotplug` in the daemon: use `pyudev` to watch for USB device events (cameras, network dongles) and react — update `psilia.yaml`, notify the UI. Replaces the current "written once, may go stale" camera/hotspot detection.
- Structure logging across the stack and document a clear map of what writes where: daemon PID and log (`~/.psilia/run/`, `~/.psilia/log/`), ROS node logs (`{runtime_home}/log/` via `ROS_LOG_DIR`), colcon build logs (`{runtime_home}/ros/log/`), FastAPI/uvicorn logs, and `heartbeat.json`/`status.json` in `~/.psilia/run/`. Should answer: where do I look when something goes wrong at each layer?
- Design how the spatial runtime ros node configuration and so on can be configured.
- Add validation for config files (`psilia.yaml`, `runtime.yaml`) — schema check on read, clear error messages for missing or malformed fields.
- Set up structured logging across `psilia_edge` (currently using `logging.getLogger(__name__)` in places but no root config). Warnings like rosbridge publish failures currently go nowhere.
- Check Runtime status reliability: `status.json` and `heartbeat.json` are ephemeral (cleared on container start), and `_read_heartbeat()` now checks file mtime to detect stale data. But `_read_ros_status()` still depends on the rosbridge WebSocket publish succeeding — if that fails, `status.json` won't be refreshed and the ros section will be missing. Needs a reliable trigger mechanism (WebSocket, ROS topic, or direct container exec).
- Add a `psilia runtime status --reliable` (or `--slow`) mode that fetches ROS nodes and topics directly via `docker exec ros2 node list` / `ros2 topic list` — slower but ground-truth, doesn't depend on rosbridge or status.json.
- `psilia runtime status` should never show stale state from a previous session. Any data sourced from files (`heartbeat.json`, `status.json`) must either pass a freshness check or be shown as unavailable.
- `run_streamed` and any `docker run` calls should avoid the `-t` (pseudo-TTY) flag when not running interactively — `-t` causes the container to emit `\r\n` line endings, which produce staircase rendering in Rich when piped.


## Troubleshooting

### Viewing ROS node logs

All ROS nodes log to stdout (`RCUTILS_LOGGING_USE_STDOUT=1` is set in the docker run command). Use:

```bash
docker logs psilia-runtime        # full log
docker logs psilia-runtime -f     # follow live
docker logs psilia-runtime --tail 100  # last 100 lines
```

### Base layer fails to start — port already in use

Symptom in `~/.psilia/log/psilia-edge.log`:
```
ERROR: [Errno 48] error while attempting to bind on address ('0.0.0.0', 8080): address already in use
```

This usually means a previous psilia server is still running (stale PID file) or another process is on port 8080.

Find what's on the port:
```bash
lsof -i :8080
```

Kill the psilia process (replace PID with the one from `lsof`):
```bash
kill <PID>
```

Or kill everything on the port in one shot:
```bash
lsof -ti :8080 | xargs kill
```

Then run `psilia runtime stop` to clean up the stale PID file before starting again.

### Docker build fails — parent snapshot does not exist

Symptom:
```
ERROR: failed to solve: failed to prepare extraction snapshot "...": parent snapshot ... does not exist: not found
```

This is a Docker layer cache corruption issue, not a code problem. The build steps complete successfully but the final export fails.

Fix:
```bash
docker builder prune -f
```

Then rebuild.


## Notes & Ideas & Keep-in-minds

### Package distribution: extras vs namespace packages

Two options for splitting out the data API and future utilities from the core runtime:

**Extras** (`pip install psilia-edge[data]`) — one package, optional dependency groups. `pip install psilia-edge` gives the minimal runtime for Jetson; `pip install psilia-edge[data]` adds `mcap`, `numpy`, and future data/analysis tools for the laptop side. Simpler to maintain, recommended for now.

**Namespace packages** — multiple separately-installable packages (`psilia-edge`, `psilia-data`, ...) that all expose modules under a shared `psilia.*` namespace. Independent PyPI packages, can live in separate repos, stitched together by Python at import time. More overhead, makes sense only if the sub-packages are genuinely independent and distributed separately.

The three sub-packages and their deployment targets:

| Package | Target | Role |
|---|---|---|
| `psilia-edge` | Jetson (host) | Runtime, CLI, base + spatial layer lifecycle |
| `psilia-inference` | Docker container | Inference algorithms, model wrappers, ROS nodes |
| `psilia-dev` | Laptop / cloud | MCAP reader, data API, notebook utilities, dev tooling |

Since these have distinct deployment targets, namespace packages may make more sense than extras long-term — you'd never want inference deps on the Jetson host or dev tooling inside Docker.

### Calibration storage

Store calibration data in `psilia.yaml` (or split into a dedicated file — e.g. `calibrations.yaml` — if it grows large). Key idea: use a unique sensor identifier (e.g. serial number) as the key, so calibration data is reliably mapped to a specific physical sensor regardless of port or connection order.

Each entry stores intrinsic and extrinsic calibration. Simple case: a single stereo camera (intrinsics per lens + stereo extrinsics). More complex case: a full sensor rig with multiple cameras and/or IMUs, each with their own intrinsics and extrinsics relative to a common rig frame.

```yaml
calibrations:
  <sensor-serial>:
    type: stereo_camera   # or mono_camera, imu, sensor_rig, ...
    intrinsics:
      left:  { ... }
      right: { ... }
    extrinsics:
      left_to_right: { ... }
  <rig-serial>:
    type: sensor_rig
    sensors:
      - serial: <sensor-serial>
        extrinsic_to_rig: { ... }
```

May split into a separate `calibrations.yaml` once the schema is stable, with a pointer in `psilia.yaml`.

- Home network (`network.home`) is declared in `psilia.yaml`. The base layer detects if the Jetson is on that network and indicates it in the Web UI. Future: trigger cloud upload when connected. Other connection types (ethernet) may be relevant here too.

### Camera pipeline architecture

The frame pipeline is central to the runtime. The target architecture separates concerns into three layers:

1. **CameraStream** — capture thread writes frames into a shared ring buffer. Pure Python/OpenCV, no ROS dependency.
2. **Algorithm workers** (pose estimation, depth inference, etc.) — plain Python, each reads from the ring buffer, copies their frame, runs inference. No ROS.
3. **ROS publisher nodes** — thin wrappers that drain result queues and publish to `/psilia/pose`, `/psilia/depth`, etc. ROS is only involved at this last step.

This keeps algorithms independently testable outside ROS and decouples inference speed from the ROS publish rate.

### Ring buffer for zero-copy frame sharing across processes

For sharing frames across OS processes without copying through ROS topics or queues:

- Main process allocates `N * frame_size + sizeof(int)` bytes via `multiprocessing.shared_memory`
- Layout: N fixed-size frame slots + one int (write index) at a known offset
- Capture thread writes frame at slot `i % N`, increments index
- Each consumer process attaches by name, reads from `index - 1`, copies once into their own working buffer
- Multiple readers never conflict — reads don't advance the pointer, only the capture thread does
- At 30fps and N=10 slots, consumers have ~300ms of slack before their slot gets overwritten

Synchronization is minimal — one atomic int write. No locks needed if memory ordering is handled carefully. At 3200x1200 color (11.5 MB/frame) zero-copy at the handoff matters — each consumer still pays one copy into their working buffer, but no additional copies for routing/queuing.

- `runtime.yaml` should eventually have a `launch_args:` section — a user-friendly place to configure ROS node parameters (camera type, resolution, etc.). Before launch, `start_spatial_layer()` reads this section and writes a properly formatted ROS params yaml to `~/.psilia/run/` which gets passed to the nodes via `parameters=[...]`. Currently the params file is written directly from auto-detected values.

- "runtime home" has a nice ring to it — `runtime.home_path` in the config reads naturally. Settled on `psilia-runtime-home` as the default directory name.
- The ROS workspace (`psilia_runtime`) is copied to the runtime home and mounted into the container at runtime — it is NOT baked into the Docker image. This keeps it visible and editable on the host without rebuilding the image. May revisit if we ever want a fully self-contained image.

### /psilia/interface — keeping it honest

The static info topic currently hardcodes the list of topics Psilia publishes.
This is a promise to other nodes — but if a node isn't running (e.g. depth_node
disabled, camera not connected), the promise is broken.

Need a way to keep /psilia/info in sync with what is actually being published.
Some directions worth exploring:

- Have each node register itself at startup (e.g. publish to a /psilia/registry
  topic or write to a shared state). The status node aggregates and re-broadcasts.
- Introspect the ROS graph at startup (ros2 topic list) and filter for /psilia/*
  topics that have active publishers before broadcasting /psilia/info.
- Delay the /psilia/info broadcast slightly to let all nodes come up, then
  discover what's actually live before publishing.
- Treat /psilia/info as dynamic (re-publish periodically) rather than truly static,
  so it reflects the current state of the graph.
