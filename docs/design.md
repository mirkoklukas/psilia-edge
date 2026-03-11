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
  ros/                      # colcon workspace, mounted into Docker at runtime
  data/                     # MCAP recordings
  log/                      # runtime logs
  runtime_config.yaml       # user-editable: what nodes to start, topics to record, etc.
```


📄 **Other files** the CLI touches:

`psilia pair` also adds a managed section to `~/.ssh/config` (bounded by `# >>> psilia-edge` / `# <<< psilia-edge` markers) with one entry per registered device. Nothing outside that section is touched.


## Key Config Files

**`~/.psilia/psilia.yaml`** is the single unified config file for the psilia tooling on any machine.
Its path is `psilia_edge.runtime.config.CONFIG/"psilia.yaml"` and stored additionally in `psilia_edge.runtime.config.CONFIG_PATH`.

It has two independent main sections (potentially more in the future) — either or both may be present depending on what the machine does:

```yaml
runtime:
  home_path: ~/psilia-runtime-home   # written by `psilia runtime setup`

hotspot:                             # written by `psilia runtime setup` (Jetson only)
  ssid: my-jetson-ap                 # NOTE: hardware may change between boots —
  password: psilia1234               # these values can be stale if dongle is swapped
  interface: wlx...                  # or camera is unplugged. live detection TBD.

camera:                              # written by `psilia runtime setup` (optional)
  type: null                         # e.g. zed2i, oak-d, realsense

registered_devices:                 # written by `psilia pair`
  my-jetson:
    host: my-jetson.local
    user: nvidia
    key: ~/.psilia/keys/my-jetson
```

A machine with `runtime.home_path` set has a local runtime installed. A machine with `registered_devices` set manages one or more remote runtimes. A laptop in dev mode can have both. This replaces the old role-detection heuristic of checking for a Jetson-specific file — the CLI now simply checks whether `runtime.home_path` is present.

**`{home_path}/runtime_config.yaml`** is user-editable and controls what nodes to start, which topics to record, and so on. Created with defaults by `psilia runtime setup`. Its path is stored in `psilia_edge.runtime.config.RUNTIME_CONFIG_PATH`.


## Environment and important config variables

|Python (`runtime.config`)| Env Variable | Default | Purpose |
|---|---|---|---|
| `CONFIG_DIR` | `PSILIA_DIR` | `~/.psilia` | Override the hidden psilia dir (e.g. `/ssd/.psilia` on Jetson)|
|`CONFIG_PATH`| - | - | Path to psilia config file `{CONFIG_DIR}/psilia.yaml`|
|`get_runtime_home()`| - | *(from psilia.yaml)* | Points to the runtime home directory |
|`RUN_DIR`| `PSILIA_RUN_DIR` | `~/.psilia/run` | Override the PID file directory (e.g. `/run/psilia` on Jetson) |
|`LOG_DOR`| `PSILIA_LOG_DIR` | `~/.psilia/log` | Override the log file directory (e.g. `/var/log/psilia` on Jetson) |
|- | `PSILIA_SSH_CONFIG_PATH`| `~/.ssh/config`| Managing ssh connection for registered devices |

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
Docker. On Jetson: `nmcli` / NetworkManager (hotspot), `systemd` (autostart).

**Python packages (`psilia-edge`):**
`typer`, `rich`, `pyyaml`, `paramiko`, `fastapi`, `uvicorn`, `psutil`, `mcap`, `numpy`.

**Docker image (`psilia/runtime:latest`):**
ROS 2 Humble, CUDA / JetPack-compatible base, camera drivers, MCAP recorder, Foxglove bridge, `colcon`.

**`psilia` inference library (inside Docker only):**
`numpy`, `opencv-python`, and optional inference deps (`torch`, `onnxruntime`) installed as extras.


## Docker Container Layout

The container mounts two directories from the host:

```
Host                          Container
~/.psilia/run/            →   /psilia/run/       status files written by core_node
{runtime_home}/ros/       →   /opt/psilia/ros/   colcon workspace (built on startup)
```

`/psilia/run/` is the shared state channel between the ROS layer and the host:
- `heartbeat.json` — written every 1 Hz tick by `core_node`: `status`, `stamp`, `ros_domain_id`
- `status.json` — written on demand when `core_node` receives a `/psilia/status_request` message: heartbeat fields + `nodes`, `topics`

The colcon workspace layout inside the container mirrors the host:
```
/opt/psilia/ros/
  src/psilia_runtime/     # mounted from host — editable without rebuilding image
  build/                  # created by colcon on container startup
  install/
  log/
```

The entrypoint runs `colcon build --packages-select psilia_runtime` on every startup (incremental — fast after first build), sources the workspace, then launches `ros2 launch psilia_runtime default.launch.py`.

To clear the build cache (e.g. after `setup.py` changes), `psilia runtime update` spins up a temporary container to `rm -rf` the build dirs — no sudo needed on the host.


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

**FastAPI REST (port 8080)** — base layer, always-on control plane:
- `GET /api/status` — full runtime status (triggers a ROS status request internally)
- `GET /api/config` — current `psilia.yaml` as JSON
- `POST /api/spatial/start` / `POST /api/spatial/stop` — start/stop the Docker container

**rosbridge WebSocket (port 9090)** — live ROS communication, only available when the Docker container is running:
- Used by the web UI for live topic subscription (ping/pong test page)
- Used by the host Python code to publish to `/psilia/status_request` (triggers `core_node` to write `status.json`)
- Future: recording control (start/stop MCAP recorder via ROS topic)

The split of responsibilities is intentional: FastAPI owns lifecycle and config; rosbridge owns all live ROS interaction. The host never runs `ros2` CLI tools directly — it either reads files from the shared `run/` mount or publishes via rosbridge.


## Notes & Ideas

- "runtime home" has a nice ring to it — `runtime.home_path` in the config reads naturally. Settled on `psilia-runtime-home` as the default directory name.
