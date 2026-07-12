"""LLM Ops tracing system for TAZ OS — observability for agent runs.

Captures the full event tree per cycle:
  - Node execution (agent runs, duration, status)
  - Tool calls (tool name, args, result, duration)
  - LLM calls (model, tokens, latency)
  - Retrieval events (memory lookups, context building)

Integration options:
  - Langfuse (preferred, open-source)
  - Custom JSON-based tracing (fallback)

Events are emitted asynchronously to avoid blocking graph execution.

Usage:
    from aos.tracing import get_tracer, LangfuseTracer

    tracer = get_tracer()  # Auto-detects Langfuse or falls back to JSON

    # Start cycle trace
    tracer.start_cycle(cycle_id="2026-07-02-executive", venture_id="netso")

    # Log node execution
    tracer.log_node(
        node_name="review",
        agent_id="AGT-EXEC-COO",
        status="success",
        duration_ms=1234,
        output={"summary": "..."}
    )

    # Log LLM call
    tracer.log_llm(
        agent_id="AGT-EXEC-COO",
        model="claude-sonnet-4-20250514",
        prompt_tokens=1000,
        completion_tokens=500,
        latency_ms=800
    )

    # Log tool call
    tracer.log_tool(
        agent_id="AGT-EXEC-LEGAL",
        tool_name="read_dashboard",
        args={"path": "/path/to/file"},
        result={"ok": True, "content": "..."},
        duration_ms=50
    )

    # End cycle
    tracer.end_cycle(status="success", total_duration_ms=15000)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


# ---------------------------------------------------------------------------
# Event data models
# ---------------------------------------------------------------------------

@dataclass
class NodeEvent:
    """Event for a graph node execution."""
    node_name: str
    agent_id: str | None
    status: str  # success, error, skipped
    duration_ms: int
    output: dict[str, Any]
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class LLMEvent:
    """Event for an LLM completion call."""
    agent_id: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    provider: str = "unknown"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ToolEvent:
    """Event for a tool call."""
    agent_id: str
    tool_name: str
    args: dict[str, Any]
    result: dict[str, Any]
    duration_ms: int
    status: str  # success, error
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RetrievalEvent:
    """Event for memory/context retrieval."""
    agent_id: str
    retrieval_type: str  # memory, artifact, context
    query: str
    results_count: int
    duration_ms: int
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# Tracer protocol
# ---------------------------------------------------------------------------

class Tracer(Protocol):
    """Abstract interface for tracing backends."""

    def start_cycle(
        self,
        cycle_id: str,
        venture_id: str,
        harness_id: str = "HAR-EXEC-001",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Start a new cycle trace."""
        ...

    def log_node(
        self,
        node_name: str,
        agent_id: str | None,
        status: str,
        duration_ms: int,
        output: dict[str, Any],
        error: str | None = None,
    ) -> None:
        """Log a graph node execution."""
        ...

    def log_llm(
        self,
        agent_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        provider: str = "unknown",
    ) -> None:
        """Log an LLM completion call."""
        ...

    def log_tool(
        self,
        agent_id: str,
        tool_name: str,
        args: dict[str, Any],
        result: dict[str, Any],
        duration_ms: int,
        status: str = "success",
    ) -> None:
        """Log a tool call."""
        ...

    def log_retrieval(
        self,
        agent_id: str,
        retrieval_type: str,
        query: str,
        results_count: int,
        duration_ms: int,
    ) -> None:
        """Log a memory/context retrieval."""
        ...

    def end_cycle(
        self,
        status: str,
        total_duration_ms: int,
        error: str | None = None,
    ) -> None:
        """End the current cycle trace."""
        ...

    def flush(self) -> None:
        """Flush any pending events."""
        ...


# ---------------------------------------------------------------------------
# JSON-based tracer (fallback implementation)
# ---------------------------------------------------------------------------

class JSONTracer:
    """Simple JSON-based tracer that writes events to disk.

    Events are written to ~/.aos/traces/{cycle_id}.json
    Each trace file contains the full event tree for one cycle.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir or Path.home() / ".aos" / "traces"
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._cycle_id: str | None = None
        self._venture_id: str | None = None
        self._harness_id: str | None = None
        self._start_time: float = 0
        self._events: list[dict[str, Any]] = []
        self._metadata: dict[str, Any] = {}

    def start_cycle(
        self,
        cycle_id: str,
        venture_id: str,
        harness_id: str = "HAR-EXEC-001",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._cycle_id = cycle_id
        self._venture_id = venture_id
        self._harness_id = harness_id
        self._start_time = time.monotonic()
        self._events = []
        self._metadata = metadata or {}

    def log_node(
        self,
        node_name: str,
        agent_id: str | None,
        status: str,
        duration_ms: int,
        output: dict[str, Any],
        error: str | None = None,
    ) -> None:
        event = NodeEvent(
            node_name=node_name,
            agent_id=agent_id,
            status=status,
            duration_ms=duration_ms,
            output=output,
            error=error,
        )
        self._events.append({
            "type": "node",
            "data": {
                "node_name": event.node_name,
                "agent_id": event.agent_id,
                "status": event.status,
                "duration_ms": event.duration_ms,
                "output": event.output,
                "error": event.error,
                "timestamp": event.timestamp,
            },
        })

    def log_llm(
        self,
        agent_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        provider: str = "unknown",
    ) -> None:
        event = LLMEvent(
            agent_id=agent_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            provider=provider,
        )
        self._events.append({
            "type": "llm",
            "data": {
                "agent_id": event.agent_id,
                "model": event.model,
                "prompt_tokens": event.prompt_tokens,
                "completion_tokens": event.completion_tokens,
                "total_tokens": event.prompt_tokens + event.completion_tokens,
                "latency_ms": event.latency_ms,
                "provider": event.provider,
                "timestamp": event.timestamp,
            },
        })

    def log_tool(
        self,
        agent_id: str,
        tool_name: str,
        args: dict[str, Any],
        result: dict[str, Any],
        duration_ms: int,
        status: str = "success",
    ) -> None:
        event = ToolEvent(
            agent_id=agent_id,
            tool_name=tool_name,
            args=args,
            result=result,
            duration_ms=duration_ms,
            status=status,
        )
        self._events.append({
            "type": "tool",
            "data": {
                "agent_id": event.agent_id,
                "tool_name": event.tool_name,
                "args": event.args,
                "result": event.result,
                "duration_ms": event.duration_ms,
                "status": event.status,
                "timestamp": event.timestamp,
            },
        })

    def log_retrieval(
        self,
        agent_id: str,
        retrieval_type: str,
        query: str,
        results_count: int,
        duration_ms: int,
    ) -> None:
        event = RetrievalEvent(
            agent_id=agent_id,
            retrieval_type=retrieval_type,
            query=query,
            results_count=results_count,
            duration_ms=duration_ms,
        )
        self._events.append({
            "type": "retrieval",
            "data": {
                "agent_id": event.agent_id,
                "retrieval_type": event.retrieval_type,
                "query": event.query,
                "results_count": event.results_count,
                "duration_ms": event.duration_ms,
                "timestamp": event.timestamp,
            },
        })

    def end_cycle(
        self,
        status: str,
        total_duration_ms: int,
        error: str | None = None,
    ) -> None:
        if not self._cycle_id:
            return

        trace = {
            "cycle_id": self._cycle_id,
            "venture_id": self._venture_id,
            "harness_id": self._harness_id,
            "status": status,
            "total_duration_ms": total_duration_ms,
            "error": error,
            "metadata": self._metadata,
            "events": self._events,
            "summary": self._build_summary(),
        }

        output_file = self.output_dir / f"{self._cycle_id}.json"
        output_file.write_text(json.dumps(trace, indent=2))

    def flush(self) -> None:
        """No-op for JSON tracer (writes on end_cycle)."""
        pass

    def _build_summary(self) -> dict[str, Any]:
        """Build summary statistics from events."""
        llm_events = [e for e in self._events if e["type"] == "llm"]
        tool_events = [e for e in self._events if e["type"] == "tool"]
        node_events = [e for e in self._events if e["type"] == "node"]

        total_tokens = sum(
            e["data"]["total_tokens"] for e in llm_events
        )
        total_llm_latency = sum(
            e["data"]["latency_ms"] for e in llm_events
        )
        total_tool_latency = sum(
            e["data"]["duration_ms"] for e in tool_events
        )

        return {
            "total_llm_calls": len(llm_events),
            "total_tool_calls": len(tool_events),
            "total_nodes": len(node_events),
            "total_tokens": total_tokens,
            "total_llm_latency_ms": total_llm_latency,
            "total_tool_latency_ms": total_tool_latency,
            "successful_nodes": len([e for e in node_events if e["data"]["status"] == "success"]),
            "failed_nodes": len([e for e in node_events if e["data"]["status"] == "error"]),
        }


# ---------------------------------------------------------------------------
# Langfuse tracer (preferred implementation)
# ---------------------------------------------------------------------------

class LangfuseTracer:
    """Langfuse-based tracer with full observability features.

    Requires langfuse package: pip install langfuse
    Reads credentials from environment:
      - LANGFUSE_PUBLIC_KEY
      - LANGFUSE_SECRET_KEY
      - LANGFUSE_HOST (optional, defaults to cloud)
    """

    def __init__(self) -> None:
        try:
            from langfuse import Langfuse
        except ImportError:
            raise ImportError(
                "Langfuse not installed. Install with: pip install langfuse"
            )

        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

        if not public_key or not secret_key:
            raise ValueError(
                "Langfuse credentials not found. Set LANGFUSE_PUBLIC_KEY and "
                "LANGFUSE_SECRET_KEY environment variables."
            )

        self._client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )

        self._trace = None
        self._current_span = None
        self._span_stack: list[Any] = []

    def start_cycle(
        self,
        cycle_id: str,
        venture_id: str,
        harness_id: str = "HAR-EXEC-001",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Start a new cycle trace in Langfuse."""
        self._trace = self._client.trace(
            name=f"cycle_{cycle_id}",
            id=cycle_id,
            metadata={
                "venture_id": venture_id,
                "harness_id": harness_id,
                **(metadata or {}),
            },
        )

    def log_node(
        self,
        node_name: str,
        agent_id: str | None,
        status: str,
        duration_ms: int,
        output: dict[str, Any],
        error: str | None = None,
    ) -> None:
        """Log a graph node execution as a Langfuse span."""
        if not self._trace:
            return

        span = self._trace.span(
            name=node_name,
            metadata={
                "agent_id": agent_id,
                "node_type": "graph_node",
            },
            level="DEFAULT" if status == "success" else "ERROR",
            status_message=error if error else None,
        )

        # Record output
        span.event(
            name=f"{node_name}_output",
            metadata={
                "status": status,
                "duration_ms": duration_ms,
                "output_keys": list(output.keys()),
            },
        )

        span.end()

    def log_llm(
        self,
        agent_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        provider: str = "unknown",
    ) -> None:
        """Log an LLM call as a Langfuse generation."""
        if not self._trace:
            return

        self._trace.generation(
            name=f"{agent_id}_llm_call",
            model=model,
            usage={
                "input": prompt_tokens,
                "output": completion_tokens,
                "total": prompt_tokens + completion_tokens,
            },
            metadata={
                "agent_id": agent_id,
                "provider": provider,
                "latency_ms": latency_ms,
            },
        )

    def log_tool(
        self,
        agent_id: str,
        tool_name: str,
        args: dict[str, Any],
        result: dict[str, Any],
        duration_ms: int,
        status: str = "success",
    ) -> None:
        """Log a tool call as a Langfuse span."""
        if not self._trace:
            return

        span = self._trace.span(
            name=f"tool_{tool_name}",
            metadata={
                "agent_id": agent_id,
                "tool_name": tool_name,
                "duration_ms": duration_ms,
            },
            level="DEFAULT" if status == "success" else "ERROR",
        )

        span.event(
            name=f"{tool_name}_call",
            metadata={
                "args": args,
                "result_keys": list(result.keys()),
                "status": status,
            },
        )

        span.end()

    def log_retrieval(
        self,
        agent_id: str,
        retrieval_type: str,
        query: str,
        results_count: int,
        duration_ms: int,
    ) -> None:
        """Log a retrieval event as a Langfuse span."""
        if not self._trace:
            return

        span = self._trace.span(
            name=f"retrieval_{retrieval_type}",
            metadata={
                "agent_id": agent_id,
                "query": query[:200],  # Truncate long queries
                "results_count": results_count,
                "duration_ms": duration_ms,
            },
        )

        span.end()

    def end_cycle(
        self,
        status: str,
        total_duration_ms: int,
        error: str | None = None,
    ) -> None:
        """End the cycle trace."""
        if not self._trace:
            return

        self._trace.update(
            output={
                "status": status,
                "total_duration_ms": total_duration_ms,
                "error": error,
            },
        )

    def flush(self) -> None:
        """Flush pending events to Langfuse."""
        if self._client:
            self._client.flush()


# ---------------------------------------------------------------------------
# Null tracer (no-op for disabled tracing)
# ---------------------------------------------------------------------------

class NullTracer:
    """No-op tracer for when tracing is disabled."""

    def start_cycle(
        self,
        cycle_id: str,
        venture_id: str,
        harness_id: str = "HAR-EXEC-001",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        pass

    def log_node(
        self,
        node_name: str,
        agent_id: str | None,
        status: str,
        duration_ms: int,
        output: dict[str, Any],
        error: str | None = None,
    ) -> None:
        pass

    def log_llm(
        self,
        agent_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: int,
        provider: str = "unknown",
    ) -> None:
        pass

    def log_tool(
        self,
        agent_id: str,
        tool_name: str,
        args: dict[str, Any],
        result: dict[str, Any],
        duration_ms: int,
        status: str = "success",
    ) -> None:
        pass

    def log_retrieval(
        self,
        agent_id: str,
        retrieval_type: str,
        query: str,
        results_count: int,
        duration_ms: int,
    ) -> None:
        pass

    def end_cycle(
        self,
        status: str,
        total_duration_ms: int,
        error: str | None = None,
    ) -> None:
        pass

    def flush(self) -> None:
        pass


# ---------------------------------------------------------------------------
# Tracer factory and global instance
# ---------------------------------------------------------------------------

_GLOBAL_TRACER: Tracer | None = None


def get_tracer(force_backend: str | None = None) -> Tracer:
    """Get or create the global tracer instance.

    Args:
        force_backend: Force a specific backend ("langfuse", "json", "null")
                      If None, auto-detects in order: Langfuse -> JSON

    Returns:
        Tracer instance (Langfuse, JSON, or Null)

    Environment variables:
        AOS_TRACING: "enabled" | "disabled" (default: enabled)
        AOS_TRACING_BACKEND: "langfuse" | "json" | "auto" (default: auto)
    """
    global _GLOBAL_TRACER

    if _GLOBAL_TRACER is not None:
        return _GLOBAL_TRACER

    # Check if tracing is disabled
    tracing_enabled = os.environ.get("AOS_TRACING", "enabled").lower()
    if tracing_enabled == "disabled":
        _GLOBAL_TRACER = NullTracer()
        return _GLOBAL_TRACER

    # Determine backend
    backend = force_backend or os.environ.get("AOS_TRACING_BACKEND", "auto")

    if backend == "langfuse":
        try:
            _GLOBAL_TRACER = LangfuseTracer()
            return _GLOBAL_TRACER
        except (ImportError, ValueError) as e:
            print(f"Warning: Langfuse tracer unavailable ({e}), falling back to JSON")
            backend = "json"

    if backend == "json":
        _GLOBAL_TRACER = JSONTracer()
        return _GLOBAL_TRACER

    if backend == "null":
        _GLOBAL_TRACER = NullTracer()
        return _GLOBAL_TRACER

    # Auto-detect: try Langfuse first, fall back to JSON
    if backend == "auto":
        try:
            _GLOBAL_TRACER = LangfuseTracer()
            return _GLOBAL_TRACER
        except (ImportError, ValueError):
            _GLOBAL_TRACER = JSONTracer()
            return _GLOBAL_TRACER

    # Default: JSON
    _GLOBAL_TRACER = JSONTracer()
    return _GLOBAL_TRACER


def set_tracer(tracer: Tracer) -> None:
    """Set the global tracer instance (for testing)."""
    global _GLOBAL_TRACER
    _GLOBAL_TRACER = tracer


def reset_tracer() -> None:
    """Reset the global tracer instance (for testing)."""
    global _GLOBAL_TRACER
    _GLOBAL_TRACER = None
