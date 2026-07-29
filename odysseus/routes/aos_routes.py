"""Odysseus routes — proxies harness dashboard API to the AOS engine.

The AOS backend runs separately (typically on port 7001). These routes
forward requests so the AOS SPA can serve the dashboard without CORS.
Includes a WebSocket proxy for live harness execution streaming.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx
import websockets
import websockets.exceptions
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

AOS_ENGINE_URL = os.getenv("AOS_ENGINE_URL", "http://127.0.0.1:7001")
AOS_ENGINE_WS_URL = AOS_ENGINE_URL.replace("http", "ws")
AOS_API_TOKEN = os.getenv("AOS_API_TOKEN", "")

_http_client: httpx.AsyncClient | None = None

# REST proxy router (mounted with /api/aos prefix by Odysseus)
router = APIRouter(prefix="/api/aos", tags=["aos"])

# WebSocket proxy router (mounted at root by Odysseus)
ws_router = APIRouter()


def _get_client() -> httpx.AsyncClient:
    """Lazy-initialize the httpx async client (first request)."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=AOS_ENGINE_URL,
            timeout=10.0,
        )
        logger.info("AOS proxy client initialized → %s", AOS_ENGINE_URL)
    return _http_client


def setup_aos_routes() -> APIRouter:
    """Return the REST proxy router (for backward compatibility)."""
    return router


# ── REST Proxy Endpoints ────────────────────────────────────────────────────


@router.get("/harnesses")
async def proxy_harnesses() -> Any:
    """Proxy GET /api/harnesses from AOS engine."""
    try:
        resp = await _get_client().get("/api/harnesses")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "AOS engine not running", "url": AOS_ENGINE_URL},
            status_code=502,
        )


@router.get("/summary")
async def proxy_summary() -> Any:
    """Proxy GET /api/summary from AOS engine."""
    try:
        resp = await _get_client().get("/api/summary")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "AOS engine not running", "url": AOS_ENGINE_URL},
            status_code=502,
        )


@router.get("/ws/stats")
async def proxy_ws_stats() -> Any:
    """Proxy GET /api/ws/stats from AOS engine."""
    try:
        resp = await _get_client().get("/api/ws/stats")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "AOS engine not running", "url": AOS_ENGINE_URL},
            status_code=502,
        )


@router.get("/health")
async def proxy_health() -> Any:
    """Proxy GET /health from AOS engine."""
    try:
        resp = await _get_client().get("/health")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "AOS engine not running", "url": AOS_ENGINE_URL},
            status_code=502,
        )


@router.get("/status")
async def proxy_status() -> Any:
    """Proxy GET /api/summary from AOS engine (alias for /summary)."""
    try:
        resp = await _get_client().get("/api/summary")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse(
            {"error": "AOS engine not running", "url": AOS_ENGINE_URL},
            status_code=502,
        )


# ── Deals Pipeline (local, no engine proxy needed) ──────────────────────────


@router.get("/deals")
async def get_deals(venture: str = "netso") -> Any:
    """Return deal pipeline for the given venture."""
    from pathlib import Path
    deals_path = Path(__file__).resolve().parent.parent.parent / "aos" / "ventures" / venture / "deals.json"
    if not deals_path.exists():
        return JSONResponse(content={"venture": venture, "deals": []})
    try:
        with open(deals_path) as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


@router.get("/deals/summary")
async def get_deals_summary(venture: str = "netso") -> Any:
    """Return deal pipeline summary (count per stage + total value)."""
    from pathlib import Path
    deals_path = Path(__file__).resolve().parent.parent.parent / "aos" / "ventures" / venture / "deals.json"
    if not deals_path.exists():
        return JSONResponse(content={"venture": venture, "stages": {}, "total_value": 0})
    try:
        with open(deals_path) as f:
            data = json.load(f)
        stages: dict[str, int] = {}
        total_value = 0.0
        for d in data.get("deals", []):
            s = d.get("stage", "unknown")
            stages[s] = stages.get(s, 0) + 1
            total_value += d.get("capacity_kw", 0) * d.get("ppa_rate", 0)
        return JSONResponse(content={"venture": venture, "stages": stages, "total_value": total_value})
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)


# ── WebSocket Proxy ─────────────────────────────────────────────────────────


@ws_router.websocket("/ws/harness/{harness_name}")
async def ws_harness_proxy(
    websocket: WebSocket,
    harness_name: str,
) -> None:
    """Bidirectional WebSocket proxy: browser ↔ Odysseus ↔ AOS engine.

    The browser connects to Odysseus, which bridges to the AOS engine's
    WebSocket endpoint. Messages flow both directions in real-time.
    Browser should NEVER connect directly to port 7001.
    """
    await websocket.accept()

    # Build target WS URL
    target_url = f"{AOS_ENGINE_WS_URL}/ws/harness/{harness_name}"
    if websocket.query_params:
        params = dict(websocket.query_params)
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        target_url = f"{target_url}?{query_string}"

    # Forward auth token if configured
    if AOS_API_TOKEN:
        separator = "&" if "?" in target_url else "?"
        target_url = f"{target_url}{separator}token={AOS_API_TOKEN}"

    logger.info("WS proxy connecting to: %s", target_url)

    try:
        async with websockets.connect(target_url) as upstream:
            # Bidirectional relay: browser ↔ AOS engine
            async def browser_to_engine() -> None:
                """Forward messages from browser to AOS engine."""
                try:
                    while True:
                        data = await websocket.receive_text()
                        await upstream.send(data)
                except WebSocketDisconnect:
                    logger.info("Browser disconnected from WS proxy")
                except Exception:
                    logger.exception("Browser → engine relay error")

            async def engine_to_browser() -> None:
                """Forward messages from AOS engine to browser."""
                try:
                    async for message in upstream:
                        if isinstance(message, bytes):
                            await websocket.send_bytes(message)
                        else:
                            await websocket.send_text(message)
                except websockets.exceptions.ConnectionClosed:
                    logger.info("AOS engine WS closed")
                except Exception:
                    logger.exception("Engine → browser relay error")

            # Run both directions concurrently; exit when either side closes
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(browser_to_engine()),
                    asyncio.create_task(engine_to_browser()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )

            # Cancel the surviving task
            for task in pending:
                task.cancel()
            for task in done:
                if task.exception():
                    logger.warning("Relay task error: %s", task.exception())

    except websockets.exceptions.InvalidURI:
        logger.error("Invalid WS target URL: %s", target_url)
        await websocket.send_json(
            {
                "event": "error",
                "message": "Invalid AOS engine URL",
            }
        )
        await websocket.close(code=1011)
    except websockets.exceptions.ConnectionClosedError:
        logger.error("Could not connect to AOS engine WS at %s", target_url)
        await websocket.send_json(
            {
                "event": "error",
                "message": "AOS engine unavailable",
            }
        )
        await websocket.close(code=1011)
    except Exception as exc:
        logger.exception("WS proxy error")
        try:
            await websocket.send_json(
                {
                    "event": "error",
                    "message": str(exc),
                }
            )
            await websocket.close(code=1011)
        except Exception:
            pass  # WebSocket may already be closed
