# Todo

## Keep in mind
- Hotspot and camera config in `psilia.yaml` are written once during `psilia runtime setup`
  and may be stale between boots if hardware changes (USB dongle swapped, camera unplugged).
  Live detection should eventually replace or validate the stored values at startup.


## Next up
- Continue code restructuring: finalize `runtime/` vs `device_manager/` split,
  clean up `runtime/commands.py` (start/stop/status/monitor logic placement),
  decide on `network/` ownership.
- Check ssh methods. What do we need the JetsonConn and LocalRunner for really? Might want to wrap output of calls like
  `docker build` in a rich   panel or something like that.
- Add `--dev` flag to runtime CLI (default from `PSILIA_DEV=1` env var). In dev mode:
  sync ROS workspace from repo into dev install path, skip/use local Docker image,
  optionally rebuild from local Dockerfile. Allows `psilia runtime start --dev` to
  pick up local node changes without a full bootstrap cycle.
