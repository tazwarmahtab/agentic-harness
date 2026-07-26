"""Odysseus — AOS Mission Control Dashboard server.

Serves the static dashboard and proxies API/WebSocket to the AOS engine.
"""
from __future__ import annotations

import os
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

# Load .env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

AOS_ENGINE_URL = os.getenv("AOS_ENGINE_URL", "http://localhost:7001")
DASHBOARD_DIR = Path(__file__).parent / "dashboard"
app = FastAPI(title="Odysseus — AOS Dashboard")

# Serve dashboard static files
app.mount("/static", StaticFiles(directory=DASHBOARD_DIR), name="static")

# API proxy to AOS engine
http_client = httpx.AsyncClient(base_url=AOS_ENGINE_URL, timeout=30.0)


@app.get("/")
async def dashboard_root() -> HTMLResponse:
    """Serve the dashboard HTML."""
    return FileResponse(DASHBOARD_DIR / "preview.html")


# Proxy all /api/* to AOS engine
@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy_api(request: Request, path: str):
    """Forward API requests to AOS engine."""
    url = f"/api/{path}"
    resp = await http_client.request(
        method=request.method,
        url=url,
        headers={k: v for k, v in request.headers.items() if k.lower() != "host"},
        content=await request.body(),
        params=request.query_params,
    )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type"),
    )


# Proxy WebSocket to AOS engine
@app.websocket("/ws/{path:path}")
async def proxy_ws(websocket: WebSocket, path: str):
    """Forward WebSocket connections to AOS engine."""
    await websocket.accept()
    aos_ws_url = f"ws://{AOS_ENGINE_URL.replace('http://', '')}/ws/{path}"

    try:
        async with websockets.connect(aos_ws_url) as aos_ws:
            # Bidirectional proxy
            async def client_to_server():
                try:
                    while True:
                        msg = await websocket.receive_text()
                        await aos_ws.send(msg)
                except WebSocketDisconnect:
                    pass

            async def server_to_client():
                try:
                    async for msg in aos_ws:
                        await websocket.send_text(msg)
                except WebSocketDisconnect:
                    pass

            import asyncio
            await asyncio.gather(client_to_server(), server_to_client())

    except Exception as e:
        await websocket.close(code=1011, reason=str(e))


# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "service": "odysseus-dashboard"}


if __name__ == "__main__":
    import websockets  # noqa: F401

    port = int(os.getenv("ODYSSEUS_PORT", "3000"))
    uvicorn.run(app, host="0.0.0.0", port=port)