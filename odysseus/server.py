"""Odysseus — AOS Mission Control Dashboard server.

Serves the dashboard SPA and proxies API/WebSocket requests to the AOS engine.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from odysseus.routes.aos_routes import setup_aos_routes, ws_router
from odysseus.routes.netso_routes import router as netso_router

DASHBOARD_DIR = Path(__file__).parent / "dashboard"

app = FastAPI(title="AOS Mission Control", version="1.0.0")

# Mount API routers FIRST (they take priority over static files)
app.include_router(setup_aos_routes())
app.include_router(netso_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "odysseus"}


@app.get("/")
async def serve_dashboard():
    """Serve the dashboard entry point."""
    index = DASHBOARD_DIR / "preview.html"
    if index.exists():
        return FileResponse(str(index))
    return FileResponse(str(DASHBOARD_DIR / "index.js"))


# Serve dashboard static files LAST (catch-all for JS, CSS, etc.)
# This must be after all explicit routes
app.mount("/", StaticFiles(directory=str(DASHBOARD_DIR)), name="dashboard")
