# Psilia: Perception & Spatial Intelligence on the Edge

## About Psilia

The name, Psilia, is derived from the greek letter psi (Ψ), which we take as an acronym for Perception & Spatial Intelligence.

We are building the spatial intelligence stack for embodied AI, starting at the foundation. Psilia Edge is the first layer: a reliable, hardware-agnostic perception runtime that gives robotics teams a stable base to build on. From there we expand into the full stack: SDK, data platform, and spatial intelligence.

(For the first stage we are going to lean heavily into the installation and setup experience and remove all friction to set up a sensor rig to record data in the field and explore that data later in a Jupyter notebook.)

## Psilia-Edge: The Spatial Runtime for Embodied AI

*Our goal is to be the first thing installed on Jetson. The Docker Desktop for spatial perception.*

Plug in a stereo camera, run one command, and get reliable depth, pose, and spatial outputs as a stable ROS interface in under 5 minutes. Hardware-agnostic, open format, no ROS wrangling required. Swap or extend the underlying algorithms without changing the interface.

A lightweight control UI handles device pairing, network setup, monitoring, recording, and data sync. No manual node orchestration, no bash scripts. Unless you want to. Everything is open and accessible. Recorded data is stored as open MCAP files and accessible via a lightweight Python API. Query topics by time, sync streams, and inspect message statistics in a few lines of code.

### **Overview**

Psilia-Edge consists of three parts: Spatial Runtime, Setup Manager & Control UI, and Dev API.

**Spatial Runtime.**

Psilia-edge is an installable spatial-perception runtime exposing a small stable interface (`/psilia/image`, `/psilia/depth`, `/psilia/pose`) on edge devices in under 5 minutes.

It includes (maybe not in v0) an optional minimal spatial intelligence layer (e.g. `/psilia/ground_plane`, `/psilia/obstacle_map`). This remains lightweight at first and serves as an entry point for future spatial intelligence. (What is the minimal layer of information needed to enable autonomy.)

The runtime is configurable / programmable. That means I should be able to switch algorithms for pose and depth estimation.

It is not a camera product nor a SDK competing with Stereolabs. Psilia Edge is a runtime layer that sits one level below autonomy stacks and one level above raw sensors and the edge device (Docker Desktop for spatial perception).

You plug in a supported stereo camera, run two commands, and get a stable spatial interface. Works with off-the-shelf hardware.

**Setup manager & Control UI.**

Psilia Edge helps you configure, manage, and setup communication with your edge device, e.g. establish ssh and wifi connections.

Psilia Edge includes a lightweight runtime control UI that lets developers monitor spatial output and manage recordings without interacting directly with ROS or the CLI. (Runs on your mobile phone for instance.) The UI should control the Psilia runtime and Psilia-managed processes and services. It should **not** become a general ROS process manager in v0.

**Dev API**

A lightweight Python interface for exploring, analyzing, and prototyping on recorded spatial data without running ROS.

On the Dev side we also provide a lightweight Python interface for working with recorded spatial data outside the live runtime. A fast, ergonomic MCAP reader that returns typed arrays/iterators with minimal ceremony. Access `/psilia/*` topics (any topic actually) as simple Python or NumPy objects, by time or time intervals etc. Inspect message timing, publishing rates, and lag. Replay or slice recordings for algorithm testing.

## Psilia-Edge (Version 0.1.0) Deliverable / Specs

Concretely what does psilia-edge provide? What is the experience? I try to chronologically go through the list of required features for the first version:

- **Establish and manage wifi and ssh connections** (wifi, ethernet, hotspots). There is usually 3 machines to connect: Jetson, Laptop, and Cloud, and potentially a mobile phone for the control UI. Maybe have a “pairing” process, psilia-edge should guide you through the experience of establishing connections and setting up hotspots and what not.
- **Control UI.** Web-based interface to:
    - Monitor status of the runtime. Configure runtime.
    - Start/Stop recording data (ROS bags/MCAP files). Easy naming of the files. Picking topics to record.
    - Sync Data.
- **Data Management.** Easy way to sync data from the Jetson to laptop and cloud (might be laptop and then cloud or direct, depending on the connection). Naming conventions for organizing the data, e.g. `f"{device}_{session}_{counter}_{timestamp}.mcap"`.
- **Data API.** Minimal python library for accessing MCAPs and lightweight Transform classes for now. Some minimal ways to view message statistics, like time lags and publishing times etc.

    ```bash
    /psilia/pose   (live topic)
    pose[t]        (offline Python array)
    pose.closest(t)
    ...
    taker = MCAP("/data/session/recording.mcap", **config)
    poses, depths = taker.k["/psilia/pose", "/psilia/depth"].i[0,0].t(5., 6.)
    ```


## The Pain Points

**Execution Environments**

Deep tech stack in robotics. Different dev and execution environments: local or cloud-based dev environment, and the deployed edge device.

There are **two execution environments** that embodied-AI teams constantly jump between:

1. On-device / edge runtime environment (OS on edge device, ROS nodes, sensors, deployment)
2. Dev environment (Python, notebooks, analysis, prototyping). This usually lives both in the cloud and your local machine.

Psilia should make the boundary between those worlds disappear.

The runtime should provide a stable spatial interface. Configurable/programmable. And we should be able to extend and iterate on the algorithms without redeploying ROS nodes.

**ROS Wrangling.**

Annoying to communicate with ROS through a bunch of terminals. Especially annoying if somewhere in the field recording data with a sensor rig …

### Example Scenario

You are a robotics dev that just assembled a sensor rig from freshly shipped parts (Jetson Nano + USB stereo cam off of Amazon). You want to take the rig and record data in the field, and explore the data later in a Jupyter notebook say. Think about everything you have to set up in order for that to happen.

- Setup the Jetson and install all relevant software.
- Establish WIFI and SSH connections between you and the Jetson. Also you are in the field later, so you might want to set up a hotspot on the Jetson or your phone as well.
- Calibrate the camera if you haven't done that. That alone is a huge pain point.
- Write a ROS nodes for the camera data if you don't already have one. You want to publish pose and depth estimates along side the original images. You probably run some test code in a Notebook, that you then wrap into an actual node. Write a nice launch script for that.
- In the field: You need to ssh into your Jetson and start your ROS nodes. At least the camera node and something like a foxglove-bridge to see the live data. You might want to check if the topics you expect are actually published, maybe check some logs and get a sense for the frame and publishing rates. Then you want to record. This is probably the 3rd terminal you have open. You start and stop a recording. Cross check the recording if everything is recorded properly. Mind you, you probably sitting on some bench in the park with a laptop on your lap.
- Back at your home base you open a terminal and pull the data from the Jetson.
- Now you open a Notebook and iterate over the ROS messages. You parse them and try to sync and match up different topics over time.
- Now also imagine you bought a new camera, an expensive ZED2i. Luckily they provide their own ROS node. Now you need to adjust your initial launch script to switch that node, and also re-map some of the topics, because they now have completely different names. Maybe you abstracted that away in your downstream code already.

For all of this there usually a bunch of bash scripts that everyone writes themselves.

## Differentiator to Stereolabs

**Stereolabs**

- Camera-first product. Stereolabs primarily sells a *hardware-centric* perception system.
- ZED cameras are the product. SDK exists to make their hardware useful.
- Their value chain: Camera → SDK → Features. Hardware drives everything.
- Closed, vertically integrated model. Calibrated factory devices, Proprietary pipeline. You adapt your robot around their stack!

**Psilia-Edge**

- Runtime-first, not camera-first. Experience is hardware agnostic.
- “The easiest way to get spatial perception running on Jetson”
- Simpler, open, and hackable. “Edge-native perception for builders/devs.”
- Value Chain: Runtime → Stable Outputs → Ecosystem. Hardware is optional scaffolding. That’s a huge structural difference.

Both give: depth, pose, spatial outputs. So to users: “It kind of feels like ZED but easier.” That’s fine. But internally you must think: “We are not replacing ZED. We are replacing ROS setup pain.”

Hardware is optional scaffolding.

- Avoid “cheap alternative to StereoLabs” framing. That’s a trap. Better positioning:

    **NOT** “Low-cost ZED replacement”

    **INSTEAD** “Edge-native spatial perception SDK” “Edge-native perception for builders/devs.”

    Not just cheaper, it is **simpler and more hackable**.


Stereolabs = hardware + SDK

Psilia Edge = Docker Desktop for spatial perception
