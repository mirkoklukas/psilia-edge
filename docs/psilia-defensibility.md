# On defensibility

## I. What about NVIDIA?

> "If the runtime is open source and gains real traction, what stops NVIDIA from absorbing this into the Jetson ecosystem directly?"

Nothing, and that would be great. More adoption feeds more data into the platform. The runtime is not the moat. It can't be, and it shouldn't be. It needs to be open and hackable. That's the point.

The moat is the data platform and the specialized algorithms built on top of it. Where is the incentive to build the data platform themselves? If Psilia succeeds, they benefit regardless. The strategic and easier thing to do would be to simply *buy* it. And even then, they'd buy it for the data.

There isn't really a moat that Google or NVIDIA could not, in principle, destroy. That's true for virtually every startup. The question is whether the problem structure favors them. Building a *foundation model* requires massive resources. Building a perception runtime and a data platform doesn't.


## II. The data flywheel

The runtime is the first thing that touches raw sensor input. Every team recording and processing data through the platform generates signal about real-world failure modes, environments, and edge cases. Over time, this compounds into datasets and benchmarks for perception on edge devices. Basically an *ImageNet* dataset for perception which drives algorithm development, and flows back into the runtime and its algorithmic core.


## III. The field has a blindspot

As outlined in the pitch, the dominant trend in AI is *scaling up*: bigger models, more compute. Edge-native perception runs orthogonal to that.

This mirrors the kind of question I worked on at MIT. A kid learns to drive a tractor in minutes, while a deep learning model needs millions of hours of data to learn the same task. That points to a fundamentally different paradigm: structured priors, data efficiency, probabilistic reasoning. Not just a smaller version of the same thing.

Edge-native algorithms are under-invested and under-built. It is a true blindspot, and it's where we want to position ourselves. To be fair, this is an unsolved problem and lies at the core of understanding learning and intelligence. At this stage, this is rather a head start, not a direct moat. But it tells us where to look and what to look for.
