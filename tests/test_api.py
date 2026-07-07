"""Tests for API authentication and safety."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from tazos.api import TAZOS_API_TOKEN


class TestTokenAuth:
    """Tests for WebSocket token-based authentication."""

    def test_token_env_var_reads_correctly(self) -> None:
        """TAZOS_API_TOKEN should reflect the environment variable."""
        with patch.dict(os.environ, {"TAZOS_API_TOKEN": "test-secret-123"}):
            # Re-import to pick up the env var
            import importlib
            import tazos.api
            importlib.reload(tazos.api)
            assert tazos.api.TAZOS_API_TOKEN == "test-secret-123"
            # Restore
            importlib.reload(tazos.api)

    def test_token_defaults_to_empty(self) -> None:
        """When TAZOS_API_TOKEN is unset, it defaults to empty string."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove the key entirely
            os.environ.pop("TAZOS_API_TOKEN", None)
            import importlib
            import tazos.api
            importlib.reload(tazos.api)
            assert tazos.api.TAZOS_API_TOKEN == ""
            # Restore
            importlib.reload(tazos.api)

    def test_ws_rejects_bad_token(self) -> None:
        """WebSocket should close with 4001 when token is wrong."""
        with patch.dict(os.environ, {"TAZOS_API_TOKEN": "correct-token"}):
            import importlib
            import tazos.api
            importlib.reload(tazos.api)

            mock_ws = MagicMock()
            mock_ws.query_params = {"token": "wrong-token"}
            mock_ws.accept = AsyncMock()
            mock_ws.send_json = AsyncMock()
            mock_ws.close = AsyncMock()

            # Import the handler after reload
            from tazos.api import harness_ws
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    harness_ws(mock_ws, "executive")
                )
            finally:
                loop.close()

            mock_ws.accept.assert_called_once()
            mock_ws.send_json.assert_called_once_with(
                {"event": "error", "message": "Unauthorized"}
            )
            mock_ws.close.assert_called_once_with(code=4001)

            # Restore
            importlib.reload(tazos.api)

    def test_ws_accepts_correct_token(self) -> None:
        """WebSocket should proceed when token matches."""
        with patch.dict(os.environ, {"TAZOS_API_TOKEN": "correct-token"}):
            import importlib
            import tazos.api
            importlib.reload(tazos.api)

            mock_ws = MagicMock()
            mock_ws.query_params = {"token": "correct-token"}
            mock_ws.accept = AsyncMock()
            # _resolve_bundle will fail (no harness), but that's fine —
            # we just need to verify it got past the auth check
            mock_ws.send_json = AsyncMock()
            mock_ws.close = AsyncMock()

            from tazos.api import harness_ws
            import asyncio

            loop = asyncio.new_event_loop()
            try:
                # Should NOT hit the auth rejection — will fail later on bundle resolution
                loop.run_until_complete(
                    harness_ws(mock_ws, "nonexistent-harness")
                )
            except Exception:
                pass
            finally:
                loop.close()

            # Auth passed — no 4001 close (close may be called by error handler later)
            for call in mock_ws.close.call_args_list:
                if call.kwargs.get("code") == 4001:
                    pytest.fail("Auth rejection (4001) should not have been called")

            # Restore
            importlib.reload(tazos.api)
