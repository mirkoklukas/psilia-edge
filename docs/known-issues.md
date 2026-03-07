# Known Issues & Fixes

## Docker build fails with `iptable_raw` error

**Error:**
```
iptables v1.8.7 (legacy): can't initialize iptables table `raw': Table does not exist
(do you need to insmod?)
```

**Cause:** The `iptable_raw` kernel module is not loaded. Docker needs it to set up its
network bridge during image builds. Common on certain JetPack versions.

**Fix:**

The `iptable_raw` module may not be available in the Tegra kernel (e.g. `5.15.148-tegra`).
In that case, build with `--network=host` to bypass bridge networking entirely:

```bash
docker build --network=host -t psilia/runtime:latest /ssd/psilia/psilia-edge/ros/
```

---

## Debugging: container exits immediately after `psilia start`

If `docker ps` shows no running container after starting the runtime, the container
likely exited due to an entrypoint error (e.g. `colcon build` failure).

```bash
docker ps -a                  # confirm container is in exited state
docker logs psilia-runtime    # see why it stopped
```
