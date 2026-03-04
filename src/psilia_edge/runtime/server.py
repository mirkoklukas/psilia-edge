"""FastAPI server: static web UI + /api/* control endpoints."""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from psilia_edge.network.probe import list_interfaces

WEB_DIR = Path(__file__).parent.parent / "web"

app = FastAPI(title="Psilia Edge", docs_url=None, redoc_url=None)


# ── API routes (must be registered before the static file catch-all) ─────────


@app.get("/api/status")
async def api_status() -> JSONResponse:
    interfaces = list_interfaces()
    return JSONResponse(
        {
            "psilia_edge": "running",
            "network": [
                {
                    "name": i.name,
                    "type": i.type,
                    "state": i.state,
                    "ip": i.ip4,
                    "connection": i.connection,
                }
                for i in interfaces
            ],
            "docker": "unknown",    # TODO: check docker status
            "ros_runtime": "unknown",  # TODO: check container status
        }
    )


# ── Static files (catch-all, must come last) ─────────────────────────────────

app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="static")


def serve(host: str = "0.0.0.0", port: int = 8080) -> None:
    uvicorn.run(app, host=host, port=port, log_level="info")
