# Filesystem Layout

## Jetson (runtime host)

```
/etc/psilia/
  device_config.yaml   # system-wide config, written during setup, read at boot
                        # lives here so it is available before the SSD mounts

/run/psilia/            # ephemeral runtime state, cleared on reboot
  psilia-edge.pid       # PID of the running base layer daemon
  psilia-edge.sock      # (future) Unix socket

/var/log/psilia/        # persistent logs
  psilia-edge.log       # base layer daemon log

/ssd/psilia/            # SSD — everything else
  psilia-edge/          # repo clone (pip install -e . run from here)
  ros/                  # colcon workspace (mounted into Docker at runtime)
    src/
      psilia_runtime/   # default ROS package — visible and editable
    build/
    install/
    log/
  data/
    recordings/         # MCAP files
      {device}_{session}_{counter}_{timestamp}.mcap
```

## Laptop (device manager)

```
~/.psilia/
  config.yaml           # device registry, pull_to path, cloud target
  keys/
    {name}              # dedicated SSH keypair per device, generated during pair

~/psilia-data/          # local recording storage (pulled from Jetson)
  recordings/
```

## Jetson Cleanup — Paths Used in Earlier Versions

Paths that were used in previous versions and can be safely removed from the Jetson.

```bash
# Config dir (moved from /opt/psilia to /etc/psilia)
sudo rm -rf /opt/psilia

# Runtime config filename (renamed from runtime_config.yaml to device_config.yaml)
sudo rm -f /etc/psilia/runtime_config.yaml
```

---

## Path Reference

| Description                          | Default      | Default overwritten       | Configurable | Python (`runtime.config`)  |
|--------------------------------------|---------------------------------|---------------------|--------|-----------------|
| **config dir** — on eMMC, always available before SSD mounts | `/etc/psilia`     | `ENV:PSILIA_CONFIG_DIR` | - | `CONFIG_DIR`            |
| **device config** — written by `psilia setup`, read at runtime | `/etc/psilia/device_config.yaml` |      | ✓  | `DEVICE_CONFIG_PATH`    |
| **run dir** — ephemeral state: PID file, sockets; cleared on reboot | `/run/psilia`  | `ENV:PSILIA_RUN_DIR`   | - | `RUN_DIR`               |
| **log dir** — persistent daemon logs | `/var/log/psilia`        | `ENV:PSILIA_LOG_DIR`      | - | `LOG_DIR`               |
| **base dir** — install root on SSD   | `/ssd/psilia`            |  `ENV:PSILIA_BASE_DIR`    | ✓ | `get_base_dir()`        |
| **repo dir** — psilia-edge repo clone (`pip install -e .`)      | `{base}/psilia-edge` |  | ✓   | `get_repo_dir()`      |
| **ros dir** — colcon workspace, mounted into Docker at runtime | `{base}/ros` |        | ✓  | `get_ros_dir()`         |
| **data dir** — MCAP recordings       | `{base}/data`              |                  | ✓  | `get_data_dir()`        |
