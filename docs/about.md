
# Psilia: Perception & Spatial Intelligence on the Edge

## About Psilia

The name, Psilia, is derived from the greek letter psi (Ψ), which we take as an acronym for Perception & Spatial Intelligence.

We are building the spatial intelligence stack for embodied AI, starting at the foundation. **Psilia Edge** is the first layer: a reliable, hardware-agnostic perception runtime that gives robotics teams a stable base to build on. From there we expand into the full stack: SDK, data platform, and spatial intelligence.

(For the first stage we are going to lean heavily into the installation and setup experience and remove all friction to set up a sensor rig to record data in the field and explore that data later in a Jupyter notebook.)

## Psilia-Edge: The Spatial Runtime for Embodied AI

*Our goal is to be the first thing installed on Jetson. The Docker Desktop for spatial perception.*

Plug in a stereo camera, run one command, and get reliable depth, pose, and spatial outputs as a stable ROS interface in under 5 minutes. Hardware-agnostic, no ROS wrangling required. Swap or extend the underlying algorithms without changing the interface.

A lightweight control UI handles device pairing, network setup, monitoring, recording, and data sync. No manual node orchestration, no bash scripts. Unless you want to. Everything is open and accessible. Recorded data is stored as open MCAP files and accessible via a lightweight Python API. Query topics by time, sync streams, and inspect message statistics in a few lines of code.
