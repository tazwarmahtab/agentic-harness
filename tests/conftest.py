"""Shared test fixtures for AOS test suite."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

from aos.registry import Registry, load_registry


# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HARNESS_DIR = PROJECT_ROOT / "aos" / "harnesses"
EXECUTIVE_HARNESS_DIR = HARNESS_DIR / "executive"


# ---------------------------------------------------------------------------
# mock_llm_client
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Mock LLM client that returns a successful completion by default."""
    client = MagicMock()
    client.complete.return_value = MagicMock(
        content="test response",
        model="cu/claude-4.5-sonnet",
        provider="9router",
        usage={"prompt_tokens": 10, "completion_tokens": 5},
    )
    return client


# ---------------------------------------------------------------------------
# test_harness_dir
# ---------------------------------------------------------------------------


@pytest.fixture
def test_harness_dir() -> Path:
    """Path to the executive harness bundle (canonical test fixture)."""
    if not EXECUTIVE_HARNESS_DIR.exists():
        pytest.skip("Executive harness directory not found")
    return EXECUTIVE_HARNESS_DIR


# ---------------------------------------------------------------------------
# test_registry
# ---------------------------------------------------------------------------


@pytest.fixture
def test_registry() -> Registry:
    """Minimal registry loaded from the executive harness."""
    if not EXECUTIVE_HARNESS_DIR.exists():
        pytest.skip("Executive harness directory not found")
    return load_registry(EXECUTIVE_HARNESS_DIR)


# ---------------------------------------------------------------------------
# mock_ws_client
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_ws_client() -> MagicMock:
    """Mock WebSocket client with standard send/receive interface."""
    ws = MagicMock()
    ws.query_params = {}
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()
    ws.close = AsyncMock()
    ws.receive_json = AsyncMock(return_value={"action": "ping"})
    return ws
