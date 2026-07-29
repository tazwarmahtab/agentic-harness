"""Graph state types, config, and small helpers for the AOS orchestrator.

Separated from graph.py to keep the state schema importable without
pulling in the full LangGraph/node machinery.
"""

from __future__ import annotations

import operator
import copy
import logging
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from aos.registry import HarnessBundle
from aos.llm import LLMClient
from aos.memory import MemoryStore
from aos.tools import ToolGateway
from aos.usage import UsageTracker

logger = logging.getLogger("aos.graph")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CONCURRENCY = 8
MEMORY_CONTEXT_CHAR_LIMIT = 3000
ARTIFACT_READ_LIMIT_CHARS = 2000
CONSENSUS_WEIGHT_THRESHOLD = 0.67


# ---------------------------------------------------------------------------
# Graph state — TypedDict with reducers for accumulating fields
# ---------------------------------------------------------------------------


class CycleState(TypedDict, total=False):
    """LangGraph state for one execution cycle.

    Fields with ``Annotated[..., operator.add]`` use list concatenation as
    their reducer — each node returns a single-element list that gets
    appended to the accumulated list.  Scalar / dict fields are overwritten
    by each node's partial return.

    Loop Engineering Fields:
        iteration_count: Current iteration number (0-indexed)
        max_iterations: Maximum allowed iterations (default: 1 for single-pass)
        completion_criteria: Dict defining when loop should terminate
        loop_context_summary: Compressed summary from previous iteration
        iteration_history: List of iteration summaries for tracking progress
    """

    # --- Identity (set once at init) ---
    venture_id: str
    harness_id: str
    cycle_id: str

    # --- Input data ---
    venture_artifacts: dict[str, Any]
    inputs: dict[str, Any]

    # --- Accumulated results (reducer: list concat) ---
    step_results: Annotated[list[dict[str, Any]], operator.add]
    approval_queue: Annotated[list[dict[str, Any]], operator.add]
    resolved_approval_ids: Annotated[list[str], operator.add]
    handoffs: Annotated[list[dict[str, Any]], operator.add]
    errors: Annotated[list[str], operator.add]

    # --- Per-step outputs (overwritten each step) ---
    review_output: dict[str, Any]
    prioritize_output: dict[str, Any]
    delegate_output: dict[str, Any]
    specialists_output: dict[str, Any]
    summarize_output: dict[str, Any]
    approval_gates_output: dict[str, Any]
    execute_output: dict[str, Any]
    log_output: dict[str, Any]

    # --- Loop Engineering ---
    iteration_count: int
    max_iterations: int
    completion_criteria: dict[str, Any]
    loop_context_summary: str
    iteration_history: Annotated[list[dict[str, Any]], operator.add]


# ---------------------------------------------------------------------------
# Infrastructure config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphConfig:
    """Infrastructure objects that nodes need but don't belong in state."""

    bundle: HarnessBundle
    llm: LLMClient
    tool_gateway: ToolGateway | None = None
    memory_store: MemoryStore | None = None
    usage_tracker: UsageTracker | None = None
    registry: Any = None  # Registry | None — avoid circular import
    approval_queue: Any = None  # ApprovalQueue | None
    venture_constants: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def _step_result_to_list(result: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a step result dict into a one-element list for the reducer."""
    clean = {k: v for k, v in result.items() if k != "_errors"}
    return [clean]


def _get_errors(result: dict[str, Any]) -> list[str]:
    """Extract errors from a step result."""
    return result.get("_errors", [])


def _get_step_output(state: CycleState, step_name: str) -> dict[str, Any]:
    """Get the output of the most recent successful step by name."""
    output_field = f"{step_name}_output"
    if output_field in state and state[output_field]:
        return state[output_field]
    # Fallback: search step_results in reverse
    for r in reversed(state.get("step_results", [])):
        if r.get("step") == step_name and r.get("status") == "success":
            return r.get("output", {})
    return {}
