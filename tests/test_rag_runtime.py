"""Unit tests for RAG runtime injection in _run_agent_node.

All pgvector, psycopg, and sentence_transformers calls are mocked.
No live DB or cocoindex install required.

Tests:
  1. _fetch_rag_context returns "" without DATABASE_URL
  2. _fetch_rag_context returns "" on any exception from retriever
  3. _fetch_rag_context formats chunks correctly
  4. _run_agent_node passes rag_context to build_prompt
  5. _run_agent_node step result includes rag_chunks_retrieved == N
  6. _run_agent_node rag_chunks_retrieved == 0 when retriever returns []
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Minimal fixtures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _MockChunk:
    filename: str
    chunk_index: int
    content: str
    doc_type: str
    score: float


def _make_agent(**overrides: Any):
    """Return a minimal Agent-like MagicMock."""
    agent = MagicMock()
    agent.id = overrides.get("id", "AGT-TEST-001")
    agent.mission = overrides.get("mission", "Test mission")
    agent.financial_rules = overrides.get("financial_rules", None)
    agent.models = None
    agent.criticality = MagicMock()
    agent.criticality.value = "low"
    return agent


# ---------------------------------------------------------------------------
# Tests for _fetch_rag_context
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFetchRagContext:
    def test_returns_empty_without_database_url(self) -> None:
        """No DATABASE_URL → returns ("", 0) immediately."""
        from aos.graph import _fetch_rag_context

        with patch.dict(os.environ, {"DATABASE_URL": ""}, clear=False):
            text, count = _fetch_rag_context("electricity rate", "AGT-TEST-001")

        assert text == ""
        assert count == 0

    def test_returns_empty_on_exception(self) -> None:
        """If retriever raises, _fetch_rag_context degrades to ("", 0)."""
        from aos.graph import _fetch_rag_context

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}, clear=False),
            patch(
                "aos.ventures.netso.retriever.retrieve_netso_context",
                side_effect=RuntimeError("DB exploded"),
            ),
        ):
            text, count = _fetch_rag_context("electricity rate", "AGT-TEST-001")

        assert text == ""
        assert count == 0

    def test_formats_chunks_correctly(self) -> None:
        """Returned chunks are formatted as [filename#index] content."""
        from aos.graph import _fetch_rag_context

        chunks = [
            _MockChunk("contracts/ppa.md", 0, "PPA rate is 10 BDT/kWh", "financial", 0.92),
            _MockChunk("ops/meter.md", 3, "Meter reading procedure", "operational", 0.81),
        ]

        async def _fake_retrieve(query, **_kw):
            return chunks

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}, clear=False),
            patch("aos.ventures.netso.retriever.retrieve_netso_context", side_effect=_fake_retrieve),
        ):
            text, count = _fetch_rag_context("electricity", "AGT-TEST-001")

        assert "[contracts/ppa.md#0] PPA rate is 10 BDT/kWh" in text
        assert "[ops/meter.md#3] Meter reading procedure" in text
        assert count == 2

    def test_returns_empty_on_import_error(self) -> None:
        """ImportError (psycopg not installed) degrades to ("", 0)."""
        from aos.graph import _fetch_rag_context

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}, clear=False),
            patch.dict(__import__("sys").modules, {"aos.ventures.netso.retriever": None}),
        ):
            text, count = _fetch_rag_context("test query", "AGT-TEST-001")

        assert text == ""
        assert count == 0


# ---------------------------------------------------------------------------
# Tests for _run_agent_node RAG integration
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestRunAgentNodeRag:
    def _make_bundle(self):
        bundle = MagicMock()
        bundle.teams = {}
        return bundle

    def _make_llm_response(self, content: str = '{"status": "ok"}'):
        resp = MagicMock()
        resp.content = content
        resp.usage = MagicMock()
        return resp

    def test_run_agent_node_passes_rag_to_build_prompt(self) -> None:
        """build_prompt must be called with the rag_context kwarg."""
        from aos.graph import _run_agent_node

        agent = _make_agent()
        bundle = self._make_bundle()
        llm = MagicMock()
        llm.complete.return_value = self._make_llm_response()

        fake_rag = "[doc.md#0] Some relevant content"

        with (
            patch("aos.graph._fetch_rag_context", return_value=(fake_rag, 1)),
            patch("aos.graph.build_prompt", return_value="system prompt") as mock_bp,
            patch("aos.graph.validate_output") as mock_val,
            patch("aos.graph._build_task_prompt", return_value="task"),
            patch("aos.graph.resolve_model", return_value="test-model"),
        ):
            mock_val.return_value = MagicMock(passed=True, violations=[], warnings=[])
            _run_agent_node(
                agent=agent,
                bundle=bundle,
                step_name="test_step",
                cycle_id="CYC-001",
                venture_id="netso",
                inputs={},
                llm=llm,
            )

        mock_bp.assert_called_once()
        _call_kwargs = mock_bp.call_args.kwargs
        assert "rag_context" in _call_kwargs
        assert _call_kwargs["rag_context"] == fake_rag

    def test_run_agent_node_rag_count_in_result(self) -> None:
        """Step result dict must include rag_chunks_retrieved == N."""
        from aos.graph import _run_agent_node

        agent = _make_agent()
        bundle = self._make_bundle()
        llm = MagicMock()
        llm.complete.return_value = self._make_llm_response()

        with (
            patch("aos.graph._fetch_rag_context", return_value=("chunk1\nchunk2\nchunk3", 3)),
            patch("aos.graph.build_prompt", return_value="system prompt"),
            patch("aos.graph.validate_output") as mock_val,
            patch("aos.graph._build_task_prompt", return_value="task"),
            patch("aos.graph.resolve_model", return_value="test-model"),
        ):
            mock_val.return_value = MagicMock(passed=True, violations=[], warnings=[])
            result = _run_agent_node(
                agent=agent,
                bundle=bundle,
                step_name="test_step",
                cycle_id="CYC-001",
                venture_id="netso",
                inputs={},
                llm=llm,
            )

        assert result["rag_chunks_retrieved"] == 3

    def test_run_agent_node_rag_count_zero_when_degraded(self) -> None:
        """When retriever returns empty list, rag_chunks_retrieved == 0."""
        from aos.graph import _run_agent_node

        agent = _make_agent()
        bundle = self._make_bundle()
        llm = MagicMock()
        llm.complete.return_value = self._make_llm_response()

        with (
            patch("aos.graph._fetch_rag_context", return_value=("", 0)),
            patch("aos.graph.build_prompt", return_value="system prompt"),
            patch("aos.graph.validate_output") as mock_val,
            patch("aos.graph._build_task_prompt", return_value="task"),
            patch("aos.graph.resolve_model", return_value="test-model"),
        ):
            mock_val.return_value = MagicMock(passed=True, violations=[], warnings=[])
            result = _run_agent_node(
                agent=agent,
                bundle=bundle,
                step_name="test_step",
                cycle_id="CYC-001",
                venture_id="netso",
                inputs={},
                llm=llm,
            )

        assert result["rag_chunks_retrieved"] == 0
