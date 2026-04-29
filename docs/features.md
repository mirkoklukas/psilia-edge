# Commands

> Available CLI commands grouped by area.

## Device Management

```
psilia pair                         Pair a Jetson (SSH keypair, register device)
psilia bootstrap <device>           Bootstrap a Jetson over SSH (clone, install, setup)
psilia devices                      List registered devices
```

## Sensors & Calibration

```
psilia sensor scan                  Detect connected cameras and USB devices
psilia sensor add                   Register a sensor, associate calibration file
psilia sensor remove <key>          Unregister a sensor
psilia sensor list                  Show registered sensors
psilia sensor push <device>         Push sensor entries + calibrations to a remote device
```

## Runtime Lifecycle

```
psilia runtime init [path]          Create runtime home, Docker image, ROS workspace
psilia runtime setup                Interactive setup (init + hotspot + WiFi)

psilia runtime start --base         Start base layer (FastAPI + Docker container)
psilia runtime start --spatial      Start spatial layer (ROS nodes)
psilia runtime stop                 Stop spatial + base layers

psilia runtime attach               Live TUI: heartbeat, topic Hz, start/stop spatial
psilia runtime status               Status snapshot (base, spatial, docker, storage, etc.)
psilia runtime config [keys...]     Query runtime config values

```

## Data Operations

```
psilia data pull [device]           Pull MCAP recordings from device to laptop
psilia data push [device]           Push data to cloud (direct or via laptop)
```


## Spatial Perception (ROS Nodes)

Nodes launched by the spatial layer, configurable via `runtime.yaml`:

```
camera_node                         Stereo camera capture (raw image pairs)
rectify_node                        Stereo rectification (remap tables)
depth_node                          Stereo depth — OpenCV StereoSGBM (CPU)
depth_cuda_node                     Stereo depth — CUDA (Jetson)
preview_node                        Downsampled image preview
depth_preview_node                  Colorized depth preview
pointcloud_preview_node             3D point cloud preview
recording_node                      MCAP recording (start/stop via ROS topic)
core_node                           Heartbeat, status, interface broadcasting
diagnostics_node                    Topic Hz monitoring
ping_node                           ROS connectivity test
```

## Web UI

Pages served by the base layer at `http://<device>.local:<api_port>`:

```
/                                   Landing page, quick status overview
/runtime-status.html                Full runtime status
/recording.html                     Start/stop recording, topic selection
/config.html                        Displays psilia.yaml
/runtime-test.html                  Ping/pong ROS connectivity test (dev)
/network-test.html                  Bandwidth and latency test (dev)
```
