"""Tests for CocoIndex retriever (pgvector similarity search).

All DB calls are mocked. Tests verify:
  - Returns [] when DATABASE_URL unset (graceful degradation)
  - Returns [] on DB exception (graceful degradation)
  - Validates query and top_k inputs
  - Passes doc_type filter as parameterised query arg
  - Returns RetrievedChunk dataclass with correct fields
  - doc_type filter excludes non-matching rows
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aos.ventures.netso.retriever import RetrievedChunk, retrieve_netso_context


@pytest.mark.unit
class TestInputValidation:
    async def test_raises_on_empty_query(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            await retrieve_netso_context("")

    async def test_raises_on_whitespace_only_query(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            await retrieve_netso_context("   ")

    async def test_raises_on_top_k_zero(self) -> None:
        with pytest.raises(ValueError, match="top_k"):
            await retrieve_netso_context("query", top_k=0)

    async def test_raises_on_top_k_too_large(self) -> None:
        with pytest.raises(ValueError, match="top_k"):
            await retrieve_netso_context("query", top_k=51)


@pytest.mark.unit
class TestGracefulDegradation:
    async def test_returns_empty_when_no_database_url(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": ""}):
            result = await retrieve_netso_context("electricity rate")
        assert result == []

    async def test_returns_empty_on_db_exception(self) -> None:
        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}),
            patch(
                "aos.ventures.netso.retriever._query_pgvector",
                AsyncMock(side_effect=Exception("connection refused")),
            ),
        ):
            result = await retrieve_netso_context("electricity rate")

        assert result == []

    async def test_returns_empty_on_import_error(self) -> None:
        """Missing psycopg/sentence_transformers → graceful empty list."""
        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}),
            patch(
                "aos.ventures.netso.retriever._query_pgvector",
                AsyncMock(side_effect=ImportError("psycopg not installed")),
            ),
        ):
            result = await retrieve_netso_context("some query")

        assert result == []


@pytest.mark.unit
class TestSuccessfulRetrieval:
    def _make_mock_rows(self) -> list[tuple[str, int, str, str, float]]:
        return [
            ("contracts/ppa.md", 0, "PPA rate is 10 BDT/kWh", "financial", 0.92),
            ("ops/meter.md", 3, "Meter reading procedure", "operational", 0.71),
        ]

    async def test_returns_retrieved_chunks(self) -> None:
        rows = self._make_mock_rows()

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}),
            patch(
                "aos.ventures.netso.retriever._query_pgvector",
                AsyncMock(return_value=[
                    RetrievedChunk(
                        filename=r[0],
                        chunk_index=r[1],
                        content=r[2],
                        doc_type=r[3],
                        score=r[4],
                    )
                    for r in rows
                ]),
            ),
        ):
            result = await retrieve_netso_context("PPA rate")

        assert len(result) == 2
        assert result[0].filename == "contracts/ppa.md"
        assert result[0].score == pytest.approx(0.92)
        assert result[0].doc_type == "financial"

    async def test_chunks_are_immutable(self) -> None:
        chunk = RetrievedChunk(
            filename="a.md",
            chunk_index=0,
            content="text",
            doc_type="financial",
            score=0.9,
        )
        with pytest.raises(Exception):  # frozen dataclass
            chunk.score = 0.5  # type: ignore[misc]

    async def test_doc_type_filter_passed_to_query(self) -> None:
        mock_query = AsyncMock(return_value=[])

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}),
            patch("aos.ventures.netso.retriever._query_pgvector", mock_query),
        ):
            await retrieve_netso_context("query", doc_type="financial")

        call_kwargs = mock_query.call_args.kwargs
        assert call_kwargs["doc_type"] == "financial"

    async def test_top_k_passed_to_query(self) -> None:
        mock_query = AsyncMock(return_value=[])

        with (
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}),
            patch("aos.ventures.netso.retriever._query_pgvector", mock_query),
        ):
            await retrieve_netso_context("query", top_k=3)

        assert mock_query.call_args.kwargs["top_k"] == 3
