"""Memory system — three-layer memory with permissions, candidates, and audit.

Three layers:
  - Long-term: persistent company facts (key-value, refs)
  - Episodic: events, decisions, meetings (time-sequenced)
  - Semantic: rules, patterns, standards (how things work)

Agents submit memory candidates → reflection engine decides → audit trail.
All writes are immutable — creates new entries, never modifies existing.
Disk persistence via markdown files.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Memory entry types
# ---------------------------------------------------------------------------

class Decision(Enum):
    STORE = "store"
    REJECT = "reject"
    SUMMARIZE = "summarize"
    MERGE = "merge"
    VERSION = "version"


class Classification(Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    FOUNDER_ONLY = "founder_only"


@dataclass(frozen=True)
class MemoryEntry:
    """Immutable memory entry. Use object.__setattr__ for replaced_by."""
    id: str
    layer: str           # long_term, episodic, semantic
    domain: str          # e.g. company_facts, daily_dashboard, pricing_model
    key: str | None = None
    value: str | None = None
    ref: str | None = None
    content: str = ""
    classification: str = "internal"
    source_agent: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    version: int = 1
    replaced_by: str | None = None

    @property
    def content_hash(self) -> str:
        """Content fingerprint for deduplication."""
        raw = f"{self.domain}:{self.key or ''}:{self.value or ''}:{self.content}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class AuditRecord:
    """Immutable audit record for a memory operation."""
    id: str
    operation: str       # store, reject, summarize, merge, version
    entry_id: str | None = None
    agent_id: str = ""
    domain: str = ""
    decision: str = ""
    reason: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    previous_entry_id: str | None = None


@dataclass
class MemoryCandidate:
    """Submitted by an agent, pending reflection engine review."""
    id: str
    agent_id: str
    layer: str
    domain: str
    key: str | None = None
    value: str | None = None
    content: str = ""
    classification: str = "internal"
    submitted_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "pending"  # pending, approved, rejected


@dataclass
class ProceduralMemoryEntry:
    """Procedural memory entry — skills, SOPs, instructions."""
    id: str
    name: str
    description: str
    content: str
    tags: list[str] = field(default_factory=list)
    file_path: str | None = None
    classification: str = "internal"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: str | None = None
    usage_count: int = 0


# ---------------------------------------------------------------------------
# Procedural Memory Store
# ---------------------------------------------------------------------------

class ProceduralMemory:
    """Procedural memory — skills, SOPs, and instructions.

    Stores reusable procedures as markdown files that can be dynamically
    loaded based on context. Maps to SOP files in harnesses.
    """

    def __init__(self, sop_root: Path | None = None):
        self.entries: dict[str, ProceduralMemoryEntry] = {}
        self.sop_root = sop_root or Path.cwd() / "sops"
        self._counter = 0

    def _next_id(self, prefix: str = "PROC") -> str:
        self._counter += 1
        return f"{prefix}-{self._counter:06d}"

    def add_procedure(
        self,
        name: str,
        description: str,
        content: str,
        tags: list[str] | None = None,
        file_path: str | None = None,
        classification: str = "internal",
    ) -> ProceduralMemoryEntry:
        """Add a new procedural memory entry."""
        entry = ProceduralMemoryEntry(
            id=self._next_id("PROC"),
            name=name,
            description=description,
            content=content,
            tags=tags or [],
            file_path=file_path,
            classification=classification,
        )
        self.entries[entry.id] = entry
        return entry

    def load_from_file(self, file_path: Path) -> ProceduralMemoryEntry:
        """Load a procedure from a markdown file."""
        content = file_path.read_text()
        name = file_path.stem

        # Extract description from first paragraph or header
        lines = content.split("\n")
        description = ""
        for line in lines[1:6]:  # Check first few lines
            if line.strip() and not line.startswith("#"):
                description = line.strip()
                break

        return self.add_procedure(
            name=name,
            description=description,
            content=content,
            file_path=str(file_path),
        )

    def load_from_directory(self, directory: Path) -> int:
        """Load all .md files from a directory as procedures."""
        count = 0
        if not directory.exists():
            return count

        for md_file in directory.glob("**/*.md"):
            try:
                self.load_from_file(md_file)
                count += 1
            except Exception:
                continue

        return count

    def search_by_tags(self, tags: list[str]) -> list[ProceduralMemoryEntry]:
        """Find procedures matching any of the given tags."""
        results = []
        for entry in self.entries.values():
            if any(tag in entry.tags for tag in tags):
                results.append(entry)
        return results

    def search_by_keyword(self, keyword: str) -> list[ProceduralMemoryEntry]:
        """Search procedures by keyword in name, description, or content."""
        keyword_lower = keyword.lower()
        results = []
        for entry in self.entries.values():
            searchable = f"{entry.name} {entry.description} {entry.content}".lower()
            if keyword_lower in searchable:
                results.append(entry)
        return results

    def get(self, proc_id: str) -> ProceduralMemoryEntry | None:
        """Get a procedure by ID and track usage."""
        entry = self.entries.get(proc_id)
        if entry:
            entry.usage_count += 1
            entry.last_used = datetime.now().isoformat()
        return entry

    def retrieve_for_context(
        self,
        keywords: list[str] | None = None,
        tags: list[str] | None = None,
        max_entries: int = 5,
    ) -> str:
        """Retrieve relevant procedures for agent context."""
        results: list[ProceduralMemoryEntry] = []

        if tags:
            results.extend(self.search_by_tags(tags))

        if keywords:
            for keyword in keywords:
                results.extend(self.search_by_keyword(keyword))

        # Deduplicate and sort by usage
        unique = {e.id: e for e in results}
        sorted_entries = sorted(
            unique.values(),
            key=lambda e: e.usage_count,
            reverse=True,
        )[:max_entries]

        if not sorted_entries:
            return ""

        lines = ["# Procedural Memory (SOPs)", ""]
        for entry in sorted_entries:
            lines.append(f"## {entry.name}")
            lines.append(f"{entry.description}")
            lines.append(f"```\n{entry.content[:500]}\n```")
            lines.append("")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Memory Store
# ---------------------------------------------------------------------------

class MemoryStore:
    """Three-layer memory with permissions, candidates, and audit trail.

    Enforces:
      - Per-agent least-privilege read/write/cannot_read
      - Candidate submission pattern (no direct writes)
      - Immutable audit trail
      - Versioning for updated entries
    """

    def __init__(
        self,
        permissions: dict[str, dict[str, list[str]]] | None = None,
        update_rules: dict[str, Any] | None = None,
        llm_client: Any | None = None,
        db_path: Path | None = None,
        embedding_provider: Any | None = None,
        max_audit_records: int = 200,
    ):
        self.layers: dict[str, dict[str, list[MemoryEntry]]] = {
            "long_term": defaultdict(list),
            "episodic": defaultdict(list),
            "semantic": defaultdict(list),
        }
        self.permissions = permissions or {}
        self.update_rules = update_rules or {}
        self.candidates: list[MemoryCandidate] = []
        self.audit_trail: list[AuditRecord] = []
        self._max_audit_records = max_audit_records
        self._counter = 0
        self.procedural = ProceduralMemory()
        self.llm_client = llm_client
        self._episodic_size_threshold = 100  # Consolidate after N entries
        self._last_consolidation: str | None = None
        self.db_path: Path | None = db_path

        # Vector index — lazy-built on first search_vector() call
        self._embedding_provider = embedding_provider
        self._vector_index: Any | None = None
        self._vector_index_dirty = True  # needs rebuild after writes

        # Load existing entries from SQLite if db_path is provided
        if self.db_path is not None:
            self._load_from_sqlite()

    def _next_id(self, prefix: str = "MEM") -> str:
        self._counter += 1
        return f"{prefix}-{self._counter:06d}"

    # ----- Permission checks -----

    def can_read(self, agent_id: str, domain: str) -> bool:
        """Check if agent can read from a domain."""
        perms = self.permissions.get(agent_id, {})
        cannot_read = perms.get("cannot_read", [])
        read_list = perms.get("read", [])

        # Check cannot_read first (explicit deny)
        for pattern in cannot_read:
            if self._matches_domain(pattern, domain):
                return False

        # Check read list
        for pattern in read_list:
            if self._matches_domain(pattern, domain):
                return True

        # CEO has all_long_term/all_episodic/all_semantic
        if "all_long_term" in read_list and domain in self.layers.get("long_term", {}):
            return True
        if "all_episodic" in read_list and domain in self.layers.get("episodic", {}):
            return True
        if "all_semantic" in read_list and domain in self.layers.get("semantic", {}):
            return True

        return False

    def can_write(self, agent_id: str, domain: str) -> bool:
        """Check if agent can write to a domain."""
        perms = self.permissions.get(agent_id, {})
        write_list = perms.get("write", [])
        for pattern in write_list:
            if self._matches_domain(pattern, domain):
                return True
        return False

    def _matches_domain(self, pattern: str, domain: str) -> bool:
        """Check if a permission pattern matches a domain name."""
        if pattern == domain:
            return True
        if pattern.endswith("*") and domain.startswith(pattern[:-1]):
            return True
        return False

    # ----- Read operations -----

    def read(self, layer: str, domain: str, agent_id: str) -> list[MemoryEntry]:
        """Read entries from a memory domain. Enforces permissions."""
        if not self.can_read(agent_id, domain):
            return []

        entries = self.layers.get(layer, {}).get(domain, [])
        return [e for e in entries if not e.replaced_by]  # exclude superseded

    def read_all(self, agent_id: str) -> dict[str, dict[str, list[MemoryEntry]]]:
        """Read all accessible memory for an agent."""
        result = {}
        for layer in self.layers:
            result[layer] = {}
            for domain in self.layers[layer]:
                entries = self.read(layer, domain, agent_id)
                if entries:
                    result[layer][domain] = entries
        return result

    def search(self, query: str, agent_id: str) -> list[MemoryEntry]:
        """Search memory entries by content match (basic RAG)."""
        results = []
        query_lower = query.lower()
        for layer in self.layers:
            for domain in self.layers[layer]:
                if not self.can_read(agent_id, domain):
                    continue
                for entry in self.layers[layer][domain]:
                    if entry.replaced_by:
                        continue
                    searchable = f"{entry.key or ''} {entry.value or ''} {entry.content} {entry.description if hasattr(entry, 'description') else ''}".lower()
                    if query_lower in searchable:
                        results.append(entry)
        return results

    # ----- Vector (semantic) search -----

    def _rebuild_vector_index(self, agent_id: str | None = None) -> Any:
        """Rebuild the vector index from current memory entries.

        Uses lazy initialization — index is rebuilt only when dirty (after writes).
        """
        if self._embedding_provider is None:
            return None

        from aos.vector_store import build_vector_index_from_memory

        self._vector_index = build_vector_index_from_memory(
            store=self,
            provider=self._embedding_provider,
            agent_id=agent_id,
        )
        self._vector_index_dirty = False
        return self._vector_index

    def _get_vector_index(self, agent_id: str | None = None) -> Any:
        """Get the vector index, rebuilding if dirty."""
        if self._embedding_provider is None:
            return None
        if self._vector_index is None or self._vector_index_dirty:
            return self._rebuild_vector_index(agent_id)
        return self._vector_index

    def search_vector(
        self,
        query: str,
        agent_id: str,
        top_k: int = 10,
        layer: str | None = None,
        domain: str | None = None,
    ) -> list[MemoryEntry]:
        """Semantic search using vector embeddings.

        Returns MemoryEntry objects ranked by cosine similarity.
        Falls back to keyword search if no embedding provider is configured.
        Falls back gracefully if the vector index is empty.
        """
        if self._embedding_provider is None:
            return self.search(query, agent_id)

        index = self._get_vector_index(agent_id)
        if index is None or index.size == 0:
            return self.search(query, agent_id)

        # Build accessible domains set for permission filtering
        accessible_domains: set[str] = set()
        for layer_name in self.layers:
            for domain_name in self.layers[layer_name]:
                if self.can_read(agent_id, domain_name):
                    accessible_domains.add(domain_name)

        results = index.search(
            query=query,
            top_k=top_k,
            layer=layer,
            domain=domain,
            accessible_domains=accessible_domains,
        )

        # Map SearchResult back to MemoryEntry objects
        entry_map: dict[str, MemoryEntry] = {}
        for layer_name in self.layers:
            for domain_name, entries in self.layers[layer_name].items():
                for entry in entries:
                    entry_map[entry.id] = entry

        return [entry_map[r.entry_id] for r in results if r.entry_id in entry_map]

    def search_episodic_by_time(
        self,
        agent_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        domain: str | None = None,
    ) -> list[MemoryEntry]:
        """Search episodic memory by time range (SQL-style filtering)."""
        results = []
        for domain_name, entries in self.layers["episodic"].items():
            if domain and domain_name != domain:
                continue
            if not self.can_read(agent_id, domain_name):
                continue

            for entry in entries:
                if entry.replaced_by:
                    continue

                # Filter by date range
                if start_date and entry.created_at < start_date:
                    continue
                if end_date and entry.created_at > end_date:
                    continue

                results.append(entry)

        # Sort by timestamp descending
        results.sort(key=lambda e: e.created_at, reverse=True)
        return results

    def retrieve_hybrid(
        self,
        agent_id: str,
        query: str,
        start_date: str | None = None,
        end_date: str | None = None,
        max_entries: int = 10,
    ) -> dict[str, list[MemoryEntry]]:
        """Dual retrieval strategy: RAG for semantic + SQL for episodic.

        Combines semantic search (RAG) across semantic/long_term memory
        with time-series queries (SQL-style) for episodic memory.
        """
        results = {
            "semantic": [],
            "episodic": [],
            "long_term": [],
        }

        # RAG search for semantic and long_term layers
        query_lower = query.lower()
        for layer in ["semantic", "long_term"]:
            for domain in self.layers[layer]:
                if not self.can_read(agent_id, domain):
                    continue
                for entry in self.layers[layer][domain]:
                    if entry.replaced_by:
                        continue
                    searchable = f"{entry.key or ''} {entry.value or ''} {entry.content}".lower()
                    if query_lower in searchable:
                        results[layer].append(entry)

        # SQL-style time-series query for episodic
        results["episodic"] = self.search_episodic_by_time(
            agent_id=agent_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Limit results per layer
        for layer in results:
            results[layer] = results[layer][:max_entries]

        return results

    def retrieve_for_agent(
        self,
        agent_id: str,
        domain_hint: str | None = None,
        max_chars: int = 3000,
    ) -> str:
        """Retrieve memory context for an agent, formatted for prompt injection.

        Searches all layers for accessible entries matching the domain hint.
        Returns a formatted string suitable for including in a system prompt.
        Respects permissions — only returns entries the agent can read.
        """
        results: list[str] = []
        total_chars = 0

        for layer in ["long_term", "episodic", "semantic"]:
            for domain, entries in self.layers[layer].items():
                if not self.can_read(agent_id, domain):
                    continue

                # Filter by domain hint if provided
                if domain_hint and domain_hint.lower() not in domain.lower():
                    continue

                active = [e for e in entries if not e.replaced_by]
                if not active:
                    continue

                for entry in active:
                    if total_chars >= max_chars:
                        break

                    line = ""
                    if entry.key and entry.value:
                        line = f"[{layer}/{domain}] {entry.key}: {entry.value}"
                    elif entry.content:
                        line = f"[{layer}/{domain}] {entry.content[:200]}"
                    else:
                        continue

                    results.append(line)
                    total_chars += len(line)

            if total_chars >= max_chars:
                break

        if not results:
            return ""

        header = f"Memory ({len(results)} entries, {total_chars} chars):"
        return header + "\n" + "\n".join(results)

    def consolidate_episodic_to_semantic(
        self,
        agent_id: str = "system",
        use_llm: bool = True,
    ) -> list[MemoryEntry]:
        """Consolidate episodic memory into semantic memory.

        Uses LLM to extract durable facts and patterns from time-series events.
        Returns the new semantic entries created.
        """
        # Collect recent episodic entries
        episodic_entries = []
        for domain, entries in self.layers["episodic"].items():
            active = [e for e in entries if not e.replaced_by]
            episodic_entries.extend(active)

        if not episodic_entries:
            return []

        # Sort by timestamp
        episodic_entries.sort(key=lambda e: e.created_at)

        # If no LLM client, do simple keyword extraction
        if not use_llm or not self.llm_client:
            return self._consolidate_simple(episodic_entries, agent_id)

        # Use LLM to summarize and extract patterns
        return self._consolidate_with_llm(episodic_entries, agent_id)

    def _consolidate_simple(
        self,
        episodic_entries: list[MemoryEntry],
        agent_id: str,
    ) -> list[MemoryEntry]:
        """Simple consolidation without LLM — extract common patterns."""
        # Group entries by domain
        by_domain: dict[str, list[MemoryEntry]] = defaultdict(list)
        for entry in episodic_entries:
            by_domain[entry.domain].append(entry)

        new_semantic = []
        for domain, entries in by_domain.items():
            # Create a summary entry
            content_parts = [e.content[:100] for e in entries[:5]]
            summary = f"Summary of {len(entries)} events: " + "; ".join(content_parts)

            semantic_entry = MemoryEntry(
                id=self._next_id("MEM"),
                layer="semantic",
                domain=domain,
                content=summary,
                classification="internal",
                source_agent=agent_id,
            )
            self.layers["semantic"][domain].append(semantic_entry)
            new_semantic.append(semantic_entry)

        self._last_consolidation = datetime.now().isoformat()
        return new_semantic

    def _consolidate_with_llm(
        self,
        episodic_entries: list[MemoryEntry],
        agent_id: str,
    ) -> list[MemoryEntry]:
        """LLM-powered consolidation — extract durable facts and patterns."""
        # Build prompt for LLM
        entries_text = "\n".join(
            f"- [{e.domain}] {e.created_at}: {e.content[:200]}"
            for e in episodic_entries[:50]  # Limit to recent 50
        )

        prompt = f"""Analyze these episodic memory entries and extract durable facts, patterns, and rules.

Episodic entries:
{entries_text}

Extract:
1. Durable facts (things that remain true)
2. Patterns (recurring behaviors or decisions)
3. Rules or standards (how things should work)

Format each finding as:
DOMAIN: <domain_name>
CONTENT: <the fact/pattern/rule>
---
"""

        try:
            # Call LLM (pseudo-code, actual implementation depends on llm_client interface)
            response = self.llm_client.complete(prompt)

            # Parse LLM response and create semantic entries
            new_semantic = []
            sections = response.split("---")

            for section in sections:
                if "DOMAIN:" not in section:
                    continue

                lines = section.strip().split("\n")
                domain = ""
                content = ""

                for line in lines:
                    if line.startswith("DOMAIN:"):
                        domain = line.replace("DOMAIN:", "").strip()
                    elif line.startswith("CONTENT:"):
                        content = line.replace("CONTENT:", "").strip()

                if domain and content:
                    semantic_entry = MemoryEntry(
                        id=self._next_id("MEM"),
                        layer="semantic",
                        domain=domain,
                        content=content,
                        classification="internal",
                        source_agent=agent_id,
                    )
                    self.layers["semantic"][domain].append(semantic_entry)
                    new_semantic.append(semantic_entry)

            self._last_consolidation = datetime.now().isoformat()
            return new_semantic

        except Exception:
            # Fallback to simple consolidation
            return self._consolidate_simple(episodic_entries, agent_id)

    def check_consolidation_needed(self) -> bool:
        """Check if episodic memory needs consolidation."""
        total_episodic = sum(
            len([e for e in entries if not e.replaced_by])
            for entries in self.layers["episodic"].values()
        )
        return total_episodic >= self._episodic_size_threshold

    def get_memory_health_metrics(self) -> dict[str, Any]:
        """Get memory health metrics."""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "layers": {},
            "last_consolidation": self._last_consolidation,
            "consolidation_needed": self.check_consolidation_needed(),
        }

        for layer in ["long_term", "episodic", "semantic"]:
            domains = self.layers[layer]
            active_entries = sum(
                len([e for e in entries if not e.replaced_by])
                for entries in domains.values()
            )
            total_entries = sum(len(entries) for entries in domains.values())

            metrics["layers"][layer] = {
                "domains": len(domains),
                "active_entries": active_entries,
                "total_entries": total_entries,
                "superseded_entries": total_entries - active_entries,
            }

        metrics["procedural"] = {
            "total_procedures": len(self.procedural.entries),
            "avg_usage": (
                sum(e.usage_count for e in self.procedural.entries.values())
                / len(self.procedural.entries)
                if self.procedural.entries
                else 0
            ),
        }

        return metrics

    # ----- Candidate submission -----

    def submit_candidate(
        self,
        agent_id: str,
        layer: str,
        domain: str,
        key: str | None = None,
        value: str | None = None,
        content: str = "",
        classification: str = "internal",
    ) -> MemoryCandidate:
        """Agent submits a memory candidate for reflection engine review."""
        candidate = MemoryCandidate(
            id=self._next_id("CAND"),
            agent_id=agent_id,
            layer=layer,
            domain=domain,
            key=key,
            value=value,
            content=content,
            classification=classification,
        )
        self.candidates.append(candidate)
        return candidate

    def review_candidate(
        self,
        candidate_id: str,
        decision: Decision,
        reason: str = "",
    ) -> MemoryEntry | None:
        """Reflection engine reviews a candidate and decides.

        Returns the stored entry if decision is STORE or VERSION,
        None otherwise.
        """
        candidate = None
        for c in self.candidates:
            if c.id == candidate_id:
                candidate = c
                break

        if not candidate:
            return None

        entry: MemoryEntry | None = None

        if decision == Decision.STORE:
            entry = self._store_entry(candidate)
        elif decision == Decision.VERSION:
            entry = self._version_entry(candidate)
        elif decision == Decision.MERGE:
            entry = self._merge_entry(candidate)
        # REJECT and SUMMARIZE just log

        # Record audit
        self.audit_trail.append(AuditRecord(
            id=self._next_id("AUD"),
            operation=decision.value,
            entry_id=entry.id if entry else None,
            agent_id=candidate.agent_id,
            domain=candidate.domain,
            decision=decision.value,
            reason=reason or f"Candidate {candidate.id} → {decision.value}",
            previous_entry_id=entry.replaced_by if entry else None,
        ))

        # Enforce audit trail cap — keep most recent entries
        if len(self.audit_trail) > self._max_audit_records:
            self.audit_trail = self.audit_trail[-self._max_audit_records:]

        # Mark candidate processed
        candidate.status = decision.value
        return entry

    def _store_entry(self, candidate: MemoryCandidate) -> MemoryEntry:
        """Store a new memory entry."""
        self._vector_index_dirty = True
        entry = MemoryEntry(
            id=self._next_id("MEM"),
            layer=candidate.layer,
            domain=candidate.domain,
            key=candidate.key,
            value=candidate.value,
            content=candidate.content,
            classification=candidate.classification,
            source_agent=candidate.agent_id,
        )
        self.layers[candidate.layer][candidate.domain].append(entry)
        return entry

    def _version_entry(self, candidate: MemoryCandidate) -> MemoryEntry:
        """Create a new version, superseding the old entry."""
        # Find the latest entry in this domain with matching key
        old_entry = None
        for entry in reversed(self.layers[candidate.layer].get(candidate.domain, [])):
            if candidate.key and entry.key == candidate.key:
                old_entry = entry
                break

        new_entry = MemoryEntry(
            id=self._next_id("MEM"),
            layer=candidate.layer,
            domain=candidate.domain,
            key=candidate.key,
            value=candidate.value,
            content=candidate.content,
            classification=candidate.classification,
            source_agent=candidate.agent_id,
            version=(old_entry.version + 1) if old_entry else 1,
            replaced_by=None,
        )

        # Mark old entry as superseded (frozen dataclass bypass)
        if old_entry:
            object.__setattr__(old_entry, 'replaced_by', new_entry.id)

        self.layers[candidate.layer][candidate.domain].append(new_entry)
        return new_entry

    def _merge_entry(self, candidate: MemoryCandidate) -> MemoryEntry:
        """Merge candidate content into the latest matching entry."""
        old_entry = None
        for entry in reversed(self.layers[candidate.layer].get(candidate.domain, [])):
            if candidate.key and entry.key == candidate.key:
                old_entry = entry
                break

        if old_entry:
            # Merge content
            merged_content = old_entry.content
            if candidate.content and candidate.content not in merged_content:
                merged_content = f"{merged_content}\n{candidate.content}"

            new_entry = MemoryEntry(
                id=self._next_id("MEM"),
                layer=candidate.layer,
                domain=candidate.domain,
                key=candidate.key,
                value=candidate.value or old_entry.value,
                content=merged_content,
                classification=candidate.classification,
                source_agent=candidate.agent_id,
                version=old_entry.version + 1,
            )
            object.__setattr__(old_entry, 'replaced_by', new_entry.id)
            self.layers[candidate.layer][candidate.domain].append(new_entry)
            return new_entry

        # No existing entry — just store
        return self._store_entry(candidate)

    # ----- Direct write (for venture artifact refs) -----

    def seed_from_dict(self, layer: str, domain: str, data: Any) -> None:
        """Seed memory from YAML manifest data (one-time load)."""
        self._vector_index_dirty = True
        if isinstance(data, list):
            for item in data:
                entry = MemoryEntry(
                    id=self._next_id("MEM"),
                    layer=layer,
                    domain=domain,
                    key=item.get("key") if isinstance(item, dict) else None,
                    value=item.get("value") if isinstance(item, dict) else None,
                    ref=item.get("ref") if isinstance(item, dict) else None,
                    content=item.get("description", "") if isinstance(item, dict) else str(item),
                    classification=item.get("classification", "internal") if isinstance(item, dict) else "internal",
                    source_agent="system_seed",
                )
                self.layers[layer][domain].append(entry)
        elif isinstance(data, dict):
            entry = MemoryEntry(
                id=self._next_id("MEM"),
                layer=layer,
                domain=domain,
                ref=data.get("ref"),
                content=data.get("description", ""),
                classification=data.get("classification", "internal"),
                source_agent="system_seed",
            )
            self.layers[layer][domain].append(entry)

    # ----- Reflection engine -----

    def review_pending(self, auto_store: bool = True) -> list[AuditRecord]:
        """Review all pending candidates. Returns audit records.

        If auto_store=True, candidates are stored automatically.
        If False, only hash dedup is done (candidates stay pending).
        """
        results = []
        for candidate in list(self.candidates):
            if candidate.status != "pending":
                continue

            # Check for duplicate by content hash
            content_hash = hashlib.sha256(
                f"{candidate.domain}:{candidate.key or ''}:{candidate.value or ''}:{candidate.content}".encode()
            ).hexdigest()[:16]

            is_duplicate = False
            for layer in self.layers:
                for domain_entries in self.layers[layer].values():
                    for entry in domain_entries:
                        if not entry.replaced_by and entry.content_hash == content_hash:
                            is_duplicate = True
                            break

            if is_duplicate:
                candidate.status = "duplicate"
                continue

            if auto_store:
                # Auto-store: if domain has existing entries, version; else store
                existing = self.layers.get(candidate.layer, {}).get(candidate.domain, [])
                active = [e for e in existing if not e.replaced_by and e.key == candidate.key]
                if active:
                    decision = Decision.VERSION
                    entry = self._version_entry(candidate)
                else:
                    decision = Decision.STORE
                    entry = self._store_entry(candidate)

                candidate.status = decision.value
                self.audit_trail.append(AuditRecord(
                    id=self._next_id("AUD"),
                    operation=decision.value,
                    entry_id=entry.id,
                    agent_id=candidate.agent_id,
                    domain=candidate.domain,
                    decision=decision.value,
                    reason=f"Auto-reviewed: {candidate.id} → {decision.value}",
                ))

                # Enforce audit trail cap
                if len(self.audit_trail) > self._max_audit_records:
                    self.audit_trail = self.audit_trail[-self._max_audit_records:]
                results.append(self.audit_trail[-1])
            else:
                candidate.status = "reviewed"

        return results

    # ----- SQLite persistence -----

    def _load_from_sqlite(self) -> None:
        """Load all memory entries from SQLite database into self.layers."""
        import sqlite3

        if self.db_path is None or not self.db_path.exists():
            return

        conn = sqlite3.connect(str(self.db_path))
        try:
            cursor = conn.execute(
                "SELECT id, layer, domain, key, value, ref, content, "
                "classification, source_agent, created_at, version, "
                "replaced_by, content_hash "
                "FROM memory_entries"
            )
            max_counter = 0
            for row in cursor:
                entry_id, layer, domain = row[0], row[1], row[2]
                if layer not in self.layers:
                    continue

                entry = MemoryEntry(
                    id=entry_id,
                    layer=layer,
                    domain=domain,
                    key=row[3],
                    value=row[4],
                    ref=row[5],
                    content=row[6] or "",
                    classification=row[7] or "internal",
                    source_agent=row[8],
                    created_at=row[9],
                    version=row[10] or 1,
                    replaced_by=row[11],
                )
                self.layers[layer][domain].append(entry)

                # Advance counter to avoid ID collisions
                try:
                    num = int(entry_id.split("-")[-1])
                    if num > max_counter:
                        max_counter = num
                except (ValueError, IndexError):
                    pass

            self._counter = max(self._counter, max_counter)
        finally:
            conn.close()

    def _save_to_sqlite(self, venture_id: str = "") -> None:
        """Upsert all memory entries to SQLite database."""
        import sqlite3

        if self.db_path is None:
            return

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS memory_entries ("
                "    id TEXT PRIMARY KEY,"
                "    layer TEXT NOT NULL,"
                "    domain TEXT NOT NULL,"
                "    key TEXT,"
                "    value TEXT,"
                "    ref TEXT,"
                "    content TEXT,"
                "    classification TEXT DEFAULT 'internal',"
                "    source_agent TEXT,"
                "    created_at TEXT NOT NULL,"
                "    version INTEGER DEFAULT 1,"
                "    replaced_by TEXT,"
                "    venture_id TEXT,"
                "    content_hash TEXT"
                ")"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mem_layer_domain "
                "ON memory_entries(layer, domain)"
            )
            for layer in self.layers:
                for domain, entries in self.layers[layer].items():
                    for entry in entries:
                        conn.execute(
                            "INSERT OR REPLACE INTO memory_entries "
                            "(id, layer, domain, key, value, ref, content, "
                            "classification, source_agent, created_at, version, "
                            "replaced_by, venture_id, content_hash) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                entry.id,
                                entry.layer,
                                entry.domain,
                                entry.key,
                                entry.value,
                                entry.ref,
                                entry.content,
                                entry.classification,
                                entry.source_agent,
                                entry.created_at,
                                entry.version,
                                entry.replaced_by,
                                venture_id or None,
                                entry.content_hash,
                            ),
                        )
            conn.commit()
        finally:
            conn.close()

    # ----- Disk persistence -----

    def persist_to_disk(self, venture_root: Path, cycle_id: str = "") -> dict[str, Any]:
        """Write memory state to disk. Returns summary of what was written.

        Writes:
          - audit.log (JSON-lines, append-only)
          - TAZOS_MEMORY.md (human-readable memory snapshot)
          - SQLite database (if db_path configured)
        """
        written: dict[str, str] = {}

        # Write audit log
        audit_path = venture_root / "ai_system" / "System" / "TAZOS_AUDIT.log"
        audit_path.parent.mkdir(parents=True, exist_ok=True)

        # Append new audit records since last persist
        with open(audit_path, "a") as f:
            for rec in self.audit_trail:
                f.write(json.dumps({
                    "id": rec.id,
                    "operation": rec.operation,
                    "entry_id": rec.entry_id,
                    "agent_id": rec.agent_id,
                    "domain": rec.domain,
                    "decision": rec.decision,
                    "reason": rec.reason,
                    "timestamp": rec.timestamp,
                    "cycle_id": cycle_id,
                }) + "\n")
        written["audit_log"] = str(audit_path)

        # Write human-readable memory snapshot
        memory_path = venture_root / "ai_system" / "System" / "TAZOS_MEMORY.md"
        with open(memory_path, "w") as f:
            f.write(self.to_markdown())
        written["memory_snapshot"] = str(memory_path)

        # Persist to SQLite if db_path is configured
        if self.db_path is not None:
            venture_id = venture_root.name if venture_root else ""
            self._save_to_sqlite(venture_id=venture_id)
            written["sqlite_db"] = str(self.db_path)

        return written

    def to_markdown(self, agent_id: str | None = None) -> str:
        """Export accessible memory as markdown."""
        lines = ["# TAZ OS Memory Store", ""]

        for layer in ["long_term", "episodic", "semantic"]:
            lines.append(f"## {layer.replace('_', ' ').title()} Layer")
            lines.append("")

            for domain, entries in sorted(self.layers[layer].items()):
                active = [e for e in entries if not e.replaced_by]
                if not active:
                    continue

                lines.append(f"### {domain}")
                for entry in active:
                    if entry.key and entry.value:
                        lines.append(f"- **{entry.key}**: {entry.value}")
                    elif entry.ref:
                        lines.append(f"- ref: {entry.ref} — {entry.content}")
                    elif entry.content:
                        lines.append(f"- {entry.content[:200]}")
                lines.append("")

        # Audit trail summary
        if self.audit_trail:
            lines.append("## Audit Trail")
            lines.append(f"Total operations: {len(self.audit_trail)}")
            by_op: dict[str, int] = defaultdict(int)
            for rec in self.audit_trail:
                by_op[rec.operation] += 1
            for op, count in sorted(by_op.items()):
                lines.append(f"- {op}: {count}")
            lines.append("")

        # Candidates pending review
        pending = [c for c in self.candidates if c.status == "pending"]
        if pending:
            lines.append("## Pending Candidates")
            for c in pending:
                lines.append(f"- {c.id}: {c.agent_id} → {c.domain} ({c.submitted_at})")
            lines.append("")

        return "\n".join(lines)

    def summary(self) -> str:
        """Return a summary of memory state."""
        lines = ["Memory Store:"]
        for layer in ["long_term", "episodic", "semantic"]:
            domains = self.layers[layer]
            active = sum(1 for entries in domains.values()
                        for e in entries if not e.replaced_by)
            lines.append(f"  {layer}: {len(domains)} domains, {active} entries")
        lines.append(f"  Candidates: {len(self.candidates)} ({sum(1 for c in self.candidates if c.status == 'pending')} pending)")
        lines.append(f"  Audit records: {len(self.audit_trail)}")
        lines.append(f"  Procedural: {len(self.procedural.entries)} procedures")
        if self._last_consolidation:
            lines.append(f"  Last consolidation: {self._last_consolidation}")
        if self.check_consolidation_needed():
            lines.append("  ⚠ Consolidation recommended")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Factory: build MemoryStore from memory.yml
# ---------------------------------------------------------------------------

def build_memory_from_manifest(
    manifest: dict[str, Any],
    venture_root: Path | None = None,
    db_path: Path | None = None,
) -> MemoryStore:
    """Build a MemoryStore from a parsed memory.yml manifest.

    Seeds long_term/episodic/semantic layers from manifest data.
    Venture artifact refs are resolved to file paths if venture_root is provided.
    If db_path is provided, loads existing entries from SQLite and configures
    future persist_to_disk calls to write to SQLite as well.
    """
    permissions = manifest.get("permissions", {})
    update_rules = manifest.get("update_rules", {})
    store = MemoryStore(
        permissions=permissions,
        update_rules=update_rules,
        db_path=db_path,
    )

    layers = manifest.get("layers", {})

    # Seed long_term
    for domain, data in layers.get("long_term", {}).items():
        if isinstance(data, list):
            store.seed_from_dict("long_term", domain, data)
        elif isinstance(data, dict):
            # Resolve ref if venture_root provided
            if "ref" in data and venture_root:
                ref_path = venture_root / data["ref"]
                if ref_path.exists():
                    try:
                        content = ref_path.read_text()[:5000]
                        data = {**data, "content": content}
                    except Exception:
                        pass
            store.seed_from_dict("long_term", domain, data)

    # Seed episodic
    for domain, data in layers.get("episodic", {}).items():
        if isinstance(data, dict):
            # Resolve ref if venture_root provided
            if "ref" in data and venture_root:
                ref_path = venture_root / data["ref"]
                if ref_path.exists():
                    try:
                        content = ref_path.read_text()[:5000]
                        data = {**data, "content": content}
                    except Exception:
                        pass
            store.seed_from_dict("episodic", domain, data)

    # Seed semantic
    for domain, data in layers.get("semantic", {}).items():
        if isinstance(data, dict):
            # Resolve ref if venture_root provided
            if "ref" in data and venture_root:
                ref_path = venture_root / data["ref"]
                if ref_path.exists():
                    try:
                        content = ref_path.read_text()[:5000]
                        data = {**data, "content": content}
                    except Exception:
                        pass
            store.seed_from_dict("semantic", domain, data)

    return store
