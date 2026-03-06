# Todo

## Next up
- Continue code restructuring: finalize `runtime/` vs `device_manager/` split,
  clean up `runtime/commands.py` (start/stop/status/monitor logic placement),
  decide on `network/` ownership.

---

## Mode 1: Pair + Setup

| Step | Description | Status |
|------|-------------|--------|
| 1  | Connect — Path A (known IP) / Path B (discover over ethernet) | ✅ |
| 2  | Device name — read current hostname, set new one via hostnamectl | ✅ |
| 3  | SSH keypair — generate RSA-4096, install pubkey on Jetson | ✅ |
| 4  | Write SSH config (managed psilia-edge section) | ✅ |
| 5  | Register device (~/.psilia/config.yaml) | ✅ |
| 6  | SSD — detect drives, confirm mount point, configure /etc/fstab | ⬜ |
| 7  | Create dirs — /opt/psilia, /ssd/psilia/ros/src, /ssd/psilia/data | ✅ |
| 8  | Clone psilia-edge repo + pip install -e . | ✅ |
| 9  | Copy ROS package (psilia_runtime) to Jetson workspace | ✅ |
| 10 | Docker — check installed, install via get.docker.com if missing | ✅ |
| 11 | Build Docker image (psilia/runtime:latest) | ⬜ |
| 12 | Network — detect dongle/interface, create hotspot via nmcli | ✅ |
| 12b| Network — wifi client setup (connect Jetson to existing network) | ⬜ |
| 13 | Camera detection (optional) | ⬜ |
| 14 | Systemd autostart service | ⬜ |
| 15 | Write Jetson config (/opt/psilia/runtime_config.yaml) | ✅ |
| 16 | Sync runtime config back to laptop (~/.psilia/config.yaml) | ✅ |

## Mode 2: Runtime

| Feature | Description | Status |
|---------|-------------|--------|
| Daemon  | Start/stop background process, PID file, log file | ✅ |
| Web server | FastAPI + uvicorn, serves web/ from repo root | ✅ |
| CLI | `psilia start/stop/status/monitor [device]` | ✅ |
| Web UI | Static HTML control page, polls /api/status | ✅ |
| /api/status | Structured status dict (runtime, hotspot, sensors, storage, runtime_config) | ✅ |
| `psilia status` | Pretty-prints runtime status dict | ✅ |
| Docker status | Check if Docker is running on device | ⬜ |
| ROS runtime status | Check if psilia Docker container is running | ⬜ |
| `psilia spatial start/stop` | Start/stop the ROS Docker container | ⬜ |
