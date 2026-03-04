# Todo

## Mode 1: Init Wizard

| Step | Description | Status |
|------|-------------|--------|
| 1  | Connect — Path A (known IP) / Path B (discover over ethernet) | ✅ |
| 2  | Device name — read current hostname, set new one via hostnamectl | ✅ |
| 3  | SSH keypair — generate RSA-4096, install pubkey on Jetson | ✅ |
| 4  | Network — detect dongle/interface, create hotspot via nmcli | ✅ |
| 4b | Network — wifi client setup (connect Jetson to existing network) | ⬜ |
| 5  | SSD — detect drives, confirm mount point, configure /etc/fstab | ⬜ |
| 6  | Create dirs — /opt/psilia, /ssd/psilia/ros/src, /ssd/psilia/data | ✅ |
| 7  | Clone psilia-edge repo + pip install -e . | ✅ |
| 8  | Copy ROS package (psilia_runtime) to Jetson workspace | ✅ |
| 9  | Docker — check installed, install via get.docker.com if missing | ✅ |
| 10 | Build Docker image (psilia/runtime:latest) | ⬜ |
| 11 | Camera detection (optional) | ⬜ |
| 12 | Systemd autostart service | ⬜ |
| 13 | Write SSH config (managed psilia-edge section) | ✅ |
| 14 | Write laptop config (~/.psilia/config.yaml) | ✅ |
| 15 | Write Jetson config (/opt/psilia/config.yaml) | ✅ |

## Mode 2: Base Layer (runtime)

| Feature | Description | Status |
|---------|-------------|--------|
| Daemon  | Start/stop background process, PID file, log file | ✅ |
| Web server | FastAPI + uvicorn, served from psilia-edge install | ✅ |
| CLI | `psilia base start/stop/status/monitor`, `psilia start/stop/status` | ✅ |
| Web UI | Static HTML control page, polls /api/status every 3s | ✅ |
| /api/status | Returns network interfaces; docker/ros status stubbed | ✅ |
| Docker status | Check if Docker is running on device | ⬜ |
| ROS runtime status | Check if psilia Docker container is running | ⬜ |
| `psilia spatial start/stop` | Start/stop the ROS Docker container | ⬜ |
