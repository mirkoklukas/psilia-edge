# Psilia — Position Paper

> **Psilia is the perception and spatial intelligence platform for the edge.**


---

## The Problem

Building spatial AI on edge hardware is harder than it should be. The pain shows up at every stage:

◆ **Getting started.** Before you record a single useful frame in the field you've dealt with: OS setup on Jetson, ROS installation, Docker setup, camera drivers, camera calibration, WiFi and SSH configuration, writing launch scripts. Nothing ties it together. Everyone starts from scratch.

◆ **Field workflow.** In the field you're managing multiple terminals over SSH, manually starting ROS nodes, checking topic rates, starting and stopping recordings. If something breaks you're debugging over SSH with a laptop on your lap. The tooling assumes you're at a desk.

◇ **Data sync.** Getting recordings off the device and into a usable location — laptop, NAS, cloud — is another piece of infrastructure every team sets up from scratch. rsync scripts, USB transfers, maybe a cloud upload hook. One more thing you have to wire up and maintain yourself.

◇ **Working with data.** Once you have recordings, getting the data into a usable form is annoying. Parsing ROS bags, syncing topics by timestamp, post-processing and slicing recordings for algorithm testing, basic inspection to verify a recording is good. Tools exist but they're fragmented — you still end up writing your own code to bridge the gaps.

◇ **Two execution environments.** Embodied AI teams constantly jump between two worlds: the edge runtime (Jetson, ROS, sensors, deployment) and the dev environment (Python, notebooks, cloud, algorithm iteration). The boundary between them creates unnecessary friction. You iterate on an algorithm in a notebook, then have to redeploy to the device to test it in the real world (rewrite for performance, wrap into ROS nodes, rebuild, test on device). That round trip is clumsy. Feedback loops are slow.

◆ **Algorithm lock-in.** Proprietary stacks like the ZED SDK don't give you the hooks to customize or swap algorithms. If you want to change how depth or pose is computed, you're either fighting the SDK or rebuilding from scratch. That's fine until it isn't. Off-the-shelf algorithms work most of the time — but the acceptable failure rate depends entirely on the task. 95% might be fine for a demo, unacceptable for a deployed robot.

◆ **Hardware cost.** High-quality spatial perception today means expensive proprietary hardware — a [ZED Mini](https://www.stereolabs.com/store/products/zed-mini) starts at $399 (no global shutter at that price), the [ZED X series](https://www.stereolabs.com/products/zed-x) at $500+ (with global shutter). That an be real barrier for researchers, developers, and early-stage teams. Off-the-shelf USB stereo cameras like the [ELP USB Stereo Camera](https://www.amazon.com/ELP-60fps-Binocular-Lightburn-Synchronization/dp/B0D9793XZN) (~$100) include a global shutter and are available immediately at a fraction of the cost.

---

## The Vision

Spatial perception should be a starting point, not a project. Every team building spatial AI, from a grad student to an early-stage startup, should have a reliable, hackable foundation they can build on, so they can focus on what's unique to their mission.

Psilia's goal is to own the perception and spatial intelligence layer — the part of the stack that sits between raw sensors and the autonomy logic above.

At its core, Psilia is three things:
1. The perception and spatial intelligence layer you can rely on and build on, enabling teams to focus on what's unique to their mission.
2. High-quality spatial perception at a fraction of the hardware cost. Our algorithms let a $100 camera perform at ZED quality.
3. Fast, frictionless prototyping. We compress the plumbing/wiring so teams can test ideas in days, not weeks.

### Core Bets

The core architectural bet is a **runtime as a shared abstraction layer**. It works out of the box — plug in a camera, get spatial outputs — but it's also open and hackable. Swap the camera, swap the algorithm, change how things are configured — without fighting the system or rebuilding from scratch. The runtime is hardware-agnostic; the experience stays the same regardless of what's plugged in.

**Fast iteration as a force multiplier.** Tighter feedback loops produce better outcomes. Teams that can experiment quickly (i.e., record data, iterate on algorithms, redeploy, test) find better solutions faster. Psilia sets up the scaffolding so that cycle can be fast: the runtime handles the device, the tooling handles the data, and the dev API bridges the gap back to Python. The less time spent on plumbing/wiring between steps, the more time spent on the actual problem. The deeper Psilia is embedded in that cycle, the harder it is to replace.

**The data flywheel.** Once the runtime is deployed, data accumulates. Owning the sync, storage, and dev tooling around that data (i.e., post-processing, evaluation, annotation) ties users deeper into the ecosystem and feeds improvements back into the algorithms. It also closes the loop between the edge runtime and the dev environment: data flows out of the device, through Psilia's tooling, and back into algorithm iteration. Data is one of the most valuable assets a robotics team builds. It deserves proper infrastructure, not ad-hoc scripts.

**Algorithms as a retention driver.** As use cases grow, off-the-shelf algorithms hit their limits. Robust, high-quality algorithms — ones that handle real conditions, know their failure modes, and can be swapped without breaking downstream code — are what keep users on the runtime as their requirements get harder. Better algorithms are a differentiator and a reason to stay. They also decouple performance from hardware cost — better algorithms mean a $100 camera can do what expensive proprietary hardware does today.

Over time the goal is to be the platform every spatial AI team builds on, regardless of hardware.

### Target, Strategy, and Timing

Large robotics companies and well-funded labs already have internal pipelines for this. They've solved it for themselves. That's not the target.

The target is early-stage startups, small teams, and researchers — and even hobbyists — who currently have to own the entire stack themselves. Psilia factors out the spatial intelligence layer so they can focus on what's unique to their mission. These are also the teams building the robotics companies of tomorrow. Meeting them early and growing with them is the strategy.

Robotics hardware is getting cheaper. Entry barriers are falling. The missing piece is a runtime that turns cheap hardware into a foundation for spatial AI applications — ready out of the box, and something you can build on top of. Fast, frictionless dev and prototyping cycles that let ideas get tested in days instead of weeks.

PyTorch didn't win because it had better algorithms. It won because it made the iteration cycle fast and intuitive. A larger community could experiment, more ideas got tried, and the field moved faster. The community became the moat.

That's the model. Psilia makes spatial perception the new starting point — the baseline every team builds from, not the thing they spend months trying to get working reliably.

---

## The First Building Block: Psilia Edge

Psilia Edge is the first product. It is the runtime layer: a spatial perception stack for Jetson, packaged to be easy to install, easy to operate, and easy to build on.

> *Our goal is to be the first thing installed on Jetson. The Docker Desktop for spatial perception.*

### What it does (v0)

Psilia Edge has three parts: the runtime (including core algorithms), a control interface (CLI and web UI), and a minimal dev API.

- Installs a containerized ROS spatial stack on Jetson in minutes
- Runs core spatial algorithms and exposes outputs: `/psilia/depth`, `/psilia/pose`, `/psilia/image`
- Pairs and configures the Jetson from your laptop (SSH, WiFi, hotspot)
- Web-based control UI — monitor status, start/stop recording, manage sessions. Works from a phone.
- CLI for pairing, setup, data pull
- Minimal Python API for working with recorded MCAP data offline (topic access, time indexing, basic stats)


**What it doesn't do yet:** deeper spatial intelligence layer, cloud sync, data post-processing. Those come next.

### Go-to-market: Camera Bundle

The runtime and core algorithms are free and open source. The v0 go-to-market is a bundled USB stereo camera — cheap off-the-shelf hardware paired with our algorithms and runtime. The goal is not hardware margin. The goal is owning the first experience end-to-end: plug in the camera, run one command, get spatial outputs running. ZED-quality spatial perception at a fraction of the cost. The bundle is distribution and a wedge, not the product. It gets installs, lowers the barrier to a first success, and puts users on the data flywheel from day one.

---

## Business Model

The runtime and core algorithms are free and open source. Monetization comes from premium services layered on top:

- **Data platform** — starts with getting data off the device and into managed cloud storage, and grows into the tooling teams need once data is there: post-processing, inspection, evaluation, annotation.
- **Premium algorithms** — advanced or domain-specific algorithms beyond the open-source baseline. Open-core model.

The open runtime gets adoption. The data platform and premium services get revenue.

---

## What Psilia Is Not

Psilia is not a camera product. It overlaps with ZED in what it delivers — depth, pose, spatial outputs — but the approach is different. ZED's SDK exists to make their hardware useful; it's a means to sell cameras. Psilia's runtime is the product. It's open, hackable, and hardware-agnostic — bring any camera. And it goes further than perception outputs: the goal is to own the full cycle from runtime to data to dev tooling, not just the sensor interface.

- **Open vs closed** — you can swap algorithms, see what's happening, hack it
- **Hardware-agnostic vs hardware-locked** — Psilia works with any camera.
- **Platform vs product** — Psilia aims to be an ecosystem (runtime + data + dev tooling), ZED is a camera SDK

(TODO: Expand this section. Also address overlap with NVIDIA — Isaac, cuVSLAM, etc. NVIDIA provides building blocks but not a cohesive runtime; Psilia is the assembled, ready-to-use layer.)

---

## Who It's For

Initially: graduate students and developers, academic research teams, and early-stage startups building embodied AI products. These are the people feeling the pain today and building the products that will need this platform at scale tomorrow.

Graduate students, developers, and academic research teams get adoption — and they build the next wave of startups. Early-stage startups — and the companies they grow into — are the paying customers.

See also: [Target, Strategy, and Timing](#target-strategy-timing) in the Vision section.

---

## One-Liners & Pitch Lines

Lines worth keeping for pitch decks, one-pagers, and conversations.

- "ZED-quality spatial perception at a fraction of the cost."
- "A $100 camera performing at ZED quality."
- "Nothing ties it together. Everyone starts from scratch."
- "The tooling assumes you're at a desk."
- "Psilia is the perception and spatial intelligence platform for the edge."
- "The Docker Desktop for spatial perception."
- "The easiest way to get spatial perception running on Jetson."
- "Runtime-first, not camera-first. Experience is hardware agnostic."
- "Simpler, open, and hackable."
- "Edge-native perception for builders and developers."
- "We are not replacing ZED. We are replacing ROS setup pain."
- "It kind of feels like ZED but easier."
- "It works out of the box, but it's also hackable."
- "Compress the plumbing to near-zero and you unlock a much larger community of people who can experiment, iterate, and push boundaries."
- "At the moment everyone needs to own the whole stack themselves. Psilia factors out the spatial intelligence layer so you can focus on what's unique to your mission."
- "Like AWS factored out servers, or PyTorch factored out the training loop — Psilia factors out spatial intelligence."
- "Psilia makes spatial perception the new starting point — the baseline every team builds from, not the thing they spend months trying to get working reliably."
- "Plug in a stereo camera, run one command, and get reliable depth, pose, and spatial outputs in under 5 minutes."
- "No ROS wrangling required."
- "No manual node orchestration, no bash scripts. Unless you want to. Everything is open and accessible."
- "Psilia commoditizes spatial intelligence — making it accessible to anyone building with embodied AI, from independent builders to early-stage startups."

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

- **Algorithm reliability — deeper angle.** The reliability bar is task-dependent: 95% might be fine for a demo, unacceptable for a deployed robot. The pain is compounded by lock-in — if the algorithm fails in your use case you have no recourse. Systems should know their own boundaries: uncertainty quantification, knowing when to trust the output. Probabilistic models have an edge here. Worth exploring as a differentiator in the algorithms construction site.

- **Earlier elevator pitch notes.** At the core psilia does the following: (1) Psilia makes spatial perception the new starting point — the baseline every team builds from, not the thing they spend months trying to get working reliably. (2) Psilia enables tight iteration/prototyping cycles. (data flywheel?) (3) "ZED-quality spatial perception at a fraction of the cost."/"Our algorithms let a $100 camera perform at ZED quality." **=> So that means (\*) it's the spatial AI layer you can build/rely on. (\*\*) It does it at the fraction of the cost of other offerings. And (\*\*\*) we provide the additional tooling and abstraction to close your prototyping cycle.** The target is early-stage startups, small teams, and researchers — who currently have to own the entire stack themselves. Psilia factors out the spatial intelligence layer so they can focus on what's unique to their mission. These are also the teams building the robotics companies of tomorrow. Meeting them early and growing with them is the strategy.

---

## V0 Construction Sites

The four core focus areas for v0:

**1. Runtime.** The container, lifecycle, CLI, control UI, pairing, field workflow. The anchor layer.

**2. Core algorithms.** Depth estimation, pose. What runs inside the runtime. Robustness and reliability matter — off-the-shelf works most of the time, but most of the time isn't enough.

**3. Camera bundle.** Hardware selection, first-time setup experience, "plug in and it works." Nothing here yet.

**4. Data & dev tooling.** Data pull from device, MCAP API, offline dev workflow. Bridging the edge runtime and the dev environment.
