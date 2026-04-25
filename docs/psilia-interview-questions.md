# Psilia — Customer Interview Questions


## Context


- What are you building? What's the overall task the robot needs to accomplish, and what's the core perception task that enables it?
- What hardware are you running on?
- How big is the team? Who owns the perception stack?
- How long have you been working on this?
- What are the key constraints you're operating under?
  - Connectivity; how much can live in the cloud vs.on device;
  - Latency; does perception need to be real-time
  - Environment; indoors/outdoors, structured/unstructured, weather, lighting.
- What does "reliable enough" mean to you


## Perception stack

- How did you end up with your current perception stack? How were those decisions made?
- What made you choose the particular spatial perception algorithms you currently run?
  - Did you benchamark/evaluate alternatives?
- What does your stack actually look like? Are you running ROS? What are the main components?
- Have you ever hit a case where an off-the-shelf solution failed and you had to fix or rebuild it?
- How do you deploy software to the device? What does that process look like?
  - Flashing images? Docker containers? Direct installs?
  - In ROS environments, how do they manage launch files?
  - How long does a deploy take? How often do they do it?


## Dev cycle

- Walk me through a typical week or even iteration cycle. What does iteration look like?
- Where do you develop; on device, on your laptop.
- How do you test? In simulation? Against internet data, your own data?
- How do you primarily communicate with the device? SSH, a web UI, ROS tooling, Foxglove, something custom?
- How long does it take from a code change to knowing if it worked?
- How do you deploy to the device? What does that process look like?
  - How do you manage versions across multiple devices? Does that ever cause problems?
- What does testing an algorithm change look like end to end. Say you've been iterating in a Jupyter notebook and want to live test it on the device. How long does that cycle take?
- How long would it take to swap out a component of the pipeline, say visual odometry, without breaking everything else?


## Protyping

- How long did it take to set up the first prototype that could move and navigate so you could record the first task-relevant live data? What were the main pain points?
- How does that compare to subsequent prototypes? Did it get faster, or do you start from scratch each time?
- How often do you collect data in the field with your prototype? What would it take to do it more often?
- How do you record data in the field? How do you manage sessions?
- How do you get data off the device? How often do you actually do it?
- How do you manage your data? What is your workflow to pull data from the device? local, cloud, somewhere else? Checking if files are broken?
- Are you actively building custom training datasets to improve your models?
  - How? Annotation/Labeling? How do you identify/filter long-tail edge cases?
- What do you do with recorded data? Do you ever go back and inspect it?
  - How do you inspect it? Can you quickly inspect on the cloud storage?
  - Are you actively looking for failure cases and long-tail edge cases in your recordings, or mostly spot-checking that things looked roughly right?
  - Are you using recorded data to build internal benchmarks, or is evaluation still eyeball-based?
- Have you ever had a failure in the field you couldn't reproduce locally or in the lab?


## Testing and benchmarking

- How do you know if a change made things better or worse?
- Do you have any benchmarks or regression tests? How did they come about?
  - How did you build them? What data?
  - If not: is that a conscious choice or something they just never got to?
- Have you ever shipped something that worked in simulation but failed in the field?
  - When did you realize how did you fix it?
- Have you ever had something that worked fine for a while and then just stopped working? Running into an edge case or for no obvious cause?
- How do you recognize that something is failing or degrading? Do you have any monitoring or is it reactive?
- When something does fail in the field, what does the debugging process actually look like? How do you fix it?
  - Is there a systematic process; pull data, reproduce, fix, redeploy? or is it pure firefighting?
- When perception fails during a live deployment, what does the robot do? Does it recover, stop, or behave unpredictably?
  - Have you ever had an unsafe or damaging failure in the field? What happened?
- What does "good enough" mean for your perception stack right now?

## Workarounds

- What have you had to build yourself that you wish existed?
- What do you use off the shelf vs. build internally?
- What's the most painful thing you've just learned to live with?


## Value

- If you could fix one thing in your current workflow what would it be?
- Have you ever paid for tooling or infrastructure? What made it worth it?
- What would it need to do for you to seriously consider paying for it?
