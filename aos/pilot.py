"""Restricted document pilot; deliberately does not mount the legacy API.

Run on loopback with ``uvicorn aos.pilot:app --host 127.0.0.1 --port 7001``.
Authentication is required by the document router. This entry point is not a
public-deployment authorization or a replacement for the broader API.
"""

from fastapi import FastAPI

from aos.prospects.routes import ProspectBodyLimit, router

app = FastAPI(
    title="Agent Harness document pilot",
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)
app.add_middleware(ProspectBodyLimit)
app.include_router(router)
