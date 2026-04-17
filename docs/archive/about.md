![](../assets/psilia-logo-bw.png){width=250px}

---

# Vision & Strategy

-- SHORT,LIGHTWEIGHT, STORY, VISION, STRATEGY --

## Psilia Platform

Every robotics team working with perception on edge hardware hits the same wall. Device setup, camera calibration, field workflow, data pipelines, algorithm development -- each stage has its own friction, its own duct-tape solutions. Nothing covers the full cycle. Proprietary SDKs cover parts of it, but lock you into their hardware and their algorithms.

We are building the **perception and spatial intelligence platform** for the edge. The layer between raw sensors and the autonomy logic above, and the tooling around it -- so teams can focus on what's unique to their mission.

Concretely, that means building toward three things:

- A robust, reliable perception layer you can build on.
- The tooling for fast, frictionless prototyping.
- High-quality spatial perception at a fraction of the hardware cost.

## Psilia Edge: The foundational layer for spatial perception.

*Psilia Edge* is our first product: a **spatial perception runtime** for Jetson, packaged to be easy to install, easy to operate, and easy to build on.

Plug in a stereo camera, run one command, and get reliable depth, pose, and spatial outputs as a stable ROS interface in under 5 minutes. Hardware-agnostic, no ROS wrangling, no bash scripts. Unless you want to. Everything is open and accessible. Swap or extend the underlying algorithms without changing the interface.

A lightweight control UI handles device pairing, network setup, monitoring, recording, and data sync. Recorded data is stored as open MCAP files and accessible via a lightweight Python API. Query topics by time, sync streams, and inspect message statistics in a few lines of code.

## Target, Strategy, and Timing

Large robotics companies and well-funded labs have already built internal pipelines for this. They've solved it for themselves. That's not the target.

The target is early-stage startups, small teams, and researchers -- the people feeling the pain today and building the robotics companies of tomorrow. Meeting them early and growing with them is the strategy.

Robotics hardware is getting cheaper. Entry barriers are falling. But cheaper sensors alone don't accelerate the field -- the tooling and abstractions around them do.

PyTorch didn't win because it had better algorithms. It won because it made the iteration cycle fast and intuitive. A larger community could experiment, more ideas got tried, and the field moved faster. The community became the moat. That's the model.

## Go-to-Market

The runtime and core algorithms are free and open source. The v0 go-to-market is a bundled USB stereo camera -- cheap off-the-shelf hardware paired with our algorithms and runtime. The goal is not hardware margin. The goal is owning the first experience end-to-end: plug in the camera, run one command, get spatial outputs. The bundle is distribution and a wedge, not the product. It gets installs, lowers the barrier to a first success, and puts users on the data flywheel from day one.

## Business Model

The runtime and core algorithms are free and open source. Monetization comes from premium services layered on top:

- **Data platform** – starts with getting data off the device and into managed cloud storage, and grows into the tooling teams need once data is there: post-processing, inspection, evaluation, annotation.
- **Premium algorithms** – advanced or domain-specific algorithms beyond the open-source baseline. Open-core model.

The open runtime gets adoption. The data platform and premium services get revenue.

## Key Numbers

- 2M+ developers on NVIDIA Jetson
- $10B+ invested in robotics startups in 2025
- Edge AI market: ~$25B, growing 22% Compound Annual Growth Rate (CAGR)

References:

- [https://blogs.nvidia.com/blog/2-million-robotics-developers/](https://blogs.nvidia.com/blog/2-million-robotics-developers/)
- [https://news.crunchbase.com/venture/aerial-robotics-startup-infravision-seriesb/](https://news.crunchbase.com/venture/aerial-robotics-startup-infravision-seriesb/)
- [https://www.grandviewresearch.com/industry-analysis/edge-ai-market-report](https://www.grandviewresearch.com/industry-analysis/edge-ai-market-report)

<!--
# Psilia: Perception & Spatial Intelligence on the Edge

## Psilia Platform

Every robotics team working with perception on edge hardware hits the same wall. Device setup, camera calibration, field workflow, data pipelines, algorithm development -- each stage has its own friction, its own duct-tape solutions. Nothing covers the full cycle. Proprietary SDKs cover parts of it, but lock you into their hardware and their algorithms.

We are building the **perception and spatial intelligence platform** for the edge. The layer between raw sensors and the autonomy logic above, and the tooling around it -- so teams can focus on what's unique to their mission.

Concretely, that means building toward three things:

- A reliable perception layer you can build on.
- The tooling for fast, frictionless prototyping.
- High-quality spatial perception at a fraction of the hardware cost.

## Psilia Edge: The foundational layer for spatial perception.

*Psilia Edge* is our first product: a **spatial perception runtime** for Jetson, packaged to be easy to install, easy to operate, and easy to build on.

Plug in a stereo camera, run one command, and get reliable depth, pose, and spatial outputs as a stable ROS interface in under 5 minutes. Hardware-agnostic,
no ROS wrangling, no bash scripts. Unless you want to. Everything is open and accessible. Swap or extend the underlying algorithms without changing the interface.

A lightweight control UI handles device pairing, network setup, monitoring, recording, and data sync. Recorded data is stored as open MCAP files and accessible via a lightweight Python API. Query topics by time, sync streams, and inspect message statistics in a few lines of code. -->


<!-- ## About Psilia

Our name, Psilia, is derived from the greek letter psi (Ψ), which we take as an acronym for Perception & Spatial Intelligence.

We are building the spatial intelligence stack for embodied AI, starting at the foundation. **Psilia Edge** is the first layer: a reliable, hardware-agnostic perception runtime that gives robotics teams a stable base to build on. From there we expand into the full stack: SDK, data platform, and spatial intelligence.

(For the first stage we are going to lean heavily into the installation and setup experience and remove all friction to set up a sensor rig to record data in the field and explore that data later in a Jupyter notebook.)

## Psilia-Edge: The Spatial Runtime for Embodied AI

*Our goal is to be the first thing installed on Jetson. The Docker Desktop for spatial perception.*

Plug in a stereo camera, run one command, and get reliable depth, pose, and spatial outputs as a stable ROS interface in under 5 minutes. Hardware-agnostic, no ROS wrangling required. Swap or extend the underlying algorithms without changing the interface.

A lightweight control UI handles device pairing, network setup, monitoring, recording, and data sync. No manual node orchestration, no bash scripts. Unless you want to. Everything is open and accessible. Recorded data is stored as open MCAP files and accessible via a lightweight Python API. Query topics by time, sync streams, and inspect message statistics in a few lines of code. -->
