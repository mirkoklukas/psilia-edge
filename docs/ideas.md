# Ideas & Brainstorming

A loose collection of potential directions, extensions, and things worth exploring.
Not a todo list — just a place to think out loud.

---

## /psilia/info — keeping it honest

The static info topic currently hardcodes the list of topics Psilia publishes.
This is a promise to other nodes — but if a node isn't running (e.g. depth_node
disabled, camera not connected), the promise is broken.

Need a way to keep /psilia/info in sync with what is actually being published.
Some directions worth exploring:

- Have each node register itself at startup (e.g. publish to a /psilia/registry
  topic or write to a shared state). The status node aggregates and re-broadcasts.
- Introspect the ROS graph at startup (ros2 topic list) and filter for /psilia/*
  topics that have active publishers before broadcasting /psilia/info.
- Delay the /psilia/info broadcast slightly to let all nodes come up, then
  discover what's actually live before publishing.
- Treat /psilia/info as dynamic (re-publish periodically) rather than truly static,
  so it reflects the current state of the graph.
