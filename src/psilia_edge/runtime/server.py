"""FastAPI server: static web UI + /api/* control endpoints."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from psilia_edge.runtime.config import get_api_port


# Assumes editable install: .../psilia-edge/src/psilia_edge/runtime/server.py
WEB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "web"

# ── SSE broadcast ─────────────────────────────────────────────────────────────

_clients: list[asyncio.Queue] = []


@asynccontextmanager
async def _lifespan(app: FastAPI):
    asyncio.create_task(_status_broadcaster())
    yield


app = FastAPI(title="Psilia Edge", docs_url=None, redoc_url=None, lifespan=_lifespan)


async def _status_broadcaster() -> None:
    """Poll runtime_status() every second and push to all SSE clients on change.

    Diffs against a stripped version of the status (volatile fields like uptime
    excluded) so we only push on meaningful state changes.
    """
    last_comparable: dict | None = None
    while True:
        await asyncio.sleep(1.0)
        if not _clients:
            continue
        try:
            current = await asyncio.to_thread(_get_status)
            comparable = _strip_volatile(current)
            if comparable != last_comparable:
                last_comparable = comparable
                payload = json.dumps(current)
                for q in list(_clients):
                    await q.put(payload)
        except Exception:
            pass


def _strip_volatile(status: dict) -> dict:
    """Return a copy of status with volatile fields removed for diffing."""
    import copy

    s = copy.deepcopy(status)
    s.get("base", {}).pop("uptime", None)
    return s


def _get_status() -> dict:
    from psilia_edge.runtime.status import runtime_status

    return runtime_status(uptime=True, spatial_running=True, spatial_requirements=True)


# ── API routes (must be registered before the static file catch-all) ─────────


@app.get("/api/events")
async def api_events() -> StreamingResponse:
    q: asyncio.Queue = asyncio.Queue()
    _clients.append(q)

    # Push current state immediately on connect
    try:
        current = await asyncio.to_thread(_get_status)
        await q.put(json.dumps(current))
    except Exception:
        pass

    async def stream() -> AsyncIterator[str]:
        try:
            while True:
                data = await q.get()
                yield f"data: {data}\n\n"
        finally:
            _clients.remove(q)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/config")
async def api_config() -> JSONResponse:
    from psilia_edge.runtime.config import read_config

    return JSONResponse(dict(read_config()))


@app.get("/api/status")
async def api_status(
    uptime: bool = True,
    base: bool = True,
    spatial_running: bool = True,
    spatial: bool = True,
    spatial_requirements: bool = True,
    server: bool = True,
    docker: bool = True,
    ros: bool = True,
    storage: bool = True,
    hotspot: bool = True,
) -> JSONResponse:
    from psilia_edge.runtime.status import runtime_status

    status = await asyncio.to_thread(
        runtime_status,
        uptime=uptime,
        base=base,
        spatial_running=spatial_running,
        spatial=spatial,
        spatial_requirements=spatial_requirements,
        server=server,
        docker=docker,
        ros=ros,
        storage=storage,
        hotspot=hotspot,
    )
    return JSONResponse(status)


@app.post("/api/spatial/start")
async def api_spatial_start(force: bool = False) -> JSONResponse:
    from psilia_edge.runtime.core import SpatialRequirementsError, start_spatial_layer

    try:
        return JSONResponse(await asyncio.to_thread(start_spatial_layer, force))
    except SpatialRequirementsError as e:
        ctx = e.result
        checks = {}
        for key in ("container", "camera", "camera.calibration", "hotspot"):
            node = ctx[key]
            checks[key] = {"ok": node.ok, "detail": node.detail}
        return JSONResponse({"status": "error", "checks": checks}, status_code=412)


@app.post("/api/spatial/stop")
async def api_spatial_stop() -> JSONResponse:
    from psilia_edge.runtime.core import stop_spatial_layer

    return JSONResponse(await asyncio.to_thread(stop_spatial_layer))


@app.get("/api/js/config.js", response_class=PlainTextResponse)
async def api_js_config() -> str:
    from psilia_edge.runtime.config import get_api_port, get_rosbridge_port

    return (
        f"window.PSILIA = {{"
        f" rosbridgePort: {get_rosbridge_port()},"
        f" apiPort: {get_api_port()}"
        f" }};"
    )


@app.get("/api/recordings")
async def api_recordings() -> JSONResponse:
    from psilia_edge.runtime.config import get_data_dir

    data_dir = get_data_dir()
    files = []
    for mcap in sorted(
        data_dir.glob("**/*.mcap"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        stat = mcap.stat()
        files.append(
            {
                "name": mcap.stem,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            }
        )
    return JSONResponse(files)


@app.get("/api/network/ping")
async def api_network_ping() -> JSONResponse:
    return JSONResponse({"ok": True})


@app.get("/api/network/probe")
async def api_network_probe(size: int = 100_000):
    from fastapi.responses import Response

    size = min(max(size, 0), 5_000_000)
    return Response(content=bytes(size), media_type="application/octet-stream")


# ── Static files (catch-all, must come last) ─────────────────────────────────

app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="static")


def serve(host: str = "0.0.0.0", port: int | None = None) -> None:
    if port is None:
        port = get_api_port()
    uvicorn.run(app, host=host, port=port, log_level="info")
