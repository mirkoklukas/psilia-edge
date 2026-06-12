# Todos

## Active

- [ ] Audit existing logging infrastructure (daemon log, ROS, FastAPI) and design unified approach across CLI, daemon, and ROS nodes. #refactor #logging
- [ ] Fix `device_decorator` to forward flags from `sys.argv` to remote commands. #fix #runtime
  - Currently forwards only `psilia runtime {func_name}`; flags like `--data-dir` get dropped under `-d`.
  - Fix: reconstruct invocation from `sys.argv`, strip `--device`/`-d` + value, pass to `run_on_device`.
- [ ] Implement home network detection — check Jetson is connected to `network.home` SSID via `nmcli`, expose in `/api/status` and Web UI. #feature #network
- [ ] Validate `psilia.yaml` / `runtime.yaml` schemas on read with clear error messages. #feature #config
- [ ] Implement pyudev hotplug daemon for USB device events (cameras, dongles). #feature #hotplug

### Depth pipeline
- [ ] Compute and publish confidence map alongside depth (`depth_node.py`). #feature
- [ ] Publish raw disparity on `/psilia/disparity` (`depth_node.py`). #feature
- [ ] Generalize `preview_node` to accept image-topic + fps lists, replacing `preview_node` and `depth_preview_node`. #refactor

### Open design questions

> Inline bodies below are scratchpad candidates — extract when ready.

- [ ] **`runtime.yaml` node-config shape** — flat dict vs ROS 2 launch YAML structure. Current take: keep flat — extra fields would be noise unless we want users to inject arbitrary nodes. #decision-needed #config

  **Ours (`runtime.yaml`):**
  ```yaml
  ros:
    nodes:
      depth_preview_node:
        parameters:
          max_depth: 3.0
          fps: 5
  ```
  **ROS 2 launch YAML:**
  ```yaml
  launch:
  - node:
      pkg: psilia_runtime
      exec: depth_preview_node
      name: depth_preview_node
      namespace: /psilia
      parameters:
      - max_depth: 3.0
      - fps: 5
  ```

- [ ] **Make `/psilia/info` honest** — hardcoded topic list breaks when nodes don't run. #decision-needed
  - Each node registers itself at startup (e.g. `/psilia/registry`), status node aggregates and re-broadcasts.
  - Introspect ROS graph at startup, filter `/psilia/*` topics with active publishers before broadcasting.
  - Delay `/psilia/info` broadcast slightly so nodes can come up, then discover live.
  - Treat `/psilia/info` as dynamic (re-publish periodically) rather than static.

## Backlog

_(empty)_
