"""Vector store — embedding-backed semantic search for memory layer.

Provides:
  - EmbeddingProvider: abstract interface + two implementations
    (TF-IDF for zero-dependency, sentence-transformers for production)
  - VectorIndex: in-memory vector store with cosine similarity search
  - build_vector_index_from_memory: bridge from MemoryStore to VectorIndex

Design:
  - All writes create new objects (immutable pattern)
  - TF-IDF provider uses numpy only (no ML dependencies)
  - Optional sentence-transformers provider for higher quality embeddings
  - VectorIndex supports layer/domain filters and permission-aware search
"""

from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from aos.memory import MemoryStore


# ---------------------------------------------------------------------------
# Embedding provider — abstract + implementations
# ---------------------------------------------------------------------------

class EmbeddingProvider(ABC):
    """Abstract interface for text → vector embedding."""

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Return the embedding dimension."""

    @abstractmethod
    def fit(self, texts: list[str]) -> None:
        """Fit the provider on a corpus (optional for some providers)."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a vector."""

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts. Default: map embed()."""
        return [self.embed(t) for t in texts]


class TfidfEmbeddingProvider(EmbeddingProvider):
    """TF-IDF based embedding — zero ML dependencies, uses numpy only.

    Produces sparse-ish vectors from term frequency-inverse document frequency.
    Suitable for small-to-medium corpora (<10k documents).
    """

    def __init__(self, dimensions: int = 128) -> None:
        self._dimensions = dimensions
        self._vocabulary: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._fitted = False

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def fit(self, texts: list[str]) -> None:
        """Fit IDF weights from a corpus."""

        doc_count = len(texts)
        term_doc_freq: dict[str, int] = {}
        all_terms: set[str] = set()

        for text in texts:
            tokens = set(self._tokenize(text))
            all_terms.update(tokens)
            for token in tokens:
                term_doc_freq[token] = term_doc_freq.get(token, 0) + 1

        # Build vocabulary (top N terms by document frequency)
        sorted_terms = sorted(all_terms)
        self._vocabulary = {term: idx for idx, term in enumerate(sorted_terms)}

        # Compute IDF: log(N / df) with smoothing
        self._idf = {}
        for term in sorted_terms:
            df = term_doc_freq.get(term, 0)
            self._idf[term] = math.log((doc_count + 1) / (df + 1)) + 1.0

        self._fitted = True

    def embed(self, text: str) -> list[float]:
        """Embed text using TF-IDF weighted hash projection."""
        if not self._fitted:
            # Auto-fit on single text (degraded but functional for standalone use)
            self.fit([text])

        tokens = self._tokenize(text)
        if not tokens:
            return [0.0] * self._dimensions

        # Compute TF
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1

        # TF-IDF weighted vector in vocabulary space
        vocab_size = len(self._vocabulary)
        if vocab_size == 0:
            return [0.0] * self._dimensions

        # Project to fixed dimensions via hash projection
        import hashlib

        result = [0.0] * self._dimensions
        for token, count in tf.items():
            idf = self._idf.get(token, 1.0)
            tf_val = 1.0 + math.log(count) if count > 0 else 0.0
            weight = tf_val * idf

            # Hash-based projection to fixed dimensions
            h = hashlib.sha256(token.encode()).digest()
            for i in range(self._dimensions):
                # Use bytes from hash to determine sign and magnitude
                byte_val = h[i % len(h)]
                sign = 1.0 if byte_val % 2 == 0 else -1.0
                result[i] += sign * weight * (byte_val / 255.0)

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in result))
        if norm > 0:
            result = [x / norm for x in result]

        return result

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Simple whitespace + lowercase tokenization."""
        import re
        return re.findall(r"[a-z0-9]+", text.lower())


class NumpyEmbeddingProvider(EmbeddingProvider):
    """Sentence-transformers based embedding — production quality.

    Requires: pip install sentence-transformers
    Falls back to TF-IDF if sentence-transformers is not installed.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._model_name = model_name
        self._model = None
        self._dimensions = 384  # default for MiniLM
        self._load_model()

    def _load_model(self) -> None:
        """Attempt to load sentence-transformers model."""
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self._model_name)
            # Get actual dimensions from model
            test_emb = self._model.encode(["test"])
            self._dimensions = len(test_emb[0])
        except ImportError:
            # Fallback: no sentence-transformers available
            self._model = None
            self._dimensions = 384

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def fit(self, texts: list[str]) -> None:
        """No-op for sentence-transformers (pre-trained)."""
        pass

    def embed(self, text: str) -> list[float]:
        """Embed using sentence-transformers or TF-IDF fallback."""
        if self._model is not None:
            embedding = self._model.encode([text])[0]
            return embedding.tolist()
        else:
            # Fallback to TF-IDF
            fallback = TfidfEmbeddingProvider(dimensions=self._dimensions)
            # Use a minimal fit
            if not fallback._fitted:
                fallback.fit([text])
            return fallback.embed(text)


# ---------------------------------------------------------------------------
# Vector entry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VectorEntry:
    """Immutable vector store entry."""
    entry_id: str
    content: str
    embedding: list[float]
    layer: str
    domain: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Search result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SearchResult:
    """Result from vector similarity search."""
    entry: VectorEntry
    score: float

    @property
    def domain(self) -> str:
        return self.entry.domain

    @property
    def layer(self) -> str:
        return self.entry.layer

    @property
    def content(self) -> str:
        return self.entry.content

    @property
    def entry_id(self) -> str:
        return self.entry.entry_id


# ---------------------------------------------------------------------------
# VectorIndex
# ---------------------------------------------------------------------------

class VectorIndex:
    """In-memory vector index with cosine similarity search.

    Supports:
      - Add/remove entries
      - Layer and domain filtering
      - Permission-aware search (accessible_domains)
      - Persistence via pickle (save/load)
    """

    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider
        self._entries: list[VectorEntry] = []
        self._id_to_idx: dict[str, int] = {}
        self._pending: list[tuple[str, str]] = []  # (entry_id, content) for lazy fit
        self._fitted = False

    @property
    def size(self) -> int:
        return len(self._entries)

    def _ensure_fitted(self) -> None:
        """Fit provider on buffered entries if not yet fitted."""
        if self._fitted or not self._pending:
            return
        corpus = [c for _, c in self._pending]
        self._provider.fit(corpus)
        # Rebuild entries with real embeddings (frozen dataclass — rebuild list)
        new_entries = list(self._entries)
        pending_map = {eid: content for eid, content in self._pending}
        for i, old in enumerate(new_entries):
            if old.entry_id in pending_map:
                embedding = self._provider.embed(pending_map[old.entry_id])
                new_entries[i] = VectorEntry(
                    entry_id=old.entry_id,
                    content=old.content,
                    embedding=embedding,
                    layer=old.layer,
                    domain=old.domain,
                    metadata=old.metadata,
                )
        self._entries = new_entries
        self._pending.clear()
        self._fitted = True

    def add(
        self,
        entry_id: str,
        content: str,
        layer: str,
        domain: str,
        metadata: dict[str, Any] | None = None,
    ) -> VectorEntry:
        """Add an entry to the index. Embedding deferred until first search."""
        # Placeholder embedding — will be filled on _ensure_fitted
        placeholder = [0.0] * self._provider.dimensions
        entry = VectorEntry(
            entry_id=entry_id,
            content=content,
            embedding=placeholder,
            layer=layer,
            domain=domain,
            metadata=metadata or {},
        )
        idx = len(self._entries)
        self._id_to_idx[entry_id] = idx
        self._entries.append(entry)
        self._pending.append((entry_id, content))
        return entry

    def remove(self, entry_id: str) -> None:
        """Remove an entry by ID. No-op if not found."""
        if entry_id in self._id_to_idx:
            self._id_to_idx.pop(entry_id)
            self._entries = [e for e in self._entries if e.entry_id != entry_id]
            self._pending = [(eid, c) for eid, c in self._pending if eid != entry_id]
            # Rebuild index
            self._id_to_idx = {e.entry_id: i for i, e in enumerate(self._entries)}

    def search(
        self,
        query: str,
        top_k: int = 10,
        layer: str | None = None,
        domain: str | None = None,
        accessible_domains: set[str] | None = None,
    ) -> list[SearchResult]:
        """Search by cosine similarity. Returns top_k results.

        Args:
            query: search text
            top_k: max results
            layer: filter to specific memory layer
            domain: filter to specific domain
            accessible_domains: permission filter (only these domains)
        """
        self._ensure_fitted()

        if not self._entries:
            return []

        query_embedding = self._provider.embed(query)

        results: list[SearchResult] = []
        for entry in self._entries:
            # Apply filters
            if layer and entry.layer != layer:
                continue
            if domain and entry.domain != domain:
                continue
            if accessible_domains and entry.domain not in accessible_domains:
                continue

            score = _cosine_similarity(query_embedding, entry.embedding)
            results.append(SearchResult(entry=entry, score=score))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def save(self, path: Path) -> None:
        """Persist index to disk as JSON (safe, no pickle)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "dimensions": self._provider.dimensions,
            "entries": [
                {
                    "entry_id": e.entry_id,
                    "content": e.content,
                    "embedding": e.embedding,
                    "layer": e.layer,
                    "domain": e.domain,
                    "metadata": e.metadata,
                }
                for e in self._entries
            ],
        }
        with open(path, "w") as f:
            json.dump(data, f)

    @classmethod
    def load(cls, path: Path, provider: EmbeddingProvider) -> VectorIndex:
        """Load a persisted index from JSON. Returns empty index if not found."""
        if not path.exists():
            return cls(provider=provider)

        with open(path) as f:
            data = json.load(f)

        index = cls(provider=provider)
        for entry_data in data.get("entries", []):
            entry = VectorEntry(
                entry_id=entry_data["entry_id"],
                content=entry_data["content"],
                embedding=entry_data["embedding"],
                layer=entry_data["layer"],
                domain=entry_data["domain"],
                metadata=entry_data.get("metadata", {}),
            )
            index._id_to_idx[entry.entry_id] = len(index._entries)
            index._entries.append(entry)

        return index


# ---------------------------------------------------------------------------
# Factory: build from MemoryStore
# ---------------------------------------------------------------------------

def build_vector_index_from_memory(
    store: MemoryStore,
    provider: EmbeddingProvider,
    agent_id: str | None = None,
) -> VectorIndex:
    """Build a VectorIndex from all active MemoryStore entries.

    Args:
        store: the memory store to index
        provider: embedding provider
        agent_id: if provided, only index entries the agent can read
    """
    index = VectorIndex(provider=provider)

    # Collect all active entries
    all_entries: list[tuple[str, str, str, dict[str, Any]]] = []

    for layer_name in ["long_term", "episodic", "semantic"]:
        layer = store.layers.get(layer_name, {})
        for domain, entries in layer.items():
            # Permission check
            if agent_id and not store.can_read(agent_id, domain):
                continue

            for entry in entries:
                if entry.replaced_by:
                    continue

                # Build searchable text from entry fields
                searchable_parts = []
                if entry.key:
                    searchable_parts.append(entry.key)
                if entry.value:
                    searchable_parts.append(entry.value)
                if entry.content:
                    searchable_parts.append(entry.content)

                searchable_text = " ".join(searchable_parts)
                if not searchable_text.strip():
                    continue

                all_entries.append((
                    entry.id,
                    searchable_text,
                    layer_name,
                    {"domain": domain, "key": entry.key, "value": entry.value},
                ))

    # Fit provider on corpus for TF-IDF
    if all_entries:
        corpus = [text for _, text, _, _ in all_entries]
        provider.fit(corpus)

    # Add entries to index
    for entry_id, text, layer_name, metadata in all_entries:
        index.add(
            entry_id=entry_id,
            content=text,
            layer=layer_name,
            domain=metadata.get("domain", ""),
            metadata=metadata,
        )

    return index


# ---------------------------------------------------------------------------
# Cosine similarity
# ---------------------------------------------------------------------------

def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)
