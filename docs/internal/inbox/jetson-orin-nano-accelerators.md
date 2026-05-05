---
type: inbox
created: 2026-05-05
summary: Jetson Orin Nano has no PVA and no OFA — implications for stereo depth and VPI offload paths.
source: Conversation 2026-05-05
tags: [jetson-nano, pva, ofa, hardware]
---

# Jetson Orin Nano — Hardware Accelerators

## What is PVA?

**PVA = Programmable Vision Accelerator.** A dedicated piece of silicon on Jetson Orin SoCs (separate from CPU and GPU) for low-power, deterministic computer-vision workloads — stereo disparity, optical flow, image filtering, warps, FFT, feature detection. The Orin generation uses PVA v2.

Practical access is via NVIDIA's **VPI (Vision Programming Interface)**: each VPI algorithm exposes backends (`CPU`, `CUDA`, `PVA`, `VIC`, `OFA`) and the developer picks one per call. Writing custom PVA kernels requires an NDA SDK and is not generally available.

The benefit of PVA when present: it runs in parallel to the GPU, so offloading vision work frees the GPU for inference, with lower power and more predictable latency.


## What is OFA?

**OFA = Optical Flow Accelerator.** Another dedicated accelerator on Jetson Orin (separate from CPU, GPU, and PVA). VPI uses it for optical-flow estimation and exposes an "advanced SGM variant" of stereo disparity that runs on OFA (combinable with the VIC and PVA backends). Like PVA, it offers GPU-offloaded vision work with lower power and predictable latency.


## Finding: Orin Nano has no PVA and no OFA

NVIDIA's official Jetson Linux Developer Guide (R36.4.4, NVP Model Clock Configuration tables) explicitly shows neither accelerator on the Nano tier:

| Module | PVA cores | OFA |
|---|---|---|
| Jetson Orin Nano 4GB | 0 | not listed (absent) |
| Jetson Orin Nano 8GB | 0 | not listed (absent) |
| Jetson Orin NX 8GB | 1 | yes (780.8 MHz) |
| Jetson Orin NX 16GB | 1 | yes (780.8 MHz) |
| Jetson AGX Orin (all variants) | ≥1 | yes (780.8 MHz) |

For both Orin Nano variants the tables show `PVA VPS maximal frequency (MHz): n/a` and contain no OFA entry at all.


## Implications for Psilia Edge

- VPI's `StereoDisparityEstimator` can still run on Orin Nano, but only via the **CPU** or **CUDA** backends — neither **PVA** nor **OFA** backends are available.
- Any "offload stereo to PVA or OFA to free up the GPU" plan is off the table on this platform.
- Consequence: stereo depth, image preprocessing, and any inference workload all share the single Ampere GPU. Compute-budget decisions need to account for that contention.


## Not verified

- **VIC (Video Image Compositor):** likely present (it's part of the display/ISP path) but not separately confirmed.


## Sources

- [NVIDIA Jetson Linux Developer Guide — NVP Model Clock Configuration (Orin Nano / NX / AGX)](https://docs.nvidia.com/jetson/archives/r36.4.4/DeveloperGuide/SD/PlatformPowerAndPerformance/JetsonOrinNanoSeriesJetsonOrinNxSeriesAndJetsonAgxOrinSeries.html)
- [Jetson Orin Nano Super Devkit specs](https://www.nvidia.com/en-us/autonomous-machines/embedded-systems/jetson-orin/nano-super-developer-kit/)
- [NVIDIA Developer Forum — VPI PVA backend "is not available" error context](https://forums.developer.nvidia.com/t/warn-2023-12-22-0236-vpi-error-invalid-operation-pva-is-not-available-and-may-be-oversubscribed-in-the-system-pvaerror-deviceunavailable/276904)
