"""
CocoIndex incremental indexer for Netso venture documents.

Scans Netso_HQ/**/*.md → chunks → embeds → pgvector table.
Run once to bootstrap, then re-run on changes for Δ-only updates.

Usage:
    python -m aos index --venture netso
    python -m aos index --venture netso --force   # full reindex

Requires DATABASE_URL env var pointing at a pgvector-enabled Postgres instance.
Docker quick-start:
    docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=aos pgvector/pgvector:pg16
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import cocoindex

from aos.hardening import sanitize_path

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VENTURE_ROOT = Path("/Users/tazwarmahtab/Documents/10-Projects/Netso_HQ")
TABLE_NAME = "netso_docs"
CHUNK_SIZE = 512      # tokens — sweet-spot from Phase 11 lesson 06
CHUNK_OVERLAP = 50    # token overlap between adjacent chunks
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dim, local, no API cost


# ---------------------------------------------------------------------------
# CocoIndex flow definition
# ---------------------------------------------------------------------------

@cocoindex.flow_def(name="NetsoDocIndexer")
def netso_doc_flow(flow_builder: cocoindex.FlowBuilder, db_target: cocoindex.DataTarget) -> None:
    """
    Incremental indexing pipeline: Netso_HQ/*.md → pgvector.

    CocoIndex engine handles Δ-only reprocessing: only documents whose
    content (or the embedding code) changed since last run are re-embedded.
    """
    # Source: local filesystem, all markdown files under VENTURE_ROOT
    docs = flow_builder.add_source(
        cocoindex.sources.LocalFileSource(
            path=str(VENTURE_ROOT),
            included_patterns=["**/*.md"],
        )
    )

    # Chunk: recursive text splitter, 512-token chunks with 50-token overlap
    chunks = docs.transform(
        cocoindex.ops.SentenceTransformersEmbed,  # type: ignore[attr-defined]
        cocoindex.ops.RecursiveSplitter(  # type: ignore[attr-defined]
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        ),
        field="content",
        output_field="chunks",
    )

    # Embed: sentence-transformers, memoised (re-embeds only on content or code change)
    embedded = chunks.transform(
        cocoindex.ops.SentenceTransformersEmbed(  # type: ignore[attr-defined]
            model=EMBED_MODEL,
        ),
        field="chunks",
        output_field="embedding",
    )

    # Sink: pgvector table via Postgres connector
    embedded.export(
        "netso_docs",
        cocoindex.targets.Postgres(  # type: ignore[attr-defined]
            table_name=TABLE_NAME,
        ),
        primary_key_fields=["filename", "chunk_index"],
        vector_indexes=[
            cocoindex.VectorIndexDef(  # type: ignore[attr-defined]
                field="embedding",
                metric=cocoindex.VectorSimilarityMetric.CosineSimilarity,  # type: ignore[attr-defined]
            )
        ],
    )


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def get_flow() -> cocoindex.Flow:
    """Return the configured CocoIndex flow, wired to DATABASE_URL."""
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required to run the CocoIndex indexer. "
            "Set it to a pgvector-enabled Postgres connection string, e.g.: "
            "postgresql://postgres:aos@localhost:5432/aos"
        )

    # Validate DATABASE_URL is not a path traversal attempt
    # (it's from env, not user input, but defense-in-depth)
    if any(c in database_url for c in ("\x00", "..", "\\")):
        raise ValueError("DATABASE_URL contains invalid characters.")

    cocoindex.init(cocoindex.Settings(database_url=database_url))  # type: ignore[attr-defined]
    return netso_doc_flow  # type: ignore[return-value]


def run_index(*, force: bool = False) -> None:
    """
    Run the incremental index. Idempotent — safe to call repeatedly.

    Args:
        force: If True, drops and rebuilds the pgvector table from scratch.
               Normally CocoIndex handles Δ updates automatically; only use
               force when the schema changes.
    """
    _validate_venture_root()

    flow = get_flow()

    if force:
        logger.info("Force reindex requested — dropping existing table %s", TABLE_NAME)
        flow.update(full=True)
    else:
        logger.info("Running incremental index over %s", VENTURE_ROOT)
        flow.update()

    logger.info("Netso doc index complete (table=%s)", TABLE_NAME)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_venture_root() -> None:
    """Ensure VENTURE_ROOT exists and is accessible.

    VENTURE_ROOT is a trusted compile-time constant (not user input), so
    sanitize_path is not applied here — it would reject the absolute path.
    sanitize_path belongs at harness boundaries where user-supplied strings
    are consumed.
    """
    root = Path(VENTURE_ROOT)
    if not root.exists():
        raise FileNotFoundError(
            f"Netso venture root not found: {root}. "
            "Ensure the Netso_HQ directory is mounted at the expected path."
        )
    if not root.is_dir():
        raise NotADirectoryError(f"Expected directory, got file: {root}")

    md_files = list(root.rglob("*.md"))
    if not md_files:
        logger.warning("No .md files found under %s — index will be empty", root)
    else:
        logger.info("Found %d .md files to index under %s", len(md_files), root)
