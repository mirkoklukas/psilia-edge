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

### Prerequisites
- Jetson flashed with JetPack (standard SD card / eMMC flash from laptop)
- Ethernet cable between Jetson and laptop/router

### Flow

**Step 1 — Flash JetPack**
The wizard provides instructions and waits for confirmation. Standard JetPack image, nothing custom required.

**Step 2 — Connect and discover**
Power on Jetson with ethernet connected. Psilia auto-discovers it via mDNS (`psilia-jetson.local`). No manual IP hunting.

**Step 3 — Remote bootstrap (over SSH)**
Once discovered, `psilia init` SSHs into the Jetson and runs the full bootstrap remotely:

- Generate a dedicated SSH keypair for Psilia (does not touch existing SSH config)
- Install Docker
- Detect and set up SSD — the wizard detects available drives, confirms the mount point with the user (defaulting to whatever is already mounted, e.g. `/ssd/`), and configures `/ssd/psilia-data/` as the data directory. Adds fstab entry if not already mounted. Requires explicit user confirmation before any formatting. Falls back to eMMC with a storage warning if no SSD detected.
- Create `/opt/psilia/` directory structure on the Jetson
- Pull `psilia/runtime:latest` Docker image
- Copy the default `psilia_runtime` ROS package source from the image to `/opt/psilia/ros/psilia_runtime/`
- Build the overlay ROS workspace
- Detect connected camera (optional — can be skipped and configured later with `psilia config camera`)
- Configure hotspot (for field use — phone and laptop connect to Jetson)
- Set up systemd service. The wizard asks whether to enable autostart on boot — if yes, the runtime starts automatically on boot; if no, the user starts it manually with `psilia start` before going into the field.

**Step 4 — Write local config**
On completion, writes `~/.psilia/config.yaml` on the laptop:

```yaml
devices:
  my-jetson:
    host: psilia-jetson.local
    user: nvidia
    key: ~/.psilia/keys/psilia_jetson
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
- `psilia_runtime` pre-built as the base ROS workspace

The image is fully open. Users can inspect it, derive from it, or replace it entirely.

### The ROS Workspace

The launch file and ROS configuration live **outside** the container on the Jetson host at `/opt/psilia/ros/`. This directory is mounted into the container at runtime as an overlay workspace on top of the pre-built base.

At startup the container:
1. Sources the base workspace (pre-built inside the image)
2. Builds `/opt/psilia/ros/` as an overlay with `colcon build`
3. Sources the overlay
4. Runs `ros2 launch psilia_runtime default.launch.py`

Topic remapping from hardware-specific names to the stable `/psilia/*` interface is done in the launch file — not baked into the image.

### Customisation

By default the user never needs to touch any of this. When they do want to customise:

```bash
# Edit the launch file directly on the Jetson
vim /opt/psilia/ros/psilia_runtime/launch/default.launch.py

# Restart the runtime to pick up changes
psilia restart   # rebuilds overlay, relaunches
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
    web_ui_bridge,
    foxglove_bridge,
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

If autostart is enabled the runtime is already running on arrival in the field. If not, start it manually from the laptop before heading out:

```bash
psilia start          # start the runtime
psilia stop           # stop the runtime
psilia restart        # rebuild overlay and relaunch (e.g. after editing the launch file)
psilia autostart on   # enable autostart on boot
psilia autostart off  # disable autostart on boot
```

The user does not need to SSH into the Jetson for any of this.

**Entry point:** Browser on phone or laptop → Control UI served from Jetson over hotspot.

### Control UI
Minimal by design. Covers only what is needed in the field:

- **Runtime status** — is the runtime healthy, which topics are publishing, at what rate
- **Start / Stop recording** — name the file, pick topics, one tap to record
- **Active recording status** — duration, file size, confirm topics are being captured
- **Stop recording** — explicit confirmation, file is flushed and closed cleanly

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
| Spatial Runtime | Jetson (Docker) | systemd / `psilia start` | Perception outputs, recording |
| Control UI | Jetson (served) | Browser (phone/laptop) | Monitor, record |
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
      api/                # MCAP reader, Dev API
      daemon/             # runs on Jetson host (not inside Docker)
        daemon.py         # manages Docker container lifecycle via docker run/stop
        server.py         # web server, bridges daemon ↔ browser
  web/                    # Control UI frontend
    src/
    package.json
    dist/                 # built output, served by server.py
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
- `psilia` — installed via pip
- ROS node deps: camera drivers, MCAP recorder, Foxglove bridge
