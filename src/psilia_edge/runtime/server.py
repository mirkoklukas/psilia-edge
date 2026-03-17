"""FastAPI server: static web UI + /api/* control endpoints."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from psilia_edge.runtime.config import get_api_port


# Assumes editable install: .../psilia-edge/src/psilia_edge/runtime/server.py
WEB_DIR = Path(__file__).resolve().parent.parent.parent.parent / "web"

app = FastAPI(title="Psilia Edge", docs_url=None, redoc_url=None)


# ── API routes (must be registered before the static file catch-all) ─────────


@app.get("/api/config")
async def api_config() -> JSONResponse:
    from psilia_edge.runtime.config import read_config

    return JSONResponse(dict(read_config()))


@app.get("/api/status")
async def api_status() -> JSONResponse:
    from psilia_edge.runtime.status import runtime_status

    return JSONResponse(runtime_status())


@app.post("/api/spatial/start")
async def api_spatial_start() -> JSONResponse:
    from psilia_edge.runtime.core import start_spatial_layer

    return JSONResponse(start_spatial_layer())


@app.post("/api/spatial/stop")
async def api_spatial_stop() -> JSONResponse:
    from psilia_edge.runtime.core import stop_spatial_layer

    return JSONResponse(stop_spatial_layer())


@app.get("/api/js/config.js", response_class=PlainTextResponse)
async def api_js_config() -> str:
    from psilia_edge.runtime.config import get_api_port, get_rosbridge_port

    return (
        f"window.PSILIA = {{"
        f" rosbridgePort: {get_rosbridge_port()},"
        f" apiPort: {get_api_port()}"
        f" }};"
    )


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
