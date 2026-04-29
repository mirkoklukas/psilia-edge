# Setup & Install

> **Summary:** How to install and configure the system. Covers the full install flow (laptop setup, pairing, bootstrapping a Jetson, first-time init), network setup wizard (AP and client modes), and system/Python/Docker dependencies.

## Install Flow

### Laptop setup (once)

Clone the repo and pip-install to get the CLI:

```bash
git clone ... psilia-edge && cd psilia-edge
pip install -e .
```

### Connecting to a Jetson (once per device)

```bash
psilia pair [<host>]
```

Laptop-side wizard: SSH into the Jetson, generate a keypair, register the device in `~/.psilia/psilia.yaml`, and add an entry to `~/.ssh/config`. After pairing, the device is addressable by name (e.g. `my-jetson`).

### Bootstrapping a fresh Jetson (once per device)

```bash
psilia bootstrap my-jetson
```

Laptop-initiated, runs over SSH. Clones the repo on the Jetson, pip-installs, and calls `psilia init` to provision the runtime home. This is the single command to get a fresh Jetson ready from scratch. Internally it downloads and runs a bootstrap script on the device.

### First-time runtime setup (local, on the Jetson)

```bash
psilia init [<runtime-home-path>]
```

Local command, also called by `bootstrap`. Creates the runtime home directory structure, builds the Docker image, copies the ROS workspace, and writes `runtime.home_path` into `psilia.yaml`. One-time operation.

### Reconfiguring specific aspects

```bash
psilia setup --hotspot
psilia setup --wifi
psilia setup --all
```

Run at any time after `init` to configure or reconfigure specific aspects (network hotspot, home WiFi, etc.). Not a first-time-only command.

### Command roles summary

| Command | Who runs it | When |
|---|---|---|
| `psilia pair` | Laptop | Once, to register a new Jetson |
| `psilia bootstrap <device>` | Laptop (over SSH) | Once, to provision a fresh Jetson |
| `psilia init` | Jetson (local) | Once, first-time runtime home setup |
| `psilia setup [--hotspot\|--wifi]` | Jetson (local or via `-d`) | Any time, to reconfigure |
| `psilia config <key>` | Anywhere | Read-only config query |


## Network Setup

Two distinct concerns:

**1. Field connectivity** — how the phone/laptop and Jetson find each other in the field so the Web UI and rosbridge are reachable. Configured via `psilia runtime setup --network`, stored under `network.mode` / `network.ap` / `network.client`. Two modes:
- **Mode 1 — Jetson AP** (dongle or built-in WiFi): Jetson hosts a hotspot, phone/laptop connects to it.
- **Mode 2 — Jetson client**: phone creates a hotspot, Jetson connects to it.

**2. Home network** — a known WiFi the Jetson connects to when available (e.g. at home base). Not for field use. The base layer detects if the Jetson is on this network and indicates it in the Web UI. Future: trigger cloud uploads when connected. Stored under `network.home`. WiFi only for now; other connection types (ethernet) may be relevant in the future.

### Config (`psilia.yaml`)

```yaml
network:
  mode: ap          # field connectivity: ap | client
  ap:
    ssid: psilia-ap
    password: psilia1234
    interfaces:
      - name: wlx...        # detected during setup
        type: usb-dongle    # usb-dongle | built-in
        autostart: true     # nmcli autoconnect when interface is available (boot or plug-in)
        start_on_runtime: true  # brought up on `psilia runtime start`
  client:
    ssid: MyPhone
    password: secret
    autostart: true
    start_on_runtime: true
  home:
    ssid: my-home-wifi      # known WiFi — base layer detects if in range and
    password: secret        # indicates connectivity in the Web UI.
    # Future: trigger cloud upload when connected.
    # Future: other connection types (ethernet) may be relevant here too.
```

### Wizard Flow (`psilia runtime setup --network`)

1. Enumerate AP-capable interfaces; detect type via `wlx` prefix and `lsusb` cross-reference
2. If multiple, let the user pick one
3. Prompt for SSID, password, `autostart`, and `start_on_runtime` for the selected interface
4. Create an NM connection profile for that interface
5. Write config to `psilia.yaml`

For **Mode 2 (client)**, the wizard collects the phone hotspot SSID and password and creates a single NM client profile. `psilia runtime start` calls `nmcli connection up` if not already connected.

### Network Test (`/network-test.html`)

The web UI includes a network test page where the user can verify the connection is sufficient for camera streaming. The target is low-res image streaming (e.g. 320×240 @ 5 fps). The latency and throughput tests on the page should be calibrated against this requirement — pass/fail thresholds set accordingly.

When both a dongle and built-in WiFi are present, the Jetson can act as its own client: host the AP on one interface and connect to it with the other, then run the throughput test over that link. Traffic goes over the air so it's a real measurement, useful for validating an interface during setup before a phone is connected.


## Dependencies

(MAKE SURE THESE ARE UP TO DATE)

**System — required before `pip install`:**
Python 3.10+, `pip`, `git`.

**System — installed during `psilia runtime setup`:**
Docker. On Jetson: `nmcli` / NetworkManager (hotspot), `systemd` (autostart), `v4l-utils` (camera detection).

**Python packages (`psilia-edge`):**
`typer`, `rich`, `pyyaml`, `paramiko`, `fastapi`, `uvicorn`, `psutil`, `mcap`, `numpy`.

**Docker image (`psilia/runtime:latest`):**
ROS 2 Humble, CUDA / JetPack-compatible base, camera drivers, MCAP recorder, Foxglove bridge, `colcon`.

**`psilia` inference library (inside Docker only):**
`numpy`, `opencv-python`, and optional inference deps (`torch`, `onnxruntime`) installed as extras.
