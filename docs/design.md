# Psilia Edge — Spatial Runtime



## Filesystem Layout

The key mental model is as follows: The user clones and install the repository at a location of their choice (repo directory). Once installed the CLI is up. The CLI has its own state storage (config directory) under `~/.psilia/`. The runtime is the "product". A set up runtime has it's own additional user-facing and user-specified folder (runtime home), e.g. `~/psilia-runtime-home/`.

📁 **Repo Directory** `~/psilia-edge/` (cloned by the user).

The repo dir is wherever the user cloned it. Once `pip install -e .` is run, the CLI is available and the repo path can be looked up at runtime. It is separate from the runtime dir. The repo is the "source code" of the CLI. Not the product.

📁 **Web Directory** `~/psilia-edge/web`.

The `web/` directory lives in the repo and is served directly from there (`{repo_dir}/web/dist/`). This works cleanly for v0 because the repo is always present on the machine. When psilia-edge is eventually published to PyPI and installed non-editably, the web assets should move to package data (via `importlib.resources`) so they are included in the distribution.

📁 **Config Directory** `~/.psilia/` (hidden, CLI-internal).

The user never needs to know this exists. It stores the CLI's own state: a pointer to where the runtime lives, SSH keys for managed devices, and the device registry. Fixed path, overridable via `PSILIA_DIR` for testing.

```
~/.psilia/
  psilia.yaml               # unified config: runtime home path, device registry
  run/psilia-edge.pid       # daemon PID file
  log/psilia-edge.log       # daemon log
  keys/<device-name>        # SSH private key per registered device
```

📁 **Runtime Home** `~/psilia-runtime-home/` (user-facing, the product).

This is where the runtime lives. Intentionally visible and not hidden — the user is expected to look in here, edit config files, inspect data. Contains the ROS workspace, recordings, logs, and user-editable config. The path is chosen during `psilia runtime setup` and can be anywhere; the defaults are `~/psilia-runtime-home` on laptop and `/ssd/psilia-runtime-home` on Jetson.

```
psilia-runtime-home/
  ros/            # colcon workspace, mounted into Docker at runtime
  data/           # MCAP recordings
  log/            # runtime logs
  conf/           # Default place to put alternative runtime configs
  runtime.yaml    # user-editable: what nodes to start, topics to record, etc.
```


📄 **Other files** the CLI touches:

`psilia pair` also adds a managed section to `~/.ssh/config` (bounded by `# >>> psilia-edge` / `# <<< psilia-edge` markers) with one entry per registered device. Nothing outside that section is touched.

## Two Roles

The same `psilia-edge` package is installed on both your laptop and Jetson device, but each takes on a distinct role:

**(Spatial) Runtime host** (Jetson) — runs the spatial perception stack. Hosts the base layer daemon, the ROS layer in Docker, and serves the Control UI. Anything you called `psilia runimte setup` on, which basically means it has a "runtime home".

**Device/Data manager** (Laptop) — manages one or more runtime hosts. Handles pairing, bootstrapping over SSH, and data operations (pull, sync, cloud push). Keeps a registry of registered devices in `~/.psilia/psilia.yaml`.

The role distinction is intentional and usually distinct for a given machine — a Jetson is usually  a runtime host, a laptop is usually a device/data manager. However, a single machine *can* play both roles, but that is used mainly during development.


## Key Config Files

**`~/.psilia/psilia.yaml`** is the single unified config file for the psilia tooling on any machine.
Its path is `psilia_edge.runtime.config.CONFIG/"psilia.yaml"` and stored additionally in `psilia_edge.runtime.config.CONFIG_PATH`.

It can be split into two main part (potentially more in the future) — either or both may be present depending on what the machine does:
- (Spatial) Runtime specific: where the runtimes home folder is, and where to find the runtime configuration file, but also edge device information (e.g. how to access the hotspot)
- Device and Data Management

```yaml
#|
#|  Role 1: Runtime host
#|  (typically Jetson)
#|
# written by `psilia runtime setup`
runtime:
  home_path: ~/psilia-runtime-home
  config_path: ~/psilia-runtime-home/runtime.yaml
  api_port: 8080       # FastAPI web server port
  rosbridge_port: 9090 # rosbridge WebSocket port

# written by `psilia runtime setup` (Jetson only)
hotspot:
  ssid: my-jetson-ap       # NOTE: hardware may change between boots —
  password: psilia1234     # these values can be stale if dongle is swapped
  interface: wlx...        # or camera is unplugged. live detection TBD.

# written by `psilia runtime setup` (optional)
camera:
  type: null               # e.g. zed2i, oak-d, realsense

#|
#|  Role 2: Device and Data Management
#|  (typically Laptop)
#|
# written by `psilia pair`
registered_devices:
  my-jetson:
    host: my-jetson.local
    user: nvidia
    key: ~/.psilia/keys/my-jetson
```

A machine with `runtime.home_path` set has a local runtime installed. A machine with `registered_devices` set manages one or more remote runtimes. A laptop in dev mode can have both. This replaces the old role-detection heuristic of checking for a Jetson-specific file — the CLI now simply checks whether `runtime.home_path` is present.

**`{home_path}/runtime.yaml`** is user-editable and controls what nodes to start, which topics to record, and so on. Created with defaults by `psilia runtime setup`. Its path is stored in `psilia_edge.runtime.config.RUNTIME_CONFIG_PATH`. Everything runtime-specifig configurable information should go in here.

The default runtime config (`runtime.default.yaml`):
```yaml
name: My Runtime Config
ros:
  launch: default.launch.py
  recording:
    topics:
      - /psilia/interface
      - /psilia/heartbeat
```



## Environment and important config variables

|Python (`runtime.config`)| Env Variable | Default | Purpose |
|---|---|---|---|
| `CONFIG_DIR` | `PSILIA_DIR` | `~/.psilia` | Override the hidden psilia dir (e.g. `/ssd/.psilia` on Jetson)|
|`CONFIG_PATH`| - | - | Path to psilia config file `{CONFIG_DIR}/psilia.yaml`|
|`get_runtime_home()`| - | *(from psilia.yaml)* | Points to the runtime home directory |
|- | `PSILIA_SSH_CONFIG_PATH`| `~/.ssh/config`| Managing ssh connection for registered devices |
<!-- |`RUN_DIR`| `PSILIA_RUN_DIR` (REMOVED) | `CONFIG_DIR/run` | Override the PID file directory (e.g. `/run/psilia` on Jetson) |
|`LOG_DOR`| `PSILIA_LOG_DIR` (REMOVED) | `CONFIG_DIR/log` | Override the log file directory (e.g. `/var/log/psilia` on Jetson) | -->

The env vars exist primarily for testing and CI.


## Install Flow

The user clones the repository. Once `pip install -e .` is run, the CLI is available.
Now we can run `psilia runtime setup` which starts the interactive wizard that
provisions a runtime: prompts for the runtime path, creates the directory structure, writes `runtime.home_path` into `psilia.yaml`, and runs the remaining setup steps (Docker, network, etc.).

Works the same on laptop and Jetson. v0 assumes one runtime per machine.

`psilia pair` is a laptop-side wizard that registers a remote device into the `registered_devices` section of `psilia.yaml`.


## Dependencies

**System — required before `pip install`:**
Python 3.10+, `pip`, `git`.

**System — installed during `psilia runtime setup`:**
Docker. On Jetson: `nmcli` / NetworkManager (hotspot), `systemd` (autostart), `v4l-utils` (camera detection).

**Python packages (`psilia-edge`):**
`typer`, `rich`, `pyyaml`, `paramiko`, `fastapi`, `uvicorn`, `psutil`, `mcap`, `numpy`.

**Docker image (`psilia/runtime:latest`):**
ROS 2 Humble, CUDA / JetPack-compatible base, camera drivers, MCAP recorder, Foxglove bridge, `colcon`.

**`psilia` inference library (inside Docker only):**
`numpy`, `opencv-python`, and optional inference deps (`torch`, `onnxruntime`) installed as extras.


## Docker Container Layout

The container mounts a few directories from the host:

```
Host                             Container
{runtime_home}/ros/          →   /psilia/ros/            colcon workspace (built on startup)
{runtime_home}/log/          →   /psilia/log/            runtime logs
{runtime_home}/data/         →   /psilia/data/           MCAP recordings
{runtime_home}/runtime.yaml  →   /psilia/runtime.yaml    runtime config (read-only)
~/.psilia/psilia.yaml        →   /psilia/psilia.yaml     psilia config (read-only)
~/.psilia/run/               →   /psilia/run/            status files written by core_node
```

`/psilia/run/` is the shared state channel between the ROS layer and the host:
- `heartbeat.json` — written every 1 Hz tick by `core_node`: `status`, `stamp`, `ros_domain_id`
- `status.json` — written on demand when `core_node` receives a `/psilia/status_request` message: heartbeat fields + `nodes`, `topics`

The colcon workspace layout inside the container mirrors the host:
```
/psilia/
  ros/
    src/psilia_runtime/   # mounted from host — editable without rebuilding image
    build/                # created by colcon on container startup
    install/
    log/
  log/                    # runtime logs (mounted from host)
  data/                   # MCAP recordings (mounted from host)
  runtime.yaml            # runtime config (mounted read-only from host)
  psilia.yaml             # psilia config (mounted read-only from host)
  run/                    # status files written by core_node (mounted from host)
```

The entrypoint runs `colcon build --packages-select psilia_runtime` on every startup (incremental — fast after first build), sources the workspace, then launches `ros2 launch psilia_runtime default.launch.py`.

To clear the build cache (e.g. after `setup.py` changes), `psilia runtime update` spins up a temporary container to `rm -rf` the build dirs — no sudo needed on the host.


## Logging & Runtime Files

Where to look when something goes wrong at each layer:

| File | Written by | Contents |
|---|---|---|
| `~/.psilia/run/psilia-edge.pid` | `start_daemon()` in `daemon.py` | PID of the running FastAPI/uvicorn process |
| `~/.psilia/log/psilia-edge.log` | uvicorn (stdout/stderr redirected by `start_daemon()`) | Base layer startup, request logs, errors |
| `~/.psilia/run/heartbeat.json` | `core_node` inside Docker (1 Hz) | `status`, `stamp`, `ros_domain_id` |
| `~/.psilia/run/status.json` | `core_node` inside Docker (on demand) | heartbeat fields + `nodes`, `topics` |
| `{runtime_home}/log/` | ROS nodes inside Docker (`ROS_LOG_DIR`) | Per-node ROS logs |
| `{runtime_home}/ros/log/` | colcon on container startup | Build logs |

Note: `heartbeat.json` and `status.json` are ephemeral — cleared when the container starts.


## Interacting with the Runtime

There are two interfaces to the runtime, both available from laptop or phone:

**CLI** (`psilia runtime ...`) — direct terminal control:
- `psilia runtime start/stop/status` — lifecycle and status
- `psilia runtime attach` — live status view (1 Hz refresh)
- `psilia runtime update` — pull latest ROS package, rebuild Docker image

When called with a device name (e.g. `psilia runtime status my-jetson`), commands are forwarded over SSH and run on the remote device.

**Web UI** (browser → `http://<device>.local:8080`) — phone-friendly control panel. Served as static files by the base layer. Four pages:
- `/` — quick status overview
- `/runtime-status.html` — full runtime status (on-demand, via refresh button)
- `/runtime-test.html` — dev tool: ping/pong ROS connectivity test
- `/config.html` — displays `psilia.yaml`

### Two Network Connections

The web UI talks to two separate services on the Jetson:

**FastAPI REST (`api_port`, default 8080)** — base layer, always-on control plane:
- `GET /api/status` — full runtime status (triggers a ROS status request internally)
- `GET /api/config` — current `psilia.yaml` as JSON
- `GET /api/js/config.js` — JS snippet setting `window.PSILIA` with ports (loaded by web UI pages)
- `POST /api/spatial/start` / `POST /api/spatial/stop` — start/stop the Docker container

**rosbridge WebSocket (`rosbridge_port`, default 9090)** — live ROS communication, only available when the Docker container is running:
- Used by the web UI for live topic subscription (ping/pong test page)
- Used by the host Python code to publish to `/psilia/status_request` (triggers `core_node` to write `status.json`)
- Future: recording control (start/stop MCAP recorder via ROS topic)

The split of responsibilities is intentional: FastAPI owns lifecycle and config; rosbridge owns all live ROS interaction. As a soft guideline, the host avoids running `ros2` CLI tools directly — preferring the shared `run/` mount or rosbridge — but dropping into the container via `docker exec` and using `ros2` CLI is a valid escape hatch for debugging and dev.

<!-- ### Communication Matrix

The table below shows how each part of the system communicates with the others. Each cell describes the channel that the **row** uses to talk to the **column**. Parentheses indicate an indirect path. A `—` means no direct communication.

|  | **Browser** | **Terminal** | **Runtime** | **Docker** | **ROS** |
|---|---|---|---|---|---|
| **Browser** | — | — | REST :8080 | — | WS :9090 |
| **Terminal** | — | — | CLI | docker CLI | WS :9090, *(ros2 CLI)* |
| **Runtime** | REST :8080 | CLI | — | docker CLI, shared mount | shared mount, *(ros2 CLI)* |
| **Docker** | — | — | shared mount, ports | — | ros2 CLI |
| **ROS** | WS :9090 | — | shared mount | — | — |

- **REST :8080** — FastAPI server on the host; handles lifecycle (start/stop), status, and config.
- **WS :9090** — rosbridge WebSocket inside Docker; exposes live ROS topics to the outside world.
- **CLI** — the `psilia` command-line tool; runs locally on the laptop or forwarded over SSH.
- **docker CLI  (docker exec)** — used to start/stop the container or shell into it.
- **shared mount** — `~/.psilia/run/` mounted into the container; `core_node` writes `heartbeat.json` and `status.json`, Runtime reads them. The mount is bidirectional by nature.
- **ros2 CLI** — used by Docker's entrypoint to launch ROS (`ros2 launch`); also available as an escape hatch via `docker exec`. -->


## Network Setup

To reach the web UI and rosbridge, the phone (or laptop) and the Jetson must be on the same network. Psilia supports two modes, configured via `psilia runtime setup --network` and stored in `psilia.yaml` under `network:`. That command is the entrypoint to the network setup wizard — it detects available interfaces, prompts for mode and credentials, writes the config, and sets up NetworkManager for autoconnect.

**Mode 1 — Jetson AP** (dongle or built-in WiFi) · **Mode 2 — Jetson client** (connects to phone hotspot)

### Config (`psilia.yaml`)

```yaml
network:
  mode: ap          # ap | client
  ap:
    ssid: psilia-ap
    password: psilia1234
    interfaces:
      - name: wlx...        # detected during setup
        type: usb-dongle    # usb-dongle | built-in
        autostart: true     # nmcli autoconnect when interface is available (boot or plug-in)
        start_on_runtime: true  # brought up on `psilia runtime start`
  client:
    ssid: MyPhone
    password: secret
    autostart: true
    start_on_runtime: true
```

### Wizard Flow (`psilia runtime setup --network`)

1. Enumerate AP-capable interfaces; detect type via `wlx` prefix and `lsusb` cross-reference
2. If multiple, let the user pick one
3. Prompt for SSID, password, `autostart`, and `start_on_runtime` for the selected interface
4. Create an NM connection profile for that interface
5. Write config to `psilia.yaml`

For **Mode 2 (client)**, the wizard collects the phone hotspot SSID and password and creates a single NM client profile. `psilia runtime start` calls `nmcli connection up` if not already connected.

### Network Test (`/network-test.html`)

The web UI includes a network test page where the user can verify the connection is sufficient for camera streaming. The target is low-res image streaming (e.g. 320×240 @ 5 fps). The latency and throughput tests on the page should be calibrated against this requirement — pass/fail thresholds set accordingly.

When both a dongle and built-in WiFi are present, the Jetson can act as its own client: host the AP on one interface and connect to it with the other, then run the throughput test over that link. Traffic goes over the air so it's a real measurement, useful for validating an interface during setup before a phone is connected.


## V0 Features

- **WebUI:**
  - Camera stream, throttled and downsampled (configurable in RT config)
  - Spatial RT start/stop
    - Choose RT config to use on next start (options from `RT_HOME/config`)
  - Recording start/stop
    - choose which topics to record; defaults from RT config
    - easy way of nameing the recording `{device}_{session}_{counter}_{time}.mcap`; random default for sessions from a hidden configuration file (some cool names).

- **CLI**
  - `psilia pair [host] [pass]`
  - `psilia devices`
  - `psilia runtime init <device>`: initialize runtime home, dirs, entry to `psilia.yaml`, minimal setup so the runtime runs locally (dev-mode basically), but without sensors or hotspot
  - `psilia runtime start <device> [--config]`: start the runtime with an optional path to a runtime config file (DEFAULT: None or an empty dict I guess)
  - `psilia runtime stop <device>`
  - `psilia runtime status <device>`
  - `psilia runtime attach <device>`: live-view
  - `psilia runtime setup <device> [--network] [--camera]`: configures `psilia.yaml` and `runtime.yaml`

- CLI nice help visualization

### Future Versions
 - IMU and other sensors

## TODOs

- **[HIGH PRIORITY]** Revisit the network setup step (`_step_network`). Currently it looks for a USB WiFi dongle, but we should enumerate all interfaces that support AP mode and let the user choose. Show clearly which are USB dongles vs. built-in PCIe (e.g. via `wlx` prefix and `lsusb` cross-reference). Also handle hotspot autostart via NetworkManager during setup so the hotspot comes up on boot without manual intervention. Keep in mind that the connection needs to support live camera streaming to the web UI — low-res, low frame rate (e.g. 320x240 @ 5fps), but smooth enough to be useful for monitoring. Original full-res images are recorded separately; only downsampled versions are streamed. The hotspot interface choice and configuration should be validated against this bandwidth requirement.
- **[HIGH PRIORITY]** Camera support: scanning for connected cameras is roughly done (`hotplug.py`). Next step is a ROS node that reads from different camera types (USB, ZED, OAK-D, RealSense, etc.) and publishes on the stable `/psilia/image` interface. The node should be configurable (camera type and parameters from `runtime.yaml`) and handle device detection at startup.
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


## Notes & Ideas & Keep-in-minds

- `runtime.yaml` should eventually have a `launch_args:` section — a user-friendly place to configure ROS node parameters (camera type, resolution, etc.). Before launch, `start_spatial_layer()` reads this section and writes a properly formatted ROS params yaml to `~/.psilia/run/` which gets passed to the nodes via `parameters=[...]`. Currently the params file is written directly from auto-detected values.


- "runtime home" has a nice ring to it — `runtime.home_path` in the config reads naturally. Settled on `psilia-runtime-home` as the default directory name.
- The ROS workspace (`psilia_runtime`) is copied to the runtime home and mounted into the container at runtime — it is NOT baked into the Docker image. This keeps it visible and editable on the host without rebuilding the image. May revisit if we ever want a fully self-contained image.
