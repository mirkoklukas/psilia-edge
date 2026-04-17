# Perception &amp; Spatial Intelligence for the Edge

## The Vision

*Psilia* is built on two convictions:

1. **Spatial perception is infrastructure.** Every team building on the edge today owns the entire stack themselves. That's unnecessary. There should be a reliable, hackable foundation teams can build on, so they can focus on what's unique to their mission.

2. **Edge-native perception is a distinct category.** Truly autonomous systems need to operate without connectivity, on constrained hardware, in unstructured environments. The dominant trend in AI is *scaling up*: bigger models and more compute. Edge-native perception runs orthogonal to that. These systems need perception that is fast, lightweight and reliable. This is especially pronounced in fields like agriculture, defense, and construction.

We are building the **perception and spatial intelligence platform** for the edge. The layer between raw sensors and the autonomy logic above, as well as the tooling around it. We start with a foundational layer and, as the platform matures, strengthen the algorithmic core underneath.

## The Problem

Building robotics applications and working with perception on edge hardware is harder than it should be. Three pain points stand out:

- **Getting started is a project.** Before you record a single useful frame: OS setup on Jetson, ROS installation, Docker, camera drivers, calibration, WiFi, SSH, launch scripts. Nothing ties it together. Everyone starts from scratch.

- **Fragmented workflow.** Field ops over SSH on your lap. Ad-hoc rsync scripts for data. Custom code to parse recordings. Constant jumping between edge runtime and dev environment. Slow, clumsy feedback loops.

- **Algorithm and hardware lock-in.** Proprietary stacks like ZED don't let you swap or customize algorithms. If depth or pose fails in your use case, you're fighting the SDK or rebuilding from scratch.

## The first Product: Psilia Edge

*Psilia Edge* is a spatial perception runtime for Jetson. Easy to install, easy to operate, easy to build on. Plug in a stereo camera, run one command, get reliable depth, pose, and spatial outputs in under 5 minutes. Hardware-agnostic, open source, and hackable.

A lightweight control UI handles device pairing, monitoring, recording, and data sync -- works from a phone. Recorded data is stored as open MCAP files and accessible via a Python API.

**The camera bundle.** The v0 go-to-market is a bundled USB stereo camera (~€100) paired with our runtime. A ZED Mini starts at €399. The goal is not hardware margin. The goal is owning the first experience end-to-end. ZED-quality spatial perception at a fraction of the cost. The bundle is distribution and a wedge, *not* the product.

## Business Model

The runtime and core algorithms are free and open source. The open runtime gets adoption. Revenue comes from premium services layered on top:

- **Data platform.** Cloud sync, post-processing, inspection, evaluation, annotation.
Tiered pricing (€200-1,000/month) targeting small teams and early-stage startups.

- **Premium algorithms.** Advanced or domain-specific algorithms beyond the open-source baseline. Open-core model.

Year 1 focus is shipping the runtime, a compelling showcase prototype, and getting it into 50-100 hands. Camera bundle revenue from early sales. Year 3 target: data platform live, €1M+ ARR from 100-200 paying teams.

## Market and Timing

Spatial perception is a core requirement for most robotics applications. No one owns this layer. ZED is hardware-first. NVIDIA provides blocks, not a runtime.

2M+ developers on NVIDIA Jetson, doubled in three years. $10B+ invested in robotics startups in 2025. Edge AI is a ~$25B market growing at 22% annually.

The target is early-stage startups, small teams, and researchers -- the people feeling the pain today and building the robotics companies of tomorrow. Large companies have already built internal pipelines.
Meeting early-stage teams now and growing with them is the strategy.

Robotics hardware is getting cheaper. Entry barriers are falling. But that alone doesn't accelerate the field, the tooling and abstractions around them do. PyTorch didn't win because it had better algorithms. It made the iteration cycle fast, which unlocked an entire community.

## Team

**Mirko Klukas, Ph.D.** -- Founder. PhD in Pure Mathematics with 10+ years solving deep technical problems from first principles across mathematics, perception, and AI. Research and engineering at MIT (Fiete Lab, Probabilistic Computing Group), Numenta, and IST Austria. Led perception research and engineering for CHI-Sight at MIT, pushing the boundaries of symbolic AI with GPU-accelerated inference models. Deep expertise in spatial AI: probabilistic SLAM, inverse graphics, spatial representations.

Actively building the founding team.

## The Ask

€350K on a SAFE. 12-15 months to seed-ready:

- Ship Psilia Edge v0 with camera bundle.
- Build a showcase prototype demonstrating the runtime in action.
- 50-100 active users with strong retention.
- Build the founding team.

Mirko Klukas, Ph.D. • Berlin, Germany • mirko.klukas@gmail.com
