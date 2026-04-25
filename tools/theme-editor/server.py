"""Theme editor dev tool — browser-based color picker for _theme.yaml."""

from __future__ import annotations

from pathlib import Path

import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

THEME_FILE = Path(__file__).resolve().parents[2] / "src" / "psilia_edge" / "runtime" / "_theme.yaml"

app = FastAPI()


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "index.html")


@app.get("/api/theme")
def get_theme():
    if THEME_FILE.exists():
        return yaml.safe_load(THEME_FILE.read_text()) or {}
    return {}


@app.put("/api/theme")
async def put_theme(data: dict):
    with open(THEME_FILE, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    return {"status": "ok"}


if __name__ == "__main__":
    print(f"Theme file: {THEME_FILE}")
    print(f"Open http://localhost:8090")
    uvicorn.run(app, host="0.0.0.0", port=8090)
