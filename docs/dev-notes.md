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


## Notes & Ideas

> TODOs and actionable items have moved to `docs/todo.md`.

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
