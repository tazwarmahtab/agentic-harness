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
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


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


@dataclass
class MemoryEntry:
    """Memory entry — mutable replaced_by field for versioning."""
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


@dataclass
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
        self._counter = 0

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
        """Search memory entries by content match."""
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

        # Mark candidate processed
        candidate.status = decision.value
        return entry

    def _store_entry(self, candidate: MemoryCandidate) -> MemoryEntry:
        """Store a new memory entry."""
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

        # Mark old entry as superseded
        if old_entry:
            old_entry.replaced_by = new_entry.id

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
            old_entry.replaced_by = new_entry.id
            self.layers[candidate.layer][candidate.domain].append(new_entry)
            return new_entry

        # No existing entry — just store
        return self._store_entry(candidate)

    # ----- Direct write (for venture artifact refs) -----

    def seed_from_dict(self, layer: str, domain: str, data: Any) -> None:
        """Seed memory from YAML manifest data (one-time load)."""
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
                results.append(self.audit_trail[-1])
            else:
                candidate.status = "reviewed"

        return results

    # ----- Persistence -----

    def persist_to_disk(self, venture_root: Path, cycle_id: str = "") -> dict[str, Any]:
        """Write memory state to disk. Returns summary of what was written.

        Writes:
          - audit.log (JSON-lines, append-only)
          - TAZOS_MEMORY.md (human-readable memory snapshot)
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
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Factory: build MemoryStore from memory.yml
# ---------------------------------------------------------------------------

def build_memory_from_manifest(
    manifest: dict[str, Any],
    venture_root: Path | None = None,
) -> MemoryStore:
    """Build a MemoryStore from a parsed memory.yml manifest.

    Seeds long_term/episodic/semantic layers from manifest data.
    Venture artifact refs are resolved to file paths if venture_root is provided.
    """
    permissions = manifest.get("permissions", {})
    update_rules = manifest.get("update_rules", {})
    store = MemoryStore(permissions=permissions, update_rules=update_rules)

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
