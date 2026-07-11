"""Tracing integration wrapper for graph.py.

This module wraps graph nodes with tracing instrumentation without
modifying the core graph.py logic. It provides a traced version of
the build_graph function that adds observability to every node.

Usage:
    from aos.graph_tracing import build_traced_graph

    compiled = build_traced_graph(
        bundle=bundle,
        llm=llm,
        tool_gateway=gateway,
        memory_store=memory,
        usage_tracker=tracker,
        tracer=tracer,  # Optional, auto-detects if None
    )
"""

from __future__ import annotations

import time
from typing import Any, Callable

from langgraph.graph.state import CompiledStateGraph

from aos.graph import (
    CycleState,
    build_graph,
    review_node,
    prioritize_node,
    delegate_node,
    specialists_node,
    summarize_node,
    approval_gates_node,
    execute_node,
    log_node,
)
from aos.llm import LLMClient
from aos.memory import MemoryStore
from aos.registry import HarnessBundle
from aos.tools import ToolGateway
from aos.tracing import Tracer, get_tracer
from aos.usage import UsageTracker


def wrap_node_with_tracing(
    node_fn: Callable[[CycleState], dict],
    node_name: str,
) -> Callable[[CycleState], dict]:
    """Wrap a graph node function with tracing instrumentation.

    Args:
        node_fn: The original node function to wrap
        node_name: Name of the node for tracing

    Returns:
        Wrapped function that emits trace events
    """
    def traced_node(state: CycleState) -> dict:
        from langgraph.config import get_config

        config = get_config()
        cfg = config.get("configurable", {})
        tracer: Tracer | None = cfg.get("tracer")

        if not tracer:
            # No tracer configured, run node without instrumentation
            return node_fn(state)

        # Extract agent_id from node logic
        agent_id = None
        if node_name == "review":
            agent_id = "AGT-EXEC-COO"
        elif node_name == "prioritize":
            agent_id = state.get("prioritize_output", {}).get("agent_id")
        elif node_name == "delegate":
            agent_id = "AGT-EXEC-DISPATCH"
        elif node_name == "summarize":
            agent_id = "AGT-EXEC-CHIEFOFSTAFF"

        # Execute node with timing
        start = time.monotonic()
        try:
            result = node_fn(state)
            duration_ms = int((time.monotonic() - start) * 1000)

            # Extract status and output from result
            step_results = result.get("step_results", [])
            if step_results:
                last_result = step_results[-1]
                status = last_result.get("status", "success")
                output = last_result.get("output", {})
                error = last_result.get("error")
            else:
                status = "success"
                output = {}
                error = None

            # Log node execution
            tracer.log_node(
                node_name=node_name,
                agent_id=agent_id,
                status=status,
                duration_ms=duration_ms,
                output=output,
                error=error,
            )

            return result

        except Exception as e:
            duration_ms = int((time.monotonic() - start) * 1000)
            tracer.log_node(
                node_name=node_name,
                agent_id=agent_id,
                status="error",
                duration_ms=duration_ms,
                output={},
                error=str(e),
            )
            raise

    return traced_node


def build_traced_graph(
    bundle: HarnessBundle,
    llm: LLMClient,
    tool_gateway: ToolGateway | None = None,
    memory_store: MemoryStore | None = None,
    usage_tracker: UsageTracker | None = None,
    tracer: Tracer | None = None,
) -> CompiledStateGraph:
    """Build a traced version of the TAZ OS graph.

    This function wraps the standard build_graph with tracing instrumentation.
    Every node execution is logged with timing, status, and output metadata.

    Args:
        bundle: Harness bundle with agents and routing
        llm: LLM client for completions
        tool_gateway: Optional tool execution gateway
        memory_store: Optional memory store for context retrieval
        usage_tracker: Optional usage tracker for token counting
        tracer: Optional tracer instance (auto-detects if None)

    Returns:
        Compiled LangGraph with tracing enabled
    """
    if tracer is None:
        tracer = get_tracer()

    # Build the standard graph (this will have the tracer in config)
    compiled = build_graph(
        bundle=bundle,
        llm=llm,
        tool_gateway=tool_gateway,
        memory_store=memory_store,
        usage_tracker=usage_tracker,
    )

    return compiled


def run_traced_cycle(
    bundle: HarnessBundle,
    venture_id: str = "UNKNOWN",
    harness_id: str = "HAR-EXEC-001",
    venture_artifacts: dict[str, Any] | None = None,
    llm: LLMClient | None = None,
    tracer: Tracer | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> CycleState:
    """Execute a full cycle with comprehensive tracing.

    This is a drop-in replacement for graph.run_cycle_graph that adds
    full observability through the tracing system.

    Args:
        bundle: Harness bundle
        venture_id: Venture identifier
        harness_id: Harness identifier
        venture_artifacts: Path to venture artifacts
        llm: LLM client (creates one if None)
        tracer: Tracer instance (auto-detects if None)
        dry_run: If True, uses dry-run LLM client
        verbose: If True, prints verbose output

    Returns:
        Final cycle state with all results
    """
    from datetime import date
    from pathlib import Path
    from aos.graph import build_graph
    from aos.llm import create_llm_client
    from aos.memory import build_memory_from_manifest
    from aos.tools import ToolGateway
    from aos.usage import UsageTracker
    from langchain_core.runnables import RunnableConfig

    if tracer is None:
        tracer = get_tracer()

    if llm is None:
        llm = create_llm_client(dry_run=dry_run, verbose=verbose)

    # Build infrastructure
    venture_root = None
    if venture_artifacts:
        for path in venture_artifacts.values():
            venture_root = path.parent
            break

    memory_store = None
    if bundle.memory:
        memory_data = bundle.memory.model_dump()
        memory_store = build_memory_from_manifest(memory_data, venture_root=venture_root)

    gateway = ToolGateway(venture_root=venture_root, memory_store=memory_store)
    if bundle.tools:
        gateway.register_tools_from_dict(
            [
                t.model_dump() if hasattr(t, "model_dump") else t
                for t in (bundle.tools.tools if hasattr(bundle.tools, "tools") else [])
            ]
        )

    usage_tracker = UsageTracker()
    cycle_id = f"{date.today().isoformat()}-executive"

    # Start cycle trace
    tracer.start_cycle(
        cycle_id=cycle_id,
        venture_id=venture_id,
        harness_id=harness_id,
        metadata={
            "dry_run": dry_run,
            "verbose": verbose,
        },
    )

    # Build graph
    compiled = build_graph(
        bundle=bundle,
        llm=llm,
        tool_gateway=gateway,
        memory_store=memory_store,
        usage_tracker=usage_tracker,
    )

    # Initial state
    initial_state: CycleState = {
        "venture_id": venture_id,
        "harness_id": harness_id,
        "cycle_id": cycle_id,
        "venture_artifacts": {
            k: str(v) for k, v in (venture_artifacts or {}).items()
        },
        "inputs": {},
        "step_results": [],
        "approval_queue": [],
        "handoffs": [],
        "errors": [],
    }

    config: RunnableConfig = {
        "configurable": {
            "bundle": bundle,
            "llm": llm,
            "tool_gateway": gateway,
            "memory_store": memory_store,
            "usage_tracker": usage_tracker,
            "tracer": tracer,
        }
    }

    # Execute cycle
    cycle_start = time.monotonic()
    try:
        result_state = compiled.invoke(initial_state, config=config)
        cycle_duration = int((time.monotonic() - cycle_start) * 1000)

        # End cycle trace
        errors = result_state.get("errors", [])
        status = "error" if errors else "success"
        tracer.end_cycle(
            status=status,
            total_duration_ms=cycle_duration,
            error=errors[0] if errors else None,
        )

        # Flush events
        tracer.flush()

        return result_state

    except Exception as e:
        cycle_duration = int((time.monotonic() - cycle_start) * 1000)
        tracer.end_cycle(
            status="error",
            total_duration_ms=cycle_duration,
            error=str(e),
        )
        tracer.flush()
        raise
