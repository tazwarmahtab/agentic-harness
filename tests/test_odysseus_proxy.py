"""Tests for Odysseus WebSocket proxy and HTTP endpoints."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from odysseus.routes.aos_routes import router


# Create test app with the router
def create_test_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture(autouse=True)
def _reset_httpx_client():
    """Reset the cached httpx client before each test to avoid event loop leaks."""
    import odysseus.routes.aos_routes as mod
    mod._http_client = None
    yield
    mod._http_client = None


@pytest.fixture
def client() -> TestClient:
    """Create test client for odysseus routes."""
    app = create_test_app()
    return TestClient(app)


class TestAOSHealthProxy:
    """Tests for AOS health check proxy endpoint."""

    def test_health_check_returns_dict(self, client: TestClient) -> None:
        """GET /api/aos/health returns 502 when AOS engine is not running."""
        response = client.get("/api/aos/health")
        assert response.status_code == 502
        body = response.json()
        assert "error" in body

    def test_health_check_handles_unavailable(self, client: TestClient) -> None:
        """Health check returns 502 with engine-unavailable error body."""
        response = client.get("/api/aos/health")
        assert response.status_code == 502
        body = response.json()
        assert body["error"] == "AOS engine not running"


class TestAOSStatusProxy:
    """Tests for AOS status proxy endpoint."""

    def test_status_returns_dict(self, client: TestClient) -> None:
        """GET /api/aos/status returns 502 when AOS engine is not running."""
        response = client.get("/api/aos/status")
        assert response.status_code == 502
        body = response.json()
        assert isinstance(body, dict)
        assert "error" in body

    def test_status_handles_unavailable(self, client: TestClient) -> None:
        """Status returns 502 with engine-unavailable error body."""
        response = client.get("/api/aos/status")
        assert response.status_code == 502
        body = response.json()
        assert body["error"] == "AOS engine not running"


class TestWebSocketProxy:
    """Tests for WebSocket proxy endpoint."""

    def test_ws_proxy_endpoint_exists(self) -> None:
        """WebSocket proxy endpoint should be registered."""
        from odysseus.routes.aos_routes import ws_router
        routes = [route.path for route in ws_router.routes]
        assert "/ws/harness/{harness_name}" in routes

    def test_ws_proxy_has_correct_methods(self) -> None:
        """WebSocket proxy should accept WebSocket connections."""
        from odysseus.routes.aos_routes import ws_router
        for route in ws_router.routes:
            if hasattr(route, "path") and route.path == "/ws/harness/{harness_name}":
                assert hasattr(route, "endpoint")
                break
        else:
            pytest.fail("WebSocket proxy route not found")
