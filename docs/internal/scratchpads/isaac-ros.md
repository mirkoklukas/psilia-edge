# Isaac ROS — Notes & Findings

> Investigation into using NVIDIA Isaac ROS (specifically ESS stereo depth) on the Jetson Orin Nano Super. Last updated: 2026-04-24.



## ESS Stereo Depth — Not Supported on Orin Nano

Isaac ROS 4.x (`isaac_ros_dnn_stereo_depth` / ESS) does **not** support the Jetson Orin Nano. Supported platforms as of April 2026:

- Jetson Thor (T5000 / T4000) — JetPack 7.1
- x86_64 with Ampere+ GPU — Ubuntu 24.04, CUDA 13.0+, NVIDIA Driver 580+
- DGX Spark — DGX OS 7.2.3

The Orin family appears to have been dropped entirely in Isaac ROS 4.x.

Source: https://nvidia-isaac-ros.github.io/repositories_and_packages/isaac_ros_dnn_stereo_depth/index.html


## Isaac ROS Package Distribution (4.x)

Individual Isaac ROS packages (e.g. `ros-jazzy-isaac-ros-ess`) are **no longer published as apt debs**. The old `release-4` apt repo only contains `isaac-ros-cli`.

The correct apt repo URL (found in the CLI's own Dockerfile) is:
```
https://isaac.download.nvidia.com/isaac-ros/release-4.3 noble main external-main
```
But even this repo only ships `isaac-ros-cli` (v2.2.0).

`isaac-ros-cli` is a development environment manager with three modes (`docker`, `venv`, `baremetal`). It does not install individual ROS packages — it either spawns an NVIDIA Docker container or sets up a shell environment. The actual packages come from either:
- NVIDIA's pre-built Docker images on NGC (`nvcr.io/nvidia/isaac/ros:...`)
- Building from source (GitHub repos under `NVIDIA-ISAAC-ROS`)


## Docker Image Notes

### Base Image
We use `dustynv/ros:jazzy-ros-base-r36.4.0-cu128-24.04` which provides ROS 2 Jazzy + CUDA on L4T R36.4 (JetPack 6.x).

### Build Issues Encountered
1. **iptables error** during `docker build` — fixed with `--network=host`
2. **Expired ROS 2 GPG key** in base image — fixed by refreshing the key:
   ```dockerfile
   RUN rm -f /usr/share/keyrings/ros-archive-keyring.gpg \
       && curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
           | gpg --batch --dearmor -o /usr/share/keyrings/ros-archive-keyring.gpg
   ```
3. **ESS packages not found** — because they're no longer distributed as debs (see above)


## Alternatives for DNN Stereo Depth on Orin Nano Super

Since ESS is off the table, options for DNN-based stereo depth:

1. **Current approach (no DNN):** `depth_cuda_node` using OpenCV CUDA StereoSGM — already works.
2. **Lighter stereo depth models via TensorRT:** RAFT-Stereo, CREStereo, or HitNet — smaller models that may fit on the Orin Nano's GPU (1024 CUDA cores, 8GB RAM, no DLA).
3. **Older Isaac ROS (3.x):** May have supported Orin with ESS, but targets ROS 2 Humble (we use Jazzy).
