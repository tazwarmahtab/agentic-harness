"""Tests for API authentication, connection limiting, and safety."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import MagicMock, AsyncMock, patch

import pytest
from starlette.testclient import TestClient

from aos.api import app


class TestTokenAuth:
    """Tests for WebSocket token-based authentication."""

    def test_token_env_var_reads_correctly(self) -> None:
        """AOS_API_TOKEN should reflect the environment variable."""
        with patch.dict(os.environ, {"AOS_API_TOKEN": "test-secret-123"}):
            # Re-import to pick up the env var
            import importlib
            import aos.api

            importlib.reload(aos.api)
            assert aos.api.AOS_API_TOKEN == "test-secret-123"
            # Restore
            importlib.reload(aos.api)

    def test_token_defaults_to_empty(self) -> None:
        """When AOS_API_TOKEN is unset, it defaults to empty string."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key entirely
            os.environ.pop("AOS_API_TOKEN", None)
            os.environ.pop("AOS_API_TOKEN", None)
            import importlib
            import aos.api

            importlib.reload(aos.api)
            assert aos.api.AOS_API_TOKEN == ""
            # Restore
            importlib.reload(aos.api)

    def test_ws_rejects_bad_token(self) -> None:
        """WebSocket should close with 4001 when token is wrong."""
        with patch.dict(os.environ, {"AOS_API_TOKEN": "correct-token"}):
            import importlib
            import aos.api

            importlib.reload(aos.api)

            mock_ws = MagicMock()
            mock_ws.query_params = {"token": "wrong-token"}
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()
            mock_ws.close = AsyncMock()

            # Import the handler after reload
            from aos.api import harness_ws
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(harness_ws(mock_ws, "executive"))
            finally:
                loop.close()

            mock_ws.accept.assert_called_once()
            mock_ws.send_json.assert_called_once_with(
                {"event": "error", "message": "Unauthorized"}
            )
            mock_ws.close.assert_called_once_with(code=4001)

            # Restore
            importlib.reload(aos.api)

    def test_ws_accepts_correct_token(self) -> None:
        """WebSocket should proceed when token matches."""
        with patch.dict(os.environ, {"AOS_API_TOKEN": "correct-token"}):
            import importlib
            import aos.api

            importlib.reload(aos.api)

            mock_ws = MagicMock()
            mock_ws.query_params = {"token": "correct-token"}
            mock_ws.accept = AsyncMock()
            # _resolve_bundle will fail (no harness), but that's fine —
            # we just need to verify it got past the auth check
            mock_ws.send_json = AsyncMock()
            mock_ws.close = AsyncMock()

            from aos.api import harness_ws
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                # Should NOT hit the auth rejection — will fail later on bundle resolution
                loop.run_until_complete(harness_ws(mock_ws, "nonexistent-harness"))
            except Exception:
                pass
            finally:
                loop.close()

            # Auth passed — no 4001 close (close may be called by error handler later)
            for call in mock_ws.close.call_args_list:
                if call.kwargs.get("code") == 4001:
                    pytest.fail("Auth rejection (4001) should not have been called")

            # Restore
            importlib.reload(aos.api)


class TestConnectionLimiterWiring:
    """Tests for WebSocket connection limiter integration in the API layer."""

    @patch("aos.api.AOS_API_TOKEN", "")
    @patch("aos.api._ws_limiter")
    def test_ws_rejects_when_at_capacity(self, mock_limiter: MagicMock) -> None:
        """WebSocket should close with 4029 when connection limit is reached."""
        mock_limiter.try_acquire.return_value = False

        mock_ws = MagicMock()
        mock_ws.query_params = {}
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.close = AsyncMock()

        from aos.api import harness_ws

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(harness_ws(mock_ws, "test-harness"))
        finally:
            loop.close()

        mock_limiter.try_acquire.assert_called_once()
        mock_ws.send_json.assert_called_once_with(
            {
                "event": "error",
                "message": "Connection limit reached. Try again later.",
            }
        )
        mock_ws.close.assert_called_once_with(code=4029)

    @patch("aos.api.AOS_API_TOKEN", "")
    @patch("aos.api._resolve_bundle", return_value=(None, "unknown", "test-harness"))
    @patch("aos.api._ws_limiter")
    def test_ws_acquires_and_releases_slot(
        self,
        mock_limiter: MagicMock,
        mock_resolve: MagicMock,
    ) -> None:
        """Connection slot should be released in the finally block after execution."""
        mock_limiter.try_acquire.return_value = True

        mock_ws = MagicMock()
        mock_ws.query_params = {}
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.close = AsyncMock()

        from aos.api import harness_ws

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(harness_ws(mock_ws, "test-harness"))
        finally:
            loop.close()

        mock_limiter.try_acquire.assert_called_once()
        mock_limiter.release.assert_called_once()
        # Verify close was called (in finally block)
        mock_ws.close.assert_called()

    def test_ws_stats_endpoint(self) -> None:
        """GET /api/ws/stats should return active and max connection counts."""
        client = TestClient(app)
        response = client.get("/api/ws/stats")

        assert response.status_code == 200
        body = response.json()
        assert "active_connections" in body
        assert "max_connections" in body
        assert isinstance(body["active_connections"], int)
        assert isinstance(body["max_connections"], int)
        assert body["max_connections"] == 10
        assert body["active_connections"] >= 0


class TestDashboardEndpoints:
    """Tests for dashboard REST endpoints."""

    def test_health_returns_ok(self) -> None:
        """GET /health should return status ok."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "aos-engine"

    def test_harnesses_returns_list(self) -> None:
        """GET /api/harnesses should return a list of harness dicts."""
        client = TestClient(app)
        response = client.get("/api/harnesses")
        assert response.status_code == 200
        harnesses = response.json()
        assert isinstance(harnesses, list)
        assert len(harnesses) > 0
        # Each harness should have required keys
        for h in harnesses:
            assert "id" in h
            assert "name" in h
            assert "venture" in h

    def test_summary_returns_kpis(self) -> None:
        """GET /api/summary should return dashboard KPIs."""
        client = TestClient(app)
        response = client.get("/api/summary")
        assert response.status_code == 200
        body = response.json()
        assert "harnesses" in body
        assert "tests" in body
        assert "memory_domains" in body
        assert "financial_accuracy" in body
        assert isinstance(body["harnesses"], int)
        assert body["harnesses"] > 0
        assert isinstance(body["tests"], int)


class TestResolveBundleValidation:
    """Tests for harness name validation in _resolve_bundle."""

    def test_rejects_path_traversal(self) -> None:
        """_resolve_bundle should reject harness names with path traversal."""
        from aos.api import _resolve_bundle

        bundle, venture_id, harness_id = _resolve_bundle("../../etc/passwd")
        assert bundle is None
        assert harness_id == "../../etc/passwd"

    def test_rejects_absolute_path(self) -> None:
        """_resolve_bundle should reject absolute path harness names."""
        from aos.api import _resolve_bundle

        bundle, venture_id, harness_id = _resolve_bundle("/etc/passwd")
        assert bundle is None

    def test_rejects_special_characters(self) -> None:
        """_resolve_bundle should reject names with shell metacharacters."""
        from aos.api import _resolve_bundle

        bundle, venture_id, harness_id = _resolve_bundle("exec; rm -rf /")
        assert bundle is None

    def test_allows_valid_name(self) -> None:
        """_resolve_bundle should accept valid harness names."""
        from aos.api import _resolve_bundle

        # "nonexistent" is a valid name format (just doesn't exist on disk)
        bundle, venture_id, harness_id = _resolve_bundle("nonexistent")
        assert bundle is None  # not found, but name was valid
        assert harness_id == "nonexistent"


class TestRESTAuthMiddleware:
    """Tests for REST approval endpoint authentication (P0-1 fix)."""

    def test_approvals_rejects_no_token(self) -> None:
        """GET /api/approvals should return 401 when AOS_API_TOKEN is set but no auth header."""
        with patch.dict(os.environ, {"AOS_API_TOKEN": "secret-123"}):
            import importlib
            import aos.api

            importlib.reload(aos.api)
            try:
                client = TestClient(app)
                response = client.get("/api/approvals")
                assert response.status_code == 401
                assert "Missing Authorization" in response.json()["detail"]
            finally:
                importlib.reload(aos.api)

    def test_approvals_rejects_bad_token(self) -> None:
        """GET /api/approvals should return 401 when token is wrong."""
        with patch.dict(os.environ, {"AOS_API_TOKEN": "secret-123"}):
            import importlib
            import aos.api

            importlib.reload(aos.api)
            try:
                client = TestClient(app)
                response = client.get(
                    "/api/approvals",
                    headers={"Authorization": "Bearer wrong-token"},
                )
                assert response.status_code == 401
                assert "Invalid token" in response.json()["detail"]
            finally:
                importlib.reload(aos.api)

    def test_approvals_rejects_bad_format(self) -> None:
        """GET /api/approvals should return 401 for non-Bearer auth format."""
        with patch.dict(os.environ, {"AOS_API_TOKEN": "secret-123"}):
            import importlib
            import aos.api

            importlib.reload(aos.api)
            try:
                client = TestClient(app)
                response = client.get(
                    "/api/approvals",
                    headers={"Authorization": "Basic secret-123"},
                )
                assert response.status_code == 401
                assert "Invalid Authorization format" in response.json()["detail"]
            finally:
                importlib.reload(aos.api)

    def test_approvals_accepts_valid_token(self) -> None:
        """GET /api/approvals should return 200 when correct Bearer token is provided."""
        with patch.dict(os.environ, {"AOS_API_TOKEN": "secret-123"}):
            import importlib
            import aos.api

            importlib.reload(aos.api)
            try:
                client = TestClient(app)
                response = client.get(
                    "/api/approvals",
                    headers={"Authorization": "Bearer secret-123"},
                )
                assert response.status_code == 200
                assert isinstance(response.json(), list)
            finally:
                importlib.reload(aos.api)

    def test_approve_endpoint_requires_auth(self) -> None:
        """POST /api/approvals/{id}/approve should return 401 without token."""
        with patch.dict(os.environ, {"AOS_API_TOKEN": "secret-123"}):
            import importlib
            import aos.api

            importlib.reload(aos.api)
            try:
                client = TestClient(app)
                response = client.post("/api/approvals/test-123/approve")
                assert response.status_code == 401
            finally:
                importlib.reload(aos.api)

    def test_reject_endpoint_requires_auth(self) -> None:
        """POST /api/approvals/{id}/reject should return 401 without token."""
        with patch.dict(os.environ, {"AOS_API_TOKEN": "secret-123"}):
            import importlib
            import aos.api

            importlib.reload(aos.api)
            try:
                client = TestClient(app)
                response = client.post("/api/approvals/test-123/reject")
                assert response.status_code == 401
            finally:
                importlib.reload(aos.api)

    def test_auth_skipped_when_no_token_configured(self) -> None:
        """GET /api/approvals should return 200 when AOS_API_TOKEN is not set (dev mode)."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("AOS_API_TOKEN", None)
            os.environ.pop("AOS_API_TOKEN", None)
            import importlib
            import aos.api

            importlib.reload(aos.api)
            try:
                client = TestClient(app)
                response = client.get("/api/approvals")
                assert response.status_code == 200
            finally:
                importlib.reload(aos.api)
