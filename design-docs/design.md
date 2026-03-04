# Psilia Edge — Structure & Experience

## Overview

Psilia Edge is a spatial perception runtime for edge devices. It sits one level above raw sensors and one level below autonomy stacks.

Our goal is to be the first thing installed on Jetson. Plug in a stereo camera, run one command, and get reliable depth, pose, and spatial outputs as a stable interface in under 5 minutes. Hardware-agnostic, open format, no ROS wrangling required.

It is not a camera product. It is the **Docker Desktop for spatial perception**. Open and hackable by default. Everything is accessible if you want to dig in, but you never have to.

---

## The Three-Component Architecture

Psilia Edge consists of three parts:

1. **Spatial Runtime** — runs on the Jetson, exposes stable perception outputs
2. **Control UI + CLI** — manage the runtime, record, sync data
3. **Dev API** — Python interface for exploring recorded data offline

### Spatial Runtime — Two Layers

The Spatial Runtime has two internal layers:

**Base layer** — daemon + web server, running directly on the Jetson host. Always-on control plane. Manages the ROS layer lifecycle, serves the Control UI, and exposes an API for the CLI and web UI. Implemented as a single FastAPI process.

**ROS layer** — ROS nodes running inside the Docker container. Started on demand by the base layer. This is the actual perception pipeline: camera driver, depth, pose, MCAP recorder, Foxglove bridge.

Boot sequence (manual): Jetson starts → base layer starts → user runs `psilia spatial start` → Docker container starts → ROS nodes come up → topics publishing.

Boot sequence (autostart): Jetson starts → systemd runs `psilia start` → both layers come up automatically. This is the default field setup.

The layered `psilia base` / `psilia spatial` commands exist for development, testing, and debugging — not because users typically operate the layers independently.

### CLI commands

```bash
psilia start           # start base layer + ROS layer
psilia stop            # stop base layer + ROS layer

psilia base start      # start base layer only
psilia base stop       # stop base layer only

psilia spatial start   # start ROS layer only (requires base layer running)
psilia spatial stop    # stop ROS layer only

psilia autostart on    # enable base layer autostart on boot
psilia autostart off   # disable base layer autostart on boot
```

---

## User Modes

There are four distinct modes a user operates in. Each has different UX requirements and should be designed for independently.

### 1. Init (one-time)
Get the Jetson, laptop, and camera talking to each other. Runs once. Never touched again.

### 2. Field
Running, monitoring, and recording in the field. Phone in hand, not laptop.

### 3. Sync
Pull recorded data off the Jetson to laptop and optionally to cloud.

### 4. Explore
Load recordings into a notebook, query topics, inspect timing, prototype algorithms.

---

## Mode 1: Init

**Entry point:** `psilia init` on the laptop. A single guided wizard. No monitor on the Jetson required.

If the Jetson is already reachable, skip discovery and go straight to bootstrap:
```bash
psilia init --host <ip-or-hostname>
```

> **Note:** This flow assumes a fresh Jetson with no prior setup. If the Jetson is already reachable over SSH (known IP or hostname), steps 1 and 2 can be skipped — the wizard should detect this and jump straight to the bootstrap. The Jetson's IP and hostname are saved to `~/.psilia/config.yaml` at the end of init for all future connections.

### Prerequisites
- Jetson flashed with JetPack (standard SD card / eMMC flash from laptop)
- Ethernet cable between Jetson and laptop/router

### Flow

**Step 1 — Prerequisites check**
The wizard displays a checklist of what is expected and asks for confirmation before proceeding. No automation — just sets expectations.

```
Before we begin, make sure you have:

  ✓ Jetson flashed with JetPack
  ✓ Ethernet cable connected between Jetson and your laptop/router
  ✓ Jetson powered on

Ready to continue? [y/N]
```

**Step 2 — Connect and discover**
Power on Jetson with ethernet connected. Psilia discovers it by inspecting the ARP table on the laptop's ethernet interface — no manual IP required. If exactly one host is found, it proceeds automatically. If multiple are found, the user is prompted to pick one.

Once connected, init sets the Jetson's hostname to `psilia-jetson` (configurable). All subsequent connections use `psilia-jetson.local` via mDNS.

**Step 3 — Remote bootstrap (over SSH)**
Once discovered, `psilia init` SSHs into the Jetson and runs the full bootstrap remotely:

1. **Generate SSH keypair** — dedicated keypair for Psilia, does not touch existing SSH config.
2. **Network setup:**
   - **Hotspot** — detect USB wifi dongle (preferred, `wlx` prefix). Fall back to built-in wifi with a warning. User prompted for SSID and password (defaults provided).
   - **WiFi connection** — scan visible networks, user selects SSID and enters password. Persisted as autoconnect profile.
3. **Set device name** — wizard prompts for a name (default: `psilia-jetson`). Sets the Jetson hostname to `<name>`, all subsequent connections use `<name>.local` via mDNS.
4. **SSH config** — optionally add an entry to `~/.ssh/config` on the laptop for easy access (`ssh <name>`) over ethernet, wifi, or hotspot.
5. **Create `/opt/psilia/` directory structure** on the Jetson.
6. **Detect and set up SSD** — wizard detects available drives, confirms mount point (default: `/ssd/`), configures `/ssd/psilia-data/` as data directory. Explicit confirmation before any formatting. Falls back to eMMC with a storage warning.
7. **Install Docker.**
8. **Clone `psilia-edge`** and `pip install -e .`. In future, `pip install psilia-edge` or a curl installer.
9. **Copy `psilia_runtime`** ROS package from the cloned repo to `/opt/psilia/ros/psilia_runtime/`.
10. **Build the Docker image** on the Jetson from `ros/Dockerfile` in the cloned repo. (In future: pull `psilia/runtime:latest` from a registry.)
11. **Detect connected camera** (optional — can be skipped and configured later with `psilia config camera`).
12. **Set up systemd service** — wizard asks whether to enable autostart on boot.

**Step 4 — Write local config**
On completion, writes `~/.psilia/config.yaml` on the laptop:

```yaml
devices:
  <name>:                                   # device name chosen during init
    host: <name>.local
    user: nvidia
    key: ~/.psilia/keys/<name>
    data_path: /ssd/psilia-data/recordings  # configured during init

defaults:
  pull_to: ~/psilia-data
```

**Done.** The user never touches the Jetson directly. One command, linear flow.

### What Init Does NOT Do
- Does not ask the user to choose a Docker image or configure ROS — Psilia owns that by default
- Does not touch existing SSH keys or network config beyond what is needed
- Does not set up cloud sync — configured separately if needed
- Does not require a camera — camera setup is optional during init. The mock node runs in its place, giving a fully working system to explore without hardware.

---

## File Layout

### Laptop

```
~/.psilia/
  config.yaml           # device registry, pull_to path, cloud target
  keys/
    psilia_jetson       # dedicated SSH key, generated during init

~/psilia-data/          # local recording storage (pulled from Jetson)
  recordings/
```

### Jetson

```
/opt/psilia/            # system config and ROS workspace (eMMC/SD)
  config.yaml           # Jetson-side config (storage mount point, runtime image, autostart)
  ros/
    psilia_runtime/     # default ROS package — visible and editable
      package.xml
      setup.py
      launch/
        default.launch.py
      config/
        params.yaml

/ssd/psilia-data/       # data storage (SSD, mount point configured during init)
  recordings/
    device_session_001_20250601T120000.mcap
    ...
```

---

## Docker Image & ROS Workspace

### The Image

Psilia ships one image: `psilia/runtime:latest`

It contains:
- ROS 2 Humble
- CUDA / JetPack compatible dependencies
- All node dependencies: camera driver, depth estimation, pose estimation, MCAP recorder, Foxglove bridge

The image is purely the environment — ROS, CUDA, and dependencies. The `psilia_runtime` ROS package lives on the Jetson host and is mounted into the container at runtime. The image is fully open. Users can inspect it, derive from it, or replace it entirely.

> **Note:** In a future version we may bake `psilia_runtime` into the image for a simpler, more reproducible deployment. For now the mounted workspace is simpler and more flexible during development.

### The ROS Workspace

`psilia_runtime` lives on the Jetson host at `/opt/psilia/ros/` and is mounted into the container at runtime:

```bash
docker run \
  -v /opt/psilia/ros:/opt/psilia/ros \
  --network host \
  psilia/runtime:latest
```

Build artifacts are also stored on the host, so incremental rebuilds are fast. At startup the container:
1. Builds `/opt/psilia/ros/` with `colcon build` (incremental — fast after first build)
2. Sources the workspace
3. Runs `ros2 launch psilia_runtime default.launch.py`

Topic remapping from hardware-specific names to the stable `/psilia/*` interface is done in the launch file.

### Customisation

Edit the launch file or nodes directly on the Jetson host, then restart the container to pick up changes:

```bash
vim /opt/psilia/ros/psilia_runtime/launch/default.launch.py
psilia spatial restart
```

To swap the Docker image entirely, override in the Jetson-side config:

```yaml
runtime:
  image: my-org/my-psilia-image:latest
```

### Mock Node

Psilia ships a mock node that publishes synthetic data on the standard `/psilia/*` topics. It runs by default in the launch file and can always be used to test the full pipeline — init, Control UI, recording, sync, and Dev API — without a camera or inference.

```python
# default.launch.py
launch_description = [
    mock_node,          # synthetic data on /psilia/* — always available
    # depth_node,       # uncomment when camera + inference configured
    # pose_node,        # uncomment when camera + inference configured
    mcap_recorder,
    rosbridge_server,   # WebSocket bridge for Control UI and recording control
    # foxglove_bridge,  # optional — useful for debugging with Foxglove Studio
]
```

Real nodes are added to the launch file as the rig is configured. Camera and inference nodes depend on `psilia` (the inference library) installed inside the Docker image, but the runtime itself has no such dependency.

### User's Own ROS Nodes

Psilia's container is Psilia's. Users run their own nodes in a separate container (or on the host) on the same ROS domain ID. They communicate with Psilia naturally over ROS 2 by consuming `/psilia/*` topics.

```bash
# Run user container on same network, same ROS domain
docker run --network host -e ROS_DOMAIN_ID=0 my-robot/my-nodes
```

No Psilia-specific integration needed. The stable topic interface is the contract.

---

## Mode 2: Field

If autostart is enabled the base layer is already running on arrival in the field. If not, start everything manually from the laptop before heading out:

```bash
psilia start          # start base layer + ROS layer
psilia stop           # stop base layer + ROS layer
```

The user does not need to SSH into the Jetson for any of this.

**Entry point:** Browser on phone or laptop → Control UI served from Jetson over hotspot.

### Control UI
Minimal by design. Covers only what is needed in the field:

- **Runtime status** — is the runtime healthy, which topics are publishing, at what rate
- **Start / Stop recording** — name the file, pick topics, one tap to record
- **Active recording status** — duration, file size, confirm topics are being captured
- **Stop recording** — explicit confirmation, file is flushed and closed cleanly

The Control UI is a single-page app served by the base layer. It makes two connections:

- **FastAPI (base layer)** — lifecycle control: start/stop the Spatial Runtime (Docker container), system status
- **rosbridge (ROS layer)** — everything ROS: live topic monitoring, start/stop recording via ROS messages to the recording node

Recording is triggered by publishing ROS messages to the recording node — no base layer involvement. The monitoring view is fully customizable on the frontend.

> **Note:** The split of responsibilities between the base layer and rosbridge may evolve. For now, the base layer owns lifecycle and rosbridge owns all ROS interaction.

### What the Control UI Does NOT Do
- Does not manage arbitrary ROS processes
- Does not expose raw ROS tooling
- Does not handle data sync (that is a post-field, laptop operation)

### Runtime Interface
The Psilia runtime exposes a small, stable set of topics regardless of which camera or algorithm is underneath:

```
/psilia/image
/psilia/depth
/psilia/pose
```

Algorithms for depth and pose estimation are swappable via the launch file without changing the interface or any downstream code.

### Recording
Recorded as MCAP files on the SSD, with a consistent naming convention:

```
{device}_{session}_{counter}_{timestamp}.mcap
```

---

## Mode 3: Sync

Data sync is a laptop-side CLI operation, run after returning from the field.

### Commands

```bash
psilia pull          # Jetson → Laptop (rsync over SSH)
psilia push          # Laptop → Cloud (rsync over SSH)
psilia sync          # Both, in sequence
```

### Pull
Rsync's completed MCAP recordings from the Jetson's `data_path` to the local `pull_to` directory. Resumable, safe to run multiple times.

### Push
Rsync's local `~/psilia-data` to a configured SSH target. No vendor lock-in — user owns the infrastructure.

Cloud target configured in `~/.psilia/config.yaml` on the laptop:

```yaml
cloud:
  host: user@my-server.com
  key: ~/.psilia/keys/psilia_cloud
  data_path: /mnt/storage/psilia
```

### Multi-device
If multiple Jetsons are registered, target explicitly:

```bash
psilia pull my-jetson
psilia pull field-rig-2
```

---

## Mode 4: Explore

Pure Python. No ROS. No runtime required.

```bash
pip install psilia
```

### Dev API

> **Draft** — the API design below is a placeholder to illustrate intent. The actual interface will be designed properly before implementation.

A lightweight MCAP reader that returns typed arrays with minimal ceremony.

```python
from psilia import Recording

rec = Recording("/data/session/device_session_001_20250601T120000.mcap")

# Access topics as numpy arrays
poses = rec["/psilia/pose"]
depths = rec["/psilia/depth"]

# Query by time
pose_at_t = poses.closest(t=5.2)
depth_slice = depths.t(5.0, 6.0)

# Inspect timing
rec.stats("/psilia/pose")
# → { rate: 30.1 hz, lag_mean: 4.2ms, lag_max: 11ms, dropped: 0 }
```

### What the Dev API Covers
- Read any topic from an MCAP file as numpy arrays or typed iterators
- Query by timestamp or time interval
- Sync multiple topics over time
- Inspect message timing, publishing rates, and lag
- Slice recordings for algorithm testing and replay

---

## Component Summary

| Component | Runs On | Entry Point | Scope |
|---|---|---|---|
| Spatial Runtime — base layer | Jetson host | systemd / `psilia base start` | Control plane, web UI, API |
| Spatial Runtime — ROS layer | Jetson (Docker) | `psilia spatial start` | Perception outputs, recording |
| Control UI | Jetson (served by base layer) | Browser (phone/laptop) | Monitor, record |
| CLI (`psilia`) | Laptop | Terminal | Init, start/stop, pull, push, sync |
| Dev API | Laptop / Cloud | Python / notebook | Explore recorded data |

---

## What Psilia Edge Is Not (v0)

- Not a general ROS process manager
- Not a camera product or SDK
- Not a cloud storage provider
- Not a calibration tool (known gap — to be addressed)
- The spatial intelligence layer (`/psilia/ground_plane`, `/psilia/obstacle_map`) is explicitly out of scope for v0

---

## Repositories

Two separate repos with distinct audiences and release cycles.

### `psilia` (inference library)

Pure Python, no ROS, no edge-specific concerns. Useful standalone — depth and pose algorithms usable independently of the edge tooling.

```
psilia/
  psilia/
    depth/                # depth estimation algorithms
    pose/                 # pose estimation algorithms
  pyproject.toml          # package: psilia
```

### `psilia-edge`

Everything needed to run, manage, and interact with the Psilia runtime on a Jetson. One repo, one install, one release.

`psilia-edge` is installed in two places:
- **Laptop** — CLI and Dev API
- **Jetson host** — CLI, daemon, and web server (installed during `psilia init`)

```
psilia-edge/
  src/
    psilia_edge/
      cli/                # psilia init, start, stop, pull, push, sync, ...
      runtime/            # base layer — FastAPI process managing Docker lifecycle
      mcap/               # MCAP reader, Dev API
  web/                    # Control UI frontend
    src/
    package.json
    dist/                 # built output, served by runtime/
  ros/                    # ROS package + Dockerfile — not pip installable
    psilia_runtime/       # copied to /opt/psilia/ros/ on Jetson during init
      nodes/
        mock_node.py      # synthetic /psilia/* publisher — no deps
        depth_node.py     # wraps psilia.depth
        pose_node.py      # wraps psilia.pose
      launch/
        default.launch.py
      config/
        params.yaml
    Dockerfile            # builds psilia/runtime:latest
  pyproject.toml          # package: psilia-edge
  docs/
```

---

## Package Dependencies

```
psilia        →  (none)
psilia-edge   →  (none — psilia is not a dependency)

runtime (Docker image):
  depth_node, pose_node  →  psilia  (installed inside image via pip)
  mock_node              →  (none)
```

The daemon and web server run directly on the Jetson host as part of `psilia-edge`. The Docker container is purely ROS nodes — no orchestration code inside it.

### Where psilia-edge Runs

| Component | Laptop | Jetson host | Docker container |
|---|---|---|---|
| CLI | ✓ | ✓ | — |
| Dev API | ✓ | — | — |
| Daemon | — | ✓ | — |
| Web server | — | ✓ | — |
| Runtime ROS nodes | — | — | ✓ |

### External Dependencies

**`psilia-edge`** (kept minimal):
- `mcap` — MCAP file reader
- `numpy` — typed arrays
- `typer` — CLI
- `paramiko` or wraps `ssh`/`rsync` — device communication
- `rich` — terminal UI for the init wizard
- `fastapi` + `uvicorn` — web server (Jetson host only)

**`psilia`** (pure Python):
- `numpy`
- `opencv-python`
- Inference-specific deps (e.g. `torch`, `onnxruntime`) — optional, declared as extras

**`runtime` Docker image**:
- ROS 2 Humble
- CUDA / JetPack compatible base
- ROS node deps: camera drivers, MCAP recorder, Foxglove bridge
