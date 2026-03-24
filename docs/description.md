# Psilia — Position Paper

> **Psilia is the platform for perception and spatial intelligence at the edge.**

---

## The Problem

Building with spatial perception on edge hardware is harder than it should be. The pain shows up at every stage:

**Getting started.** Before you record a single useful frame in the field you've dealt with: OS setup on Jetson, ROS installation, camera drivers, camera calibration, WiFi and SSH configuration, writing launch scripts. There's no standard way to do any of it. Everyone starts from scratch.

**Field workflow.** In the field you're managing multiple terminals over SSH, manually starting ROS nodes, checking topic rates, starting and stopping recordings. If something breaks you're debugging blind. The tooling assumes you're at a desk.

**Data sync.** Robotics teams record large volumes of sensor data in the field. Getting that data off the device and into a usable storage location — laptop, NAS, cloud — is its own problem. There's no standard pipeline. It's usually a mix of rsync scripts, manual USB transfers, and cloud storage hacks that everyone assembles themselves.

**Working with data.** Once you have recordings, getting the data into a usable form is friction-heavy. Parsing ROS bags, syncing topics by timestamp, loading arrays into a notebook — there's no ergonomic tooling. Everyone writes their own glue code.

**Two execution environments.** Embodied AI teams constantly jump between two worlds: the edge runtime (Jetson, ROS, sensors, deployment) and the dev environment (Python, notebooks, cloud, algorithm iteration). The boundary between them is painful. Data flows one way with effort. Feedback loops are slow.

**Algorithm lock-in.** If you're using a proprietary stack (ZED SDK, for example) customizing or swapping algorithms means touching everything downstream. There's no stable abstraction. Upgrading one piece breaks another.

**Algorithm reliability.** Off-the-shelf algorithms work most of the time. But "most of the time" isn't good enough in the field — depth estimation fails in low texture, pose drifts, edge cases break things. Robust, fast algorithms that handle real conditions are genuinely hard and genuinely matter.

**Hardware cost.** High-quality spatial perception today means expensive proprietary hardware. That's a real barrier for researchers, hobbyists, and early-stage teams.

---

## The Vision

Psilia's goal is to own the perception and spatial intelligence layer — the part of the stack that sits between raw sensors and the autonomy logic above.

```
Planning & Control
─────────────────────────
Spatial Intelligence        (obstacle map, ground plane, scene understanding)
─────────────────────────
Perception / Algorithms     (depth, pose, images)
─────────────────────────
Runtime                     ← anchor
─────────────────────────
Sensors & Hardware
```

The runtime is the anchor. Everything else grows from there — downward into hardware support and algorithms, upward into spatial intelligence and eventually planning and control primitives.

The core architectural bet is the **runtime as a shared abstraction layer**. It sits between the hardware complexity below and the application logic above, absorbs the variation, and exposes a clean stable surface: `/psilia/depth`, `/psilia/pose`, `/psilia/image`. Swap the camera, swap the algorithm underneath — the surface doesn't change. Everyone builds on the same layer, and that layer is maintained, improved, and hardware-agnostic.

**Algorithms as a retention driver.** The stable interface is what keeps downstream code working. But robust, high-quality algorithms are what keeps users on the runtime as their use cases grow and their requirements get harder. Better algorithms are a differentiator and a reason to stay.

**The data flywheel.** Once the runtime runs, data accumulates. Owning the sync, storage, and dev tooling around that data — replay, evaluation, annotation, fleet management — ties users deeper into the ecosystem and feeds improvements back into the algorithms. It also closes the loop between the edge runtime and the dev environment: data flows out of the device, through Psilia's tooling, and back into algorithm iteration. The deeper into that pipeline Psilia goes, the stickier the platform becomes.

Over time the goal is to be the platform every spatial AI team builds on, regardless of hardware.

---

## Enable the Ecosystem

Large robotics companies and well-funded labs already have internal pipelines for this. They've solved it for themselves. That's not the target.

The target is everyone else — researchers, hobbyists, small teams, early-stage startups — who currently spend the majority of their time on plumbing and a fraction of it on the actual problems they're trying to solve. Compress the plumbing to near-zero and you unlock a much larger community of people who can experiment, iterate, and push boundaries.

Robotics hardware is getting cheaper. Entry barriers are falling. The missing piece is software that makes that cheaper hardware actually usable — fast, frictionless dev and prototyping cycles that let ideas get tested in days instead of weeks.

PyTorch didn't win because it had better algorithms. It won because it made the iteration cycle fast and intuitive. A larger community could experiment, more ideas got tried, and the field moved faster. The community became the moat.

That's the model. Psilia makes spatial perception accessible enough that a much broader group of people can build with it — and that community, over time, is what drives the platform forward.

---

## Psilia Edge — The First Building Block

Psilia Edge is the first product. It is the runtime layer: a spatial perception stack for Jetson, packaged to be easy to install, easy to operate, and easy to build on.

**What it does (v0):**

- Installs a containerized ROS spatial stack on Jetson in minutes
- Exposes a stable topic interface: `/psilia/depth`, `/psilia/pose`, `/psilia/image`
- Pairs and configures the Jetson from your laptop (SSH, WiFi, hotspot)
- Web-based control UI — monitor status, start/stop recording, manage sessions. Works from a phone.
- CLI for pairing, setup, data pull
- Minimal Python API for working with recorded MCAP data offline (topic access, time indexing, basic stats)

**What it doesn't do yet:** spatial intelligence layer, cloud sync, annotation tooling, fleet management. Those come next.

**Go-to-market: camera bundle.** The runtime and core algorithms are free and open source. The v0 go-to-market is a bundled USB stereo camera — cheap off-the-shelf hardware paired with our algorithms and runtime. The goal is not hardware margin. The goal is owning the first experience end-to-end: plug in the camera, run two commands, get spatial outputs running. A $30 camera performing at ZED quality. The bundle is distribution and a wedge, not the product. It gets installs, lowers the barrier to a first success, and puts users on the data flywheel from day one.

---

## Business Model

The runtime and core algorithms are free and open source. Monetization comes from premium services layered on top:

- **Cloud data sync and storage** — the natural next step once data is accumulating on device. Reliable, managed, robotics-native.
- **Data platform** — annotation, replay, evaluation, fleet-level management. What teams need once they have data at scale.
- **Premium algorithms** — advanced or domain-specific algorithms beyond the open-source baseline. Open-core model.

The open runtime gets adoption. The data platform and premium services get revenue.

---

## What Psilia Is Not

Psilia is not a camera product. It is not a ZED replacement or a cheaper Stereolabs. Stereolabs sells cameras; their SDK exists to make their hardware useful. Hardware drives everything in their model.

Psilia's value is in the runtime and what's built on top of it. Hardware is optional scaffolding.

---

## Who It's For

Initially: hobbyist roboticists, robotics and ML researchers, and early-stage startups building embodied AI products. These are the people feeling the pain today and building the products that will need this platform at scale tomorrow.

Hobbyists and researchers get adoption. Early-stage startups — and the companies they grow into — are the paying customers.

---

## Notes & Loose Threads

Unfinished thoughts and things worth revisiting.

- **Psilia company name/vision.** Current working line: "Psilia is the platform for perception and spatial intelligence at the edge." Still forming — keep revisiting as the product sharpens.

- **Weight of the problem areas.** We listed several pain points (field workflow, data sync, dev friction, algorithm lock-in, hardware cost) but haven't ranked them by importance or decided which are the primary hook for the pitch. Worth deciding.

- **"Enable the Ecosystem" section.** The PyTorch analogy is strong but the section still feels slightly separate from the rest of the doc. Might want to weave it into the vision more tightly rather than as a standalone section.

- **Algorithm strategy.** Open-source baseline algorithms, premium advanced algorithms as open-core upsell — this is implied but not fully stated. Worth being more explicit about what's open vs. what's premium and where the line is.

- **Data platform scope.** Cloud sync is the entry point, but annotation, replay, evaluation, fleet management is where it gets interesting. Haven't defined what "fleet management" means for the initial target (researchers/early startups) vs. later (scaling companies).

- **Target customer graduation path.** Hobbyist → PhD/researcher → early startup → scaling company. Each has different needs and willingness to pay. Worth mapping this out more explicitly for the investor version.

- **Hardware bundle specifics.** Which USB stereo camera? What's the actual cost and margin? "ZED quality at $30" needs to be validated — is that claim realistic?

- **Camera calibration.** Real pain point but unclear if it belongs in v0. Touches both the camera bundle (first-time setup experience) and core algorithms (calibration quality directly affects depth). Needs a decision.

---

## V0 Construction Sites

The four core focus areas for v0:

**1. Runtime.** The container, lifecycle, CLI, control UI, pairing, field workflow. The anchor layer.

**2. Core algorithms.** Depth estimation, pose. What runs inside the runtime. Robustness and reliability matter — off-the-shelf works most of the time, but most of the time isn't enough.

**3. Camera bundle.** Hardware selection, first-time setup experience, "plug in and it works." Nothing here yet.

**4. Data & dev tooling.** Data pull from device, MCAP API, offline dev workflow. Bridging the edge runtime and the dev environment.
