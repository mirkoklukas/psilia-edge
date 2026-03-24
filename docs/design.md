<img src="../assets/psilia-logo-transparent-bg.svg" width="350" style="margin-top: 1em; margin-bottom: 1em;">

> **Summary:** Guiding principles, system architecture, and runtime operations. Covers the two roles (Jetson vs. laptop), filesystem layout, config files, the two-layer runtime (base + spatial), code structure, Docker container layout, logging reference, and how to interact with the runtime via CLI and Web UI.

# Psilia Edge — Spatial Runtime for Embodied AI.

## Guiding Principles

- **Our goal is to be the first thing installed on Jetson. The Docker Desktop for spatial perception.**
- The easiest way to get spatial perception running on Jetson
- Runtime-first, not camera-first. Experience is hardware agnostic.
- Simpler, open, and hackable. "Edge-native perception for builders and developers."
- Avoid "cheap alternative to StereoLabs" framing. That's a trap. Zed is camera-first, we're runtime first. Better positioning:
    **NOT** "Low-cost ZED replacement". **INSTEAD** "Edge-native perception for builders." Not just *cheaper*, it is **simpler and more hackable**.
- "It kind of feels like ZED but easier." That's fine. But internally you must think: "We are not replacing ZED. We are replacing ROS setup pain and remove all friction to enable a quick prototyping cycle."


# Architecture

## Two Roles

The same `psilia-edge` package is installed on both your laptop and Jetson device, but each takes on a distinct role:

**(Spatial) Runtime host** (Jetson) — runs the spatial perception stack. Hosts the base layer daemon, the ROS layer in Docker, and serves the Control UI. Anything you called `psilia runimte init/setup` on, which basically means it has a "runtime home".

**Device/Data manager** (Laptop) — manages one or more runtime hosts. Handles pairing, bootstrapping over SSH, and data operations (pull, sync, cloud push). Keeps a registry of registered devices in `~/.psilia/psilia.yaml`.

The role distinction is intentional and usually distinct for a given machine — a Jetson is usually  a runtime host, a laptop is usually a device/data manager. However, a single machine *can* play both roles, but that is used mainly during development.


## Filesystem Layout

The key mental model is as follows: The user clones and install the repository at a location of their choice (repo directory). Once installed the CLI is up. The CLI has its own state storage (config directory) under `~/.psilia/`. The runtime is the "product". A set up runtime has it's own additional user-facing and user-specified folder (runtime home), e.g. `~/psilia-runtime-home/`.

📁 **Repo Directory** `~/psilia-edge/` (cloned by the user).

The repo dir is wherever the user cloned it. Once `pip install -e .` is run, the CLI is available and the repo path can be looked up at runtime. It is separate from the runtime dir. The repo is the "source code" of the CLI. Not the product.

📁 **Web Directory** `~/psilia-edge/web`.

The `web/` directory lives in the repo and is served directly from there (`{repo_dir}/web/`). This works cleanly for v0 because the repo is always present on the machine. When psilia-edge is eventually published to PyPI and installed non-editably, the web assets should move to package data (via `importlib.resources`) so they are included in the distribution.

📁 **Config Directory** `~/.psilia/` (hidden, CLI-internal).

The user never needs to know this exists. It stores the CLI's own state: a pointer to where the runtime lives, SSH keys for managed devices, and the device registry, and others. Fixed path, overridable via the environment variable `PSILIA_DIR` for testing.

```
~/.psilia/
  psilia.yaml               # unified config: runtime home path, device registry
  run/psilia-edge.pid       # daemon PID file
  log/psilia-edge.log       # daemon log
  keys/<device-name>        # SSH private key per registered device
```

📁 **Runtime Home** `~/psilia-runtime-home/` (user-facing, the product).

This is where the runtime lives. Intentionally visible and not hidden — the user is expected to look in here, edit config files, inspect data. Contains the ROS workspace, recordings, logs, and user-editable config. The path is chosen during `psilia runtime init/setup` and can be anywhere; the defaults are `~/psilia-runtime-home` on laptop and `/ssd/psilia-runtime-home` on Jetson.

```
psilia-runtime-home/
  ros/            # colcon workspace, mounted into Docker at runtime
  data/           # MCAP recordings
  log/            # runtime logs
  conf/           # Default place to put alternative runtime configs
  runtime.yaml    # user-editable: what nodes to start, topics to record, etc.
```

📁 **Fetched/Pulled Data Dir (Manager Only)** (no default — set on first pull).

Where the recorded data pulled from a Jetson (Runtime Host) lands on the laptop (Data Manager) side. There is no default path. `data.pull_to` is prompted lazily on the first `psilia data pull` if `--to` is not given, and then saved to `psilia.yaml`. It is **not** set during `psilia pair`. Once set, the entry in `psilia.yaml` looks like:
```yaml
data:
  pull_to: ~/psilia-fetched/
```

We could make `pull_to` a field on each paired device in `psilia.yaml` (per-device override) rather than a single global setting.

📄 **Other files** the CLI touches:

`psilia pair` also adds a managed section to `~/.ssh/config` (bounded by `# >>> psilia-edge` / `# <<< psilia-edge` markers) with one entry per registered device. Nothing outside that section is touched. (actually sync that with data in psilia.yaml)


## Key Config Files and Variables

### Main Config: `~/.psilia/psilia.yaml`

`~/.psilia/psilia.yaml` is the single unified config file for the psilia tooling on any machine.
Its path is `psilia_edge.runtime.config.CONFIG_DIR/"psilia.yaml"`, also available as `psilia_edge.runtime.config.CONFIG_PATH`.

It can be split into two main parts associated with the two roles above (potentially more in the future) — either or both may be present depending on what the machine does:
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

# written by `psilia runtime setup --network` (Jetson only)
network:
  mode: ap                 # field connectivity: ap | client
  ap:
    ssid: my-jetson-ap
    password: psilia1234
    interfaces:
      - name: wlx...
        type: usb-dongle
        autostart: true
        start_on_runtime: true
  client:
    ssid: MyPhone
    password: secret
    autostart: true
    start_on_runtime: true
  home:
    ssid: my-home-wifi     # known WiFi — base layer checks if in range and
    password: secret       # indicates connectivity in the Web UI.
    # Future: trigger cloud upload when connected.
    # Future: other connection types (ethernet) may be relevant here too.

# written by `psilia runtime setup` (optional)
camera:
  type: null               # e.g. zed2i, oak-d, realsense

#|
#|  Role 2: Device and Data Management
#|  (typically Laptop)
#|
# written by `psilia pair`
data:
  pull_to: ~/psilia-fetched/
# written by `psilia pair`
registered_devices:
  my-jetson:
    host: my-jetson.local
    user: nvidia
    key: ~/.psilia/keys/my-jetson
```

A machine with `runtime.home_path` set has a local runtime installed. A machine with `registered_devices` set manages one or more remote runtimes. A laptop in dev mode can have both. This replaces the old role-detection heuristic of checking for a Jetson-specific file — the CLI now simply checks whether `runtime.home_path` is present.


### Runtime Config: `psilia-runtime-home/runtime.yaml`

**`{home_path}/runtime.yaml`** is user-editable and controls what nodes to start, which topics to record, and so on. Created with defaults by `psilia runtime init/setup`. Its path is stored in `psilia.yaml`.
Everything runtime-specifig configurable information should go in here.

The default/initial runtime config (`runtime.default.yaml`):
```yaml
name: My Runtime Config
ros:
  launch: default.launch.py
  recording:
    topics:
      - /psilia/interface
      - /psilia/heartbeat
```


### Environment Vars

The env vars exist primarily for testing and CI.

| Env Variable | Overwrites Python Var | Default | Purpose |
|-|-|-|-|
| `PSILIA_DIR` | `CONFIG_DIR` | `~/.psilia` |
Override the hidden psilia dir (e.g. `/ssd/.psilia` on Jetson)|
| `PSILIA_SSH_CONFIG_PATH`| `_SSH_CONFIG_PATH`|`~/.ssh/config`|
Managing ssh connection for registered devices |

### Variable names and getters

| Name | Python  (`runtime.config`) | Descr |
|-|-|-|
| Config/Psilia dir | `CONFIG_DIR` |  `~/.psilia` |
| Psilia config path | `CONFIG_PATH` |  `~/.psilia/psilia.yaml` |
| Psilia config | `read_config()` |  Returns the config |
| Repo dir | `get_repo_dir()` | `~/psilia-edge`|
| Runtime home | `get_runtime_home()` | `~/runtime-home`|
| ... | ... | ... |


## Two Runtime Layers

The runtime consists of two layers with distinct lifecycles:

**Base layer** — always-on, starts and stops with `psilia runtime start/stop --base-only`:
- FastAPI webserver serving the Web UI and REST API
- Docker container (started with the base layer, kept running)

**Spatial layer** — on-demand, fast to start and stop via `psilia runtime start/stop --spatial-only`:
- ROS nodes launched inside the already-running container (e.g. camera, depth, pose)
- Stopping the spatial layer sends a shutdown signal to the ROS launch process inside the container — fast, no container teardown
- Can be restarted with a different `runtime.yaml` config without touching the container

The container itself is only torn down when the base layer stops. The slow `docker stop` timeout is therefore only paid once — at full runtime shutdown, where it's acceptable. Restarting just the ROS nodes is quick.

`psilia runtime update` is the only operation that rebuilds the Docker image or clears the colcon build cache. It runs `colcon build` on the next container start (incremental, fast after first build).


## Code Structure

Three tiers, each with distinct responsibilities:

**CLI** (`cli.py`) — entry point, user interaction. Controls flow based on CLI options, calls into service modules or wizards, renders output. No implementation details — no knowledge of docker, files, daemons.

**Wizards** (`setup.py`, `pair.py`) — setup flows. The only tier besides CLI where `ui.*` and process output are allowed.
- **step** — prompt (optional) → act (including writing to config or disk) → `ui.ok` / `ui.fail` → return natural value (whatever the next step needs)
- **wizard** — runs steps, builds and prints summary (`ui.print_tree`), prints hardcoded next action hint

For long-running steps (e.g. `docker build`), raw process output scrolls by via `run_streamed` instead of a spinner — still followed by `ui.ok` / `ui.fail`.

**Service modules** (`core.py`, `daemon.py`, `docker.py`, `status.py`, `config.py`, `hotplug.py`, `server.py`) — single-concern, no UI. Return dicts, raise on failure. `core.py` is the central service: runtime lifecycle and role detection. Others are single-concern helpers.

### Output channels

- **`ui.*`** — user-facing formatted output. CLI and wizards only.
- **process output** (`run_streamed`) — raw subprocess stdout piped to terminal. Long-running transparent operations only (e.g. `docker build`, `colcon build`). CLI and wizards only.
- **`logging`** — developer-facing traces. Anywhere via `logger = logging.getLogger(__name__)`. Configured once in `psilia_edge/__init__.py` via `RichHandler`.


### `runtime/` module layout

(MAKE SURE THIS IS UP TO DATE)

| Module | Tier | Role |
|---|---|---|
| `cli.py` | CLI | Flow control, option handling, output rendering |
| `setup.py` | Wizard | Interactive runtime setup steps |
| `core.py` | Service | Runtime lifecycle, role detection |
| `daemon.py` | Service | Process lifecycle (PID file, start/stop uvicorn) |
| `docker.py` | Service | Container operations |
| `status.py` | Service | State reads, no side effects |
| `config.py` | Service | Path constants and config access |
| `hotplug.py` | Service | Camera/device detection |
| `server.py` | Service | FastAPI app definition |


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


# Operations

## Logging & Runtime Files

(MAKE SURE THIS IS UP TO DATE)

Where to look when something goes wrong at each layer:

| File | Written by | Contents |
|---|---|---|
| `~/.psilia/run/psilia-edge.pid` | `start_daemon()` in `daemon.py` | PID of the running FastAPI/uvicorn process |
| `~/.psilia/log/psilia-edge.log` | uvicorn (stdout/stderr redirected by `start_daemon()`) | Base layer startup, request logs, errors |
| `~/.psilia/run/heartbeat.json` | `core_node` inside Docker (1 Hz) | `status`, `stamp`, `ros_domain_id` |
| `~/.psilia/run/status.json` | `core_node` inside Docker (on demand) | heartbeat fields + `nodes`, `topics` |
| `{runtime_home}/log/ros.log` | `launch_ros.sh` via `docker exec -d` | ROS launch output (stdout+stderr); truncated on each spatial layer start. View with `psilia runtime logs [-f]` |
| `{runtime_home}/log/` | ROS nodes inside Docker (`ROS_LOG_DIR`) | Per-node ROS logs |
| `{runtime_home}/ros/log/` | colcon on container startup | Build logs |

Note: `heartbeat.json` and `status.json` are ephemeral — cleared when the container starts.
Note: `ros.log` is truncated on each spatial layer start — only contains the current session.

To view ROS launch output:
```bash
psilia runtime logs              # last 50 lines
psilia runtime logs --tail 100   # last 100 lines
psilia runtime logs -f           # follow live
psilia runtime logs -f -d borne  # follow live on a registered device
```


## Interacting with the Runtime

There are two interfaces to the runtime, both available from laptop or phone: the CLI and the Web UI.

### CLI

`psilia runtime ...` — direct terminal control:
- `psilia runtime start/stop` — lifecycle
- `psilia runtime attach` — live status view (1 Hz refresh); the primary way to monitor the runtime
- `psilia runtime update` — pull latest ROS package, rebuild Docker image

Dev tools:
- `psilia runtime status` — one-shot status snapshot (debugging)

When `--device` / `-d` is given (e.g. `psilia runtime status --device my-jetson`), commands are forwarded over SSH and run on the remote device.

#### CLI vs API commands

Commands fall into two categories:

**CLI commands** — human-facing, formatted output (Rich trees, colors, headers). Designed to be read in a terminal. Example: `psilia runtime status`.

**API commands** — machine-readable, plain output. Designed to be consumed by scripts, `$()` substitution, or other programs. Example: `psilia runtime config home-dir`. These print one value per line with no decoration.

CLI commands can switch into API mode with `--json`, which suppresses all human output and prints a single JSON object to stdout. Exit code signals success or failure.

The distinction is intentional — API commands are stable contracts, CLI output is allowed to change for readability.

### Web UI

Browser → `http://<device>.local:8080` — phone-friendly control panel. Served as static files by the base layer. Pages:
- `/` — landing page, quick status overview
- `/runtime-status.html` — full runtime status (on-demand, via refresh button)
- `/recording.html` — start/stop recording, topic selection, file naming
- `/config.html` — displays `psilia.yaml`
- Dev tools (not user-facing in v0):
  - `/runtime-test.html` — ping/pong ROS connectivity test
  - `/network-test.html` — bandwidth and latency test for camera streaming

### Network Connections

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
