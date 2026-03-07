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

## Hotspot not visible as available network

**Symptom:** `psilia status` shows hotspot as active but the SSID doesn't appear on other devices.

**Cause:** Some USB wifi dongles activate in `managed` mode on the first `nmcli connection up`,
even though AP mode is supported. The interface reports as connected but isn't broadcasting.

**Verify:**
```bash
iw dev    # should show "type AP" — if it shows "type managed", the hotspot isn't broadcasting
```

**Fix:** Cycle the connection:
```bash
sudo nmcli connection down <ssid>-Hotspot
sudo nmcli connection up   <ssid>-Hotspot
```

This is now handled automatically in `create_hotspot()` — the fix is in place for future setups.

---

## Debugging: container exits immediately after `psilia start`

If `docker ps` shows no running container after starting the runtime, the container
likely exited due to an entrypoint error (e.g. `colcon build` failure).

```bash
docker ps -a                  # confirm container is in exited state
docker logs psilia-runtime    # see why it stopped
```
