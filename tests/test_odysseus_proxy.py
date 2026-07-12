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
        """GET /api/aos/health should return health status."""
        response = client.get("/api/aos/health")
        assert response.status_code == 200
        body = response.json()
        assert "status" in body

    def test_health_check_handles_unavailable(self, client: TestClient) -> None:
        """Health check should handle AOS engine unavailable."""
        response = client.get("/api/aos/health")
        assert response.status_code == 200
        body = response.json()
        # Should return unavailable or error status
        assert body.get("status") in ["ok", "unavailable", "error"]


class TestAOSStatusProxy:
    """Tests for AOS status proxy endpoint."""

    def test_status_returns_dict(self, client: TestClient) -> None:
        """GET /api/aos/status should return AOS status."""
        response = client.get("/api/aos/status")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, dict)

    def test_status_handles_unavailable(self, client: TestClient) -> None:
        """Status should handle AOS engine unavailable."""
        response = client.get("/api/aos/status")
        assert response.status_code == 200
        body = response.json()
        # Should return data or error status
        assert isinstance(body, dict)


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
