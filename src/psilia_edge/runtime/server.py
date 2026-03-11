"""FastAPI server: static web UI + /api/* control endpoints."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles


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


# ── Static files (catch-all, must come last) ─────────────────────────────────

app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="static")


def serve(host: str = "0.0.0.0", port: int = 8080) -> None:
    uvicorn.run(app, host=host, port=port, log_level="info")
