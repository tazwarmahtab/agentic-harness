"""
Async pgvector retriever for Netso venture documents.

Performs semantic similarity search against the CocoIndex-maintained
pgvector table, with graceful fallback to empty results when the DB
is unavailable (so AOS harnesses degrade cleanly, not crash).

Usage (from context assembly):
    from aos.ventures.netso.retriever import retrieve_netso_context

    chunks = await retrieve_netso_context("variable electricity rate")
    rag_text = "\\n\\n".join(c.content for c in chunks)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Maximum chunks to return per query — balances recall vs token budget.
# At ~512 tokens/chunk × 5 chunks = ~2560 tokens; capped to 1500 in context.py.
DEFAULT_TOP_K = 5

# Similarity score floor — cosine distance; drop chunks below this threshold.
MIN_SCORE = 0.30


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RetrievedChunk:
    """Immutable result from a pgvector similarity search."""

    filename: str
    chunk_index: int
    content: str
    score: float
    doc_type: str  # e.g. "financial", "governance", "operational", "general"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def retrieve_netso_context(
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    doc_type: str | None = None,
    min_score: float = MIN_SCORE,
) -> list[RetrievedChunk]:
    """
    Semantic search over the Netso pgvector index.

    Args:
        query:     Natural-language query string.
        top_k:     Maximum number of chunks to return.
        doc_type:  Optional filter — only return chunks whose doc_type matches.
                   Pass None to search across all document types.
        min_score: Cosine similarity floor (0–1). Chunks below this are dropped.

    Returns:
        List of RetrievedChunk, ordered by descending similarity score.
        Returns [] on DB unavailability (graceful degradation).

    Raises:
        ValueError: If query is empty or top_k is out of range.
    """
    if not query or not query.strip():
        raise ValueError("query must be a non-empty string")
    if not (1 <= top_k <= 50):
        raise ValueError(f"top_k must be between 1 and 50, got {top_k}")

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        logger.debug("DATABASE_URL not set — skipping RAG retrieval")
        return []

    try:
        return await _query_pgvector(
            query=query.strip(),
            top_k=top_k,
            doc_type=doc_type,
            min_score=min_score,
            database_url=database_url,
        )
    except Exception as exc:  # noqa: BLE001
        # Degrade gracefully: log and return empty list so the harness
        # still functions without RAG context.
        logger.warning(
            "RAG retrieval failed (query=%r, error=%s) — proceeding without context",
            query[:80],
            exc,
        )
        return []


# ---------------------------------------------------------------------------
# Internal implementation
# ---------------------------------------------------------------------------

async def _query_pgvector(
    *,
    query: str,
    top_k: int,
    doc_type: str | None,
    min_score: float,
    database_url: str,
) -> list[RetrievedChunk]:
    """
    Execute the pgvector similarity query.

    Uses psycopg3 async API with parameterised queries (no string interpolation).
    Embeddings are generated via the same sentence-transformers model used at
    index time to ensure vector space compatibility.
    """
    # Lazy imports — psycopg and sentence_transformers are optional deps.
    # If they're missing, the ImportError propagates to the caller which
    # logs a warning and returns [].
    import psycopg  # type: ignore[import-untyped]
    from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]

    from aos.ventures.netso.indexer import EMBED_MODEL, TABLE_NAME

    # Embed the query using the same model as the index
    model = SentenceTransformer(EMBED_MODEL)
    query_vec: list[float] = model.encode(query).tolist()

    # Build the WHERE clause — parameterised to prevent injection
    filters: list[str] = ["1=1"]
    params: list[Any] = [query_vec, top_k]

    if doc_type is not None:
        filters.append(f"doc_type = ${len(params) + 1}")
        params.append(doc_type)

    where_clause = " AND ".join(filters)

    sql = f"""
        SELECT
            filename,
            chunk_index,
            content,
            doc_type,
            1 - (embedding <=> $1::vector) AS score
        FROM {TABLE_NAME}
        WHERE {where_clause}
          AND 1 - (embedding <=> $1::vector) >= {min_score}
        ORDER BY embedding <=> $1::vector
        LIMIT $2
    """  # noqa: S608 — TABLE_NAME is a module constant, not user input

    async with await psycopg.AsyncConnection.connect(database_url) as conn:
        async with conn.cursor() as cur:
            await cur.execute(sql, params)
            rows = await cur.fetchall()

    return [
        RetrievedChunk(
            filename=row[0],
            chunk_index=row[1],
            content=row[2],
            doc_type=row[3],
            score=float(row[4]),
        )
        for row in rows
    ]
