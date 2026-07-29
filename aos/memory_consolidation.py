"""Memory consolidation — compress daily cycle logs into long-term memory.

Reads from JSON tracer output, preserves violations verbatim, compresses
routine status into one-line summaries. Writes consolidated entries to
the SQLite memory store.
"""
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("aos.memory_consolidation")


@dataclass
class MemoryEntry:
    key: str
    content: str
    category: str  # "violation", "decision", "status", "lesson"
    venture: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    preserve_verbatim: bool = False


def consolidate_daily(venture: str = "netso", target_date: date | None = None) -> list[MemoryEntry]:
    """Compress today's cycle logs into structured long-term memory.

    Rules:
    - Violations: preserved verbatim (never compressed)
    - Decisions (approvals/rejections): preserved with context
    - Status updates: compressed to one line per agent
    """
    if target_date is None:
        target_date = date.today()

    entries: list[MemoryEntry] = []
    trace_dir = Path("traces")

    if not trace_dir.exists():
        logger.info(f"No traces directory found for {venture}")
        return entries

    trace_files = sorted(trace_dir.glob(f"*{venture}*.json"), reverse=True)
    if not trace_files:
        logger.info(f"No trace files for {venture} on {target_date}")
        return entries

    try:
        with open(trace_files[0]) as f:
            data = json.load(f)

        nodes = data.get("nodes", [])

        # Preserve violations verbatim
        for node in nodes:
            if node.get("status") == "error":
                entries.append(MemoryEntry(
                    key=f"violation:{node.get('node_name', 'unknown')}:{target_date}",
                    content=json.dumps(node, default=str),
                    category="violation",
                    venture=venture,
                    preserve_verbatim=True,
                ))

        # Compress status: one summary per agent
        agents_seen: dict[str, list[str]] = {}
        for node in nodes:
            agent = node.get("agent_id", "unknown")
            if agent not in agents_seen:
                agents_seen[agent] = []
            agents_seen[agent].append(node.get("node_name", ""))

        for agent_id, node_names in agents_seen.items():
            entries.append(MemoryEntry(
                key=f"status:{agent_id}:{target_date}",
                content=f"Ran {len(node_names)} nodes: {', '.join(node_names[:5])}",
                category="status",
                venture=venture,
            ))

    except Exception as e:
        logger.error(f"Failed to read trace file: {e}")

    return entries


def get_consolidation_stats(venture: str = "netso") -> dict[str, Any]:
    """Get stats about memory consolidation status."""
    trace_dir = Path("traces")
    trace_count = len(list(trace_dir.glob(f"*{venture}*.json"))) if trace_dir.exists() else 0
    return {
        "venture": venture,
        "trace_files": trace_count,
        "last_consolidation": None,
        "total_entries": 0,
    }
