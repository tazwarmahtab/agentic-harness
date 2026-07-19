"""Odysseus route modules."""

from odysseus.routes.aos_routes import setup_aos_routes, ws_router
from odysseus.routes.netso_routes import router as netso_router

__all__ = ["setup_aos_routes", "ws_router", "netso_router"]
