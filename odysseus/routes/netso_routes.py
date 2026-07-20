"""Odysseus proxy routes — Netso customer dashboard API."""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

AOS_ENGINE_URL = os.getenv("AOS_ENGINE_URL", "http://127.0.0.1:7001")

_http_client: httpx.AsyncClient | None = None

router = APIRouter(prefix="/api/netso", tags=["netso"])


def _get_client() -> httpx.AsyncClient:
    """Lazy-initialize the httpx async client (first request)."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(base_url=AOS_ENGINE_URL, timeout=10.0)
    return _http_client


@router.get("/customers/{site_id}/generation")
async def proxy_generation(site_id: str) -> Any:
    """Proxy GET /api/netso/customers/{site_id}/generation from AOS engine."""
    try:
        resp = await _get_client().get(f"/api/netso/customers/{site_id}/generation")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"error": "AOS engine not running"}, status_code=502)


@router.get("/customers/{site_id}/savings")
async def proxy_savings(site_id: str) -> Any:
    """Proxy GET /api/netso/customers/{site_id}/savings from AOS engine."""
    try:
        resp = await _get_client().get(f"/api/netso/customers/{site_id}/savings")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"error": "AOS engine not running"}, status_code=502)


@router.get("/customers/{site_id}/billing")
async def proxy_billing(site_id: str) -> Any:
    """Proxy GET /api/netso/customers/{site_id}/billing from AOS engine."""
    try:
        resp = await _get_client().get(f"/api/netso/customers/{site_id}/billing")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"error": "AOS engine not running"}, status_code=502)


@router.get("/portfolio")
async def proxy_portfolio() -> Any:
    """Proxy GET /api/netso/portfolio from AOS engine."""
    try:
        resp = await _get_client().get("/api/netso/portfolio")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"error": "AOS engine not running"}, status_code=502)


@router.get("/financials")
async def proxy_financials() -> Any:
    """Proxy GET /api/netso/financials from AOS engine."""
    try:
        resp = await _get_client().get("/api/netso/financials")
        return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except httpx.ConnectError:
        return JSONResponse({"error": "AOS engine not running"}, status_code=502)
