"""Tests for vector store — embedding provider, vector index, similarity search."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from aos.vector_store import (
    EmbeddingProvider,
    NumpyEmbeddingProvider,
    TfidfEmbeddingProvider,
    VectorIndex,
    VectorEntry,
    build_vector_index_from_memory,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tfidf_provider() -> TfidfEmbeddingProvider:
    return TfidfEmbeddingProvider(dimensions=64)


@pytest.fixture
def sample_texts() -> list[str]:
    return [
        "Netso Energy provides rooftop solar to RMG factories in Bangladesh",
        "PPA rate is BDT 10.00 per kilowatt hour with 3% escalation",
        "Customer savings are 23% versus the true variable rate",
        "The board meeting is scheduled for next Tuesday at 3pm",
        "DSCR is 2.25x under scenario A and 3.09x under scenario B",
        "We need to hire a sales lead for the Chittagong region",
    ]


# ---------------------------------------------------------------------------
# EmbeddingProvider — TfidfEmbeddingProvider
# ---------------------------------------------------------------------------

class TestTfidfProvider:
    def test_produces_correct_dimensions(self, tfidf_provider: TfidfEmbeddingProvider, sample_texts: list[str]) -> None:
        embeddings = tfidf_provider.embed_batch(sample_texts)
        assert len(embeddings) == len(sample_texts)
        for emb in embeddings:
            assert len(emb) == 64

    def test_embed_single(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        emb = tfidf_provider.embed("hello world")
        assert isinstance(emb, list)
        assert len(emb) == 64

    def test_similar_texts_produce_similar_vectors(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        emb1 = tfidf_provider.embed("solar energy installation")
        emb2 = tfidf_provider.embed("solar power setup")
        emb3 = tfidf_provider.embed("board meeting agenda")

        # Cosine similarity: solar-related pair should be more similar
        sim_related = _cosine_sim(emb1, emb2)
        sim_unrelated = _cosine_sim(emb1, emb3)
        assert sim_related > sim_unrelated

    def test_fits_before_embed(self, tfidf_provider: TfidfEmbeddingProvider, sample_texts: list[str]) -> None:
        # Must fit before embed
        tfidf_provider.fit(sample_texts)
        emb = tfidf_provider.embed("test")
        assert len(emb) == 64

    def test_fit_is_idempotent(self, tfidf_provider: TfidfEmbeddingProvider, sample_texts: list[str]) -> None:
        tfidf_provider.fit(sample_texts)
        emb1 = tfidf_provider.embed("test")
        tfidf_provider.fit(sample_texts)
        emb2 = tfidf_provider.embed("test")
        assert emb1 == emb2


# ---------------------------------------------------------------------------
# VectorEntry
# ---------------------------------------------------------------------------

class TestVectorEntry:
    def test_creates_entry(self) -> None:
        entry = VectorEntry(
            entry_id="MEM-001",
            content="test content",
            embedding=[0.1, 0.2, 0.3],
            layer="long_term",
            domain="facts",
            metadata={"key": "entity"},
        )
        assert entry.entry_id == "MEM-001"
        assert entry.embedding == [0.1, 0.2, 0.3]
        assert entry.metadata["key"] == "entity"

    def test_immutable(self) -> None:
        entry = VectorEntry(
            entry_id="MEM-001",
            content="test",
            embedding=[0.1],
            layer="long_term",
            domain="facts",
        )
        with pytest.raises(AttributeError):
            entry.entry_id = "MEM-002"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# VectorIndex — core operations
# ---------------------------------------------------------------------------

class TestVectorIndex:
    def test_add_and_search(self, tfidf_provider: TfidfEmbeddingProvider, sample_texts: list[str]) -> None:
        index = VectorIndex(provider=tfidf_provider)

        for i, text in enumerate(sample_texts):
            index.add(
                entry_id=f"MEM-{i:03d}",
                content=text,
                layer="long_term",
                domain="company_facts",
            )

        results = index.search("solar energy Bangladesh", top_k=3)
        assert len(results) <= 3
        assert len(results) > 0
        # Top result should be solar-related
        assert "solar" in results[0].content.lower() or "bangladesh" in results[0].content.lower()

    def test_search_respects_top_k(self, tfidf_provider: TfidfEmbeddingProvider, sample_texts: list[str]) -> None:
        index = VectorIndex(provider=tfidf_provider)
        for i, text in enumerate(sample_texts):
            index.add(f"MEM-{i:03d}", text, "long_term", "facts")

        results = index.search("energy", top_k=2)
        assert len(results) <= 2

    def test_search_with_layer_filter(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        index = VectorIndex(provider=tfidf_provider)
        index.add("MEM-001", "solar panel installation", "long_term", "facts")
        index.add("MEM-002", "solar panel installation", "episodic", "events")

        results = index.search("solar", layer="long_term")
        assert all(r.layer == "long_term" for r in results)
        assert len(results) == 1

    def test_search_with_domain_filter(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        index = VectorIndex(provider=tfidf_provider)
        index.add("MEM-001", "solar energy", "long_term", "energy_facts")
        index.add("MEM-002", "solar energy", "long_term", "pricing")

        results = index.search("solar", domain="energy_facts")
        assert all(r.domain == "energy_facts" for r in results)
        assert len(results) == 1

    def test_remove_entry(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        index = VectorIndex(provider=tfidf_provider)
        index.add("MEM-001", "test content", "long_term", "facts")
        assert index.size == 1

        index.remove("MEM-001")
        assert index.size == 0
        results = index.search("test")
        assert len(results) == 0

    def test_remove_nonexistent_is_noop(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        index = VectorIndex(provider=tfidf_provider)
        index.remove("MEM-999")  # should not raise

    def test_size_property(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        index = VectorIndex(provider=tfidf_provider)
        assert index.size == 0
        index.add("MEM-001", "a", "long_term", "f")
        assert index.size == 1
        index.add("MEM-002", "b", "long_term", "f")
        assert index.size == 2

    def test_empty_search(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        index = VectorIndex(provider=tfidf_provider)
        results = index.search("anything")
        assert results == []

    def test_search_with_permission_filter(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        index = VectorIndex(provider=tfidf_provider)
        index.add("MEM-001", "secret financial data", "long_term", "financial_models")
        index.add("MEM-002", "public dashboard info", "long_term", "dashboard")

        accessible_domains = {"dashboard"}
        results = index.search("data", accessible_domains=accessible_domains)
        assert all(r.domain in accessible_domains for r in results)


# ---------------------------------------------------------------------------
# VectorIndex — persistence
# ---------------------------------------------------------------------------

class TestVectorPersistence:
    def test_save_and_load(self, tfidf_provider: TfidfEmbeddingProvider, sample_texts: list[str]) -> None:
        index = VectorIndex(provider=tfidf_provider)
        for i, text in enumerate(sample_texts):
            index.add(f"MEM-{i:03d}", text, "long_term", "facts")

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "vector_index.json"
            index.save(save_path)
            assert save_path.exists()

            # Load into a new index
            new_index = VectorIndex.load(save_path, provider=tfidf_provider)
            assert new_index.size == index.size

            # Search should still work
            results = new_index.search("solar", top_k=2)
            assert len(results) > 0

    def test_save_creates_parent_dirs(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        index = VectorIndex(provider=tfidf_provider)
        index.add("MEM-001", "test", "long_term", "f")

        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / "nested" / "dir" / "index.npz"
            index.save(save_path)
            assert save_path.exists()

    def test_load_nonexistent_returns_empty(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        index = VectorIndex.load(Path("/nonexistent/path.npz"), provider=tfidf_provider)
        assert index.size == 0


# ---------------------------------------------------------------------------
# build_vector_index_from_memory
# ---------------------------------------------------------------------------

class TestBuildFromMemory:
    def test_builds_index_from_memory_store(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        from aos.memory import MemoryStore

        store = MemoryStore()
        store.seed_from_dict("long_term", "company_facts", [
            {"key": "entity", "value": "Netso Energy"},
            {"key": "market", "value": "Bangladesh RMG solar"},
        ])
        store.seed_from_dict("semantic", "pricing_model", [
            {"key": "ppa_rate", "value": "BDT 10.00 per kWh"},
        ])

        index = build_vector_index_from_memory(store, provider=tfidf_provider)
        assert index.size == 3

    def test_excludes_superseded_entries(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        from aos.memory import MemoryStore

        store = MemoryStore()
        store.seed_from_dict("long_term", "facts", [
            {"key": "a", "value": "old value"},
        ])
        # Supersede it
        entry = store.layers["long_term"]["facts"][0]
        object.__setattr__(entry, 'replaced_by', 'MEM-FAKE')

        index = build_vector_index_from_memory(store, provider=tfidf_provider)
        assert index.size == 0

    def test_respects_permissions(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        from aos.memory import MemoryStore

        store = MemoryStore(permissions={
            "AGT-COO": {
                "read": ["dashboard"],
                "cannot_read": ["financial_models"],
            },
        })
        store.seed_from_dict("long_term", "dashboard", [
            {"key": "status", "value": "on track"},
        ])
        store.seed_from_dict("long_term", "financial_models", [
            {"key": "revenue", "value": "1M"},
        ])

        index = build_vector_index_from_memory(store, provider=tfidf_provider, agent_id="AGT-COO")
        assert index.size == 1  # only dashboard

    def test_searchable_text_generation(self, tfidf_provider: TfidfEmbeddingProvider) -> None:
        from aos.memory import MemoryStore

        store = MemoryStore()
        store.seed_from_dict("long_term", "facts", [
            {"key": "entity", "value": "Netso Energy", "description": "Legal entity name"},
        ])

        index = build_vector_index_from_memory(store, provider=tfidf_provider)
        # The searchable text should include key, value, and content
        entry = index._entries[0]
        assert "entity" in entry.content.lower() or "netso" in entry.content.lower()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cosine_sim(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    import math
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
