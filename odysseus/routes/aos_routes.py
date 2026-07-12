"""Odysseus WebSocket proxy — bridges browser ↔ AOS engine.

The browser connects to Odysseus WS, Odysseus bridges to AOS engine WS.
Browser should NEVER connect directly to port 7001.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("odysseus.routes.aos_routes")

router = APIRouter()

# AOS engine base URL (default: localhost:7001)
AOS_ENGINE_URL = os.getenv("AOS_ENGINE_URL", "http://localhost:7001")

# Auth token for AOS engine
AOS_API_TOKEN = os.getenv("AOS_API_TOKEN", "") or os.getenv("TAZOS_API_TOKEN", "")


@router.websocket("/ws/aos/{path:path}")
async def aos_websocket_proxy(
    websocket: WebSocket,
    path: str,
) -> None:
    """Proxy WebSocket connections from browser to AOS engine.

    This endpoint bridges the browser to the AOS engine, allowing:
    - Single origin for all connections
    - Auth token forwarding
    - Connection lifecycle management
    - Reverse-proxy compatibility

    Query params are forwarded to the AOS engine.
    """
    await websocket.accept()

    # Build target URL
    target_url = f"ws://localhost:7001/ws/{path}"
    if websocket.query_params:
        params = dict(websocket.query_params)
        query_string = "&".join(f"{k}={v}" for k, v in params.items())
        target_url = f"{target_url}?{query_string}"

    # Forward auth token if configured
    if AOS_API_TOKEN:
        separator = "&" if "?" in target_url else "?"
        target_url = f"{target_url}{separator}token={AOS_API_TOKEN}"

    logger.info("WebSocket proxy connecting to: %s", target_url)

    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "GET",
                target_url,
                headers={"Upgrade": "websocket", "Connection": "Upgrade"},
            ) as response:
                # This is a simplified proxy — in production, use a proper WS library
                # For now, we'll use httpx for HTTP proxying and handle WS separately
                logger.info("WebSocket proxy connected to AOS engine")
                # TODO: Implement full WebSocket bidirectional proxy
                await websocket.send_json({
                    "event": "connected",
                    "message": "WebSocket proxy connected to AOS engine",
                })

    except httpx.ConnectError:
        logger.error("Failed to connect to AOS engine at %s", AOS_ENGINE_URL)
        await websocket.send_json({
            "event": "error",
            "message": "AOS engine unavailable",
        })
        await websocket.close(code=1011)
    except Exception as exc:
        logger.exception("WebSocket proxy error")
        await websocket.send_json({
            "event": "error",
            "message": str(exc),
        })
        await websocket.close(code=1011)


@router.get("/api/aos/health")
async def aos_health_check() -> dict[str, Any]:
    """Check AOS engine health via HTTP proxy."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{AOS_ENGINE_URL}/health")
            return response.json()
    except httpx.ConnectError:
        return {"status": "unavailable", "error": "AOS engine not reachable"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@router.get("/api/aos/status")
async def aos_status() -> dict[str, Any]:
    """Get AOS engine status summary."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{AOS_ENGINE_URL}/api/summary")
            return response.json()
    except httpx.ConnectError:
        return {"status": "unavailable", "error": "AOS engine not reachable"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
