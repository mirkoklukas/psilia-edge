# Filesystem Layout

## Jetson (runtime host)

```
/etc/psilia/
  runtime_config.yaml   # system-wide config, written during setup, read at boot
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

## Environment Variable Overrides (for testing)

| Variable            | Default                | Description                                                                 |
|---------------------|------------------------|-----------------------------------------------------------------------------|
| `PSILIA_CONFIG_DIR` | `/etc/psilia`          | **config dir** — system-wide config (`runtime_config.yaml`), on eMMC       |
| `PSILIA_RUN_DIR`    | `/run/psilia`          | **run dir** — ephemeral runtime state: PID file, sockets, cleared on reboot |
| `PSILIA_LOG_DIR`    | `/var/log/psilia`      | **log dir** — persistent daemon logs                                        |
| `PSILIA_BASE_DIR`   | `/ssd/psilia`          | **base dir** — install root on SSD: repo, ROS workspace, data               |
| `PSILIA_REPO_DIR`   | `/ssd/psilia/psilia-edge` | **repo dir** — psilia-edge repo clone (`pip install -e .`)               |
| `PSILIA_ROS_DIR`    | `/ssd/psilia/ros`      | **ros dir** — colcon workspace, mounted into Docker at runtime              |
| `PSILIA_DATA_DIR`   | `/ssd/psilia/data`     | **data dir** — MCAP recordings and other runtime data                       |
