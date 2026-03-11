# Psilia Edge — Spatial Runtime

## Overview

The spatial runtime has two layers:

- **Base layer** — FastAPI daemon running directly on the Jetson host. Always-on control plane. Manages the ROS layer lifecycle, serves the Control UI, exposes a REST API for the CLI and web UI.
- **ROS layer** — ROS nodes running inside a Docker container. Started on demand by the base layer. The actual perception pipeline: mock/camera driver, depth, pose, MCAP recorder, rosbridge.

---

## Nodes & Topics

| Node | Topics Published | Rate | Notes |
|------|-----------------|------|-------|
| `mock_node` | `/psilia/image`, `/psilia/depth`, `/psilia/pose` | 30 Hz | Synthetic data, no hardware required |
| `status_node` | `/psilia/status`, `/psilia/info` | 1 Hz / latched | Heartbeat + static metadata |
| `rosbridge_websocket` | — | — | WebSocket bridge on port 9090 |

---

## Communication

### Web UI ↔ Runtime

The web UI makes two distinct connections to the Jetson:

**FastAPI (base layer, port 8080)** — lifecycle control:
- `GET /api/status` — overall runtime status (docker, ROS layer up/down, network)
- `POST /api/spatial/start` — start the ROS Docker container
- `POST /api/spatial/stop` — stop the ROS Docker container

**rosbridge (ROS layer, port 9090)** — live ROS data via roslibjs:
- Subscribe to `/psilia/status` for live heartbeat and topic health
- Subscribe to `/psilia/info` for static metadata (camera config, topic list)
- Recording control: publish to a recording node topic (start/stop)

> **Note:** roslibjs is currently loaded from CDN (`unpkg.com`). In the field there may be
> no internet access — consider vendoring `roslib.min.js` into `web/vendor/` before field use.

#### Message Types

| Topic | Type | Direction | Payload |
|-------|------|-----------|---------|
| `/psilia/status` | `std_msgs/String` | subscribe | `{"status": "ok", "stamp": <nanoseconds>}` |
| `/psilia/info` | `std_msgs/String` | subscribe | `{"version", "camera", "topics", "ros_workspace"}` |
| `/psilia/ping` | `std_msgs/String` | publish | `{"message": "ping", "timestamp": <ms>}` |

### CLI ↔ Runtime

TBD
