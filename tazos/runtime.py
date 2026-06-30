"""Harness runtime — executes the daily execution cycle.

Orchestrates: review → prioritize → delegate → run_agents → summarize →
request_approvals → execute → log.

Each step reads inputs, calls agents via LLM, produces artifacts, and
validates outputs. The runtime is the "Jarvis" loop.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from tazos.llm import LLMClient, LLMResponse, DryRunLLMClient, resolve_model, create_llm_client
from tazos.registry import Registry, HarnessBundle, load_registry
from tazos.schemas.agent import Agent
from tazos.tools import ToolGateway, ToolResult
from tazos.memory import MemoryStore, build_memory_from_manifest, Decision
from tazos.usage import UsageTracker


# ---------------------------------------------------------------------------
# Execution context — passed through every step
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    """Result of executing one step in the cycle."""
    step: str
    agent_id: str | None = None
    status: str = "pending"  # pending, running, success, error, skipped
    output: dict[str, Any] = field(default_factory=dict)
    artifacts: list[Path] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0


@dataclass
class CycleContext:
    """Mutable context shared across all steps in one execution cycle."""
    venture_id: str
    harness_id: str
    cycle_id: str  # e.g. "2026-06-30-executive"
    started_at: datetime = field(default_factory=datetime.now)
    venture_artifacts: dict[str, Path] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)
    step_results: list[StepResult] = field(default_factory=list)
    approval_queue: list[dict[str, Any]] = field(default_factory=list)
    handoffs: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    tool_gateway: ToolGateway | None = None
    memory_store: MemoryStore | None = None
    usage_tracker: UsageTracker | None = None
    usage_tracker: UsageTracker | None = None

    def add_result(self, result: StepResult) -> None:
        self.step_results.append(result)

    def get_step_output(self, step_name: str) -> dict[str, Any] | None:
        for r in self.step_results:
            if r.step == step_name and r.status == "success":
                return r.output
        return None

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [
            f"Cycle: {self.cycle_id}",
            f"Harness: {self.harness_id}",
            f"Venture: {self.venture_id}",
            f"Started: {self.started_at.isoformat()}",
            f"Steps completed: {sum(1 for r in self.step_results if r.status == 'success')}/{len(self.step_results)}",
            f"Errors: {len(self.errors)}",
            f"Approvals pending: {len(self.approval_queue)}",
            f"Handoffs created: {len(self.handoffs)}",
        ]
        if self.errors:
            lines.append("\nErrors:")
            for e in self.errors:
                lines.append(f"  - {e}")
        if self.usage_tracker:
            usage = self.usage_tracker.report()
            if usage.total_calls > 0:
                lines.append(f"\nUsage: {usage.total_calls} calls, {usage.total_tokens} tokens")
                for agent_id, data in usage.by_agent.items():
                    tokens = data["prompt_tokens"] + data["completion_tokens"]
                    lines.append(f"  {agent_id}: {tokens} tokens")
        lines.append("\nStep details:")
        for r in self.step_results:
            status_icon = {"success": "✓", "error": "✗", "skipped": "○", "pending": "·"}.get(r.status, "?")
            agent_str = f" ({r.agent_id})" if r.agent_id else ""
            lines.append(f"  [{status_icon}] {r.step}{agent_str}: {r.status} ({r.duration_ms}ms)")
            if r.error:
                lines.append(f"      Error: {r.error}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Agent runner — builds prompt from agent manifest, calls LLM
# ---------------------------------------------------------------------------

def _build_agent_system_prompt(agent: Agent, bundle: HarnessBundle) -> str:
    """Build the system prompt for an agent from its manifest.

    Uses context.build_prompt for full contract serialization including
    financial ground truth for CFO agents.
    """
    from tazos.context import build_prompt
    from tazos.constants import NETSO_FINANCIAL

    netso_financial = NETSO_FINANCIAL if agent.financial_rules else None
    return build_prompt(agent, netso_financial=netso_financial)


def _build_task_prompt(
    step_name: str,
    agent: Agent,
    ctx: CycleContext,
    inputs: dict[str, Any],
) -> str:
    """Build the user-facing task prompt for one execution step."""
    parts = [
        f"[Step: {step_name}]",
        f"Cycle: {ctx.cycle_id}",
        f"Venture: {ctx.venture_id}",
        "",
        "Inputs:",
    ]

    for key, value in inputs.items():
        if isinstance(value, str) and len(value) > 500:
            parts.append(f"  {key}: {value[:500]}...")
        else:
            parts.append(f"  {key}: {value}")

    if ctx.approval_queue:
        parts.append(f"\nPending approvals: {len(ctx.approval_queue)} items")

    parts.append(f"\nExecute your role for this step. Output structured results.")
    return "\n".join(parts)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from text that may contain markdown.

    Handles:
      - Raw JSON
      - JSON wrapped in ```json ... ``` code blocks
      - JSON preceded/followed by markdown prose
    Returns None if no valid JSON found.
    """
    # Try raw parse first
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Try extracting from ```json ... ``` blocks
    import re
    code_blocks = re.findall(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    for block in code_blocks:
        try:
            result = json.loads(block.strip())
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            continue

    # Try finding first { ... } that looks like a complete object
    depth = 0
    start_idx = -1
    for i, c in enumerate(text):
        if c == "{":
            if depth == 0:
                start_idx = i
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0 and start_idx >= 0:
                try:
                    result = json.loads(text[start_idx : i + 1])
                    if isinstance(result, dict):
                        return result
                except (json.JSONDecodeError, ValueError):
                    start_idx = -1

    return None


def _run_agent(
    agent: Agent,
    bundle: HarnessBundle,
    step_name: str,
    ctx: CycleContext,
    inputs: dict[str, Any],
    llm: LLMClient,
) -> StepResult:
    """Run a single agent for one step."""
    import time
    start = time.monotonic()

    # Retrieve memory context for this agent (if memory store available)
    memory_context = None
    if ctx.memory_store:
        try:
            memory_context = ctx.memory_store.retrieve_for_agent(agent.id, step_name)
        except AttributeError:
            pass  # retrieve_for_agent not yet implemented — Phase 7 Task 3

    # Build system prompt with memory context
    from tazos.context import build_prompt
    from tazos.constants import NETSO_FINANCIAL
    netso_financial = NETSO_FINANCIAL if agent.financial_rules else None
    system_prompt = build_prompt(agent, netso_financial=netso_financial, memory_context=memory_context)
    task_prompt = _build_task_prompt(step_name, agent, ctx, inputs)

    # Use agent-level model override if set, else resolve from criticality
    agent_model = None
    if agent.models and agent.models.preferred:
        agent_model = agent.models.preferred
    model = resolve_model(agent.criticality.value, override=agent_model)

    # Use low temperature for structured output agents (dispatcher)
    temperature = 0.1 if agent.id == "AGT-EXEC-DISPATCH" else 0.3

    try:
        response = llm.complete(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": task_prompt}],
            temperature=temperature,
        )

        # Try to extract JSON (handles code blocks, prose wrapping)
        output: dict[str, Any]
        extracted = _extract_json(response.content)
        if extracted:
            output = extracted
        else:
            output = {"raw_response": response.content}

        # Track usage
        if ctx.usage_tracker:
            ctx.usage_tracker.record(agent.id, model, response.usage)

        # Validate output against ground truth
        from tazos.evaluator import validate_output
        from tazos.constants import NETSO_FINANCIAL
        validation = validate_output(output, agent.id, NETSO_FINANCIAL)
        if not validation.passed:
            for violation in validation.violations:
                ctx.errors.append(f"{agent.id}: {violation}")

        # Attach validation metadata to output
        output["_validation"] = {
            "passed": validation.passed,
            "violations": validation.violations,
            "warnings": validation.warnings,
        }

        elapsed = int((time.monotonic() - start) * 1000)
        return StepResult(
            step=step_name,
            agent_id=agent.id,
            status="success",
            output=output,
            duration_ms=elapsed,
        )

    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return StepResult(
            step=step_name,
            agent_id=agent.id,
            status="error",
            error=str(e),
            duration_ms=elapsed,
        )


# ---------------------------------------------------------------------------
# Step implementations — one function per cycle step
# ---------------------------------------------------------------------------

def step_review(
    ctx: CycleContext,
    bundle: HarnessBundle,
    llm: LLMClient,
) -> StepResult:
    """Step 1: Review all inputs — dashboard, blockers, calendar, email."""
    # Read venture artifacts via tool gateway
    inputs = {}
    if ctx.tool_gateway:
        for key, path in ctx.venture_artifacts.items():
            result = ctx.tool_gateway.call(
                "read_dashboard",
                {"path": str(path)},
                agent_id="AGT-EXEC-COO",
            )
            if result.ok:
                content = result.output.get("content", "")
                inputs[key] = content[:2000] if content else f"(empty: {path})"
            else:
                inputs[key] = f"(could not read {path}: {result.error})"
    else:
        # Fallback: direct file read
        for key, path in ctx.venture_artifacts.items():
            if path.exists():
                try:
                    inputs[key] = path.read_text()[:2000]
                except Exception:
                    inputs[key] = f"(could not read {path})"

    # Delegate to COO for initial scan
    coo = bundle.specialists.get("AGT-EXEC-COO")
    if not coo:
        return StepResult(step="review", status="error", error="COO specialist not found")

    return _run_agent(coo, bundle, "review", ctx, inputs, llm)


def step_prioritize(
    ctx: CycleContext,
    bundle: HarnessBundle,
    llm: LLMClient,
) -> StepResult:
    """Step 2: Planner generates priority list from review."""
    if not bundle.planner:
        return StepResult(step="prioritize", status="error", error="Planner not loaded")

    review_output = ctx.get_step_output("review") or {}
    inputs = {
        "review_summary": review_output,
        "backlog": ctx.inputs.get("backlog", ""),
        "weekly_plan": ctx.inputs.get("weekly_plan", ""),
    }

    return _run_agent(bundle.planner, bundle, "prioritize", ctx, inputs, llm)


def step_delegate(
    ctx: CycleContext,
    bundle: HarnessBundle,
    llm: LLMClient,
) -> StepResult:
    """Step 3: Dispatcher routes priorities to specialist agents."""
    if not bundle.dispatcher:
        return StepResult(step="delegate", status="error", error="Dispatcher not loaded")

    prioritize_output = ctx.get_step_output("prioritize") or {}
    inputs = {
        "priority_list": prioritize_output,
        "routing_table": bundle.dispatcher.routing_table.model_dump() if bundle.dispatcher.routing_table else {},
        "available_agents": [a.id for a in bundle.specialists.values()],
    }

    return _run_agent(bundle.dispatcher, bundle, "delegate", ctx, inputs, llm)


def step_run_specialists(
    ctx: CycleContext,
    bundle: HarnessBundle,
    llm: LLMClient,
) -> StepResult:
    """Step 4: Run assigned specialist agents.

    Expects dispatcher output with 'assignments' list, each entry having
    'agent_id', 'task', and optional 'input' fields. Falls back to
    checking for raw_response containing agent mentions if no assignments.
    """
    delegate_output = ctx.get_step_output("delegate") or {}

    # Primary: structured assignments from dispatcher
    assignments = delegate_output.get("assignments", [])

    # Fallback: if dispatcher returned raw text, try to extract agent mentions
    if not assignments and "raw_response" in delegate_output:
        raw = delegate_output["raw_response"]
        # Look for AGT-EXEC-XXX patterns in the raw response
        import re
        agent_mentions = re.findall(r"AGT-EXEC-[A-Z]+", raw)
        # Deduplicate while preserving order
        seen = set()
        for agent_id in agent_mentions:
            if agent_id not in seen and agent_id in bundle.specialists:
                seen.add(agent_id)
                assignments.append({
                    "agent_id": agent_id,
                    "task": raw[:500],  # pass context
                    "input": "",
                })

    if not assignments:
        return StepResult(
            step="run_specialists",
            status="skipped",
            output={"reason": "No structured assignments from dispatcher"},
        )

    results: list[dict[str, Any]] = []
    for assignment in assignments:
        agent_id = assignment.get("agent_id") or assignment.get("route_to")
        if not agent_id or agent_id not in bundle.specialists:
            continue

        agent = bundle.specialists[agent_id]
        task_input = assignment.get("task", "")
        task_context = assignment.get("input", "")
        inputs = {
            "task": task_input,
            "context": task_context or delegate_output,
            "priority": assignment.get("priority", ""),
            "sla": assignment.get("sla", ""),
        }

        agent_result = _run_agent(agent, bundle, f"specialist:{agent_id}", ctx, inputs, llm)
        results.append({
            "agent_id": agent_id,
            "status": agent_result.status,
            "output": agent_result.output,
        })

        ctx.add_result(agent_result)

        # Collect approval gates
        if "approval_required" in agent_result.output:
            ctx.approval_queue.append(agent_result.output["approval_required"])

    return StepResult(
        step="run_specialists",
        status="success" if results else "skipped",
        output={"specialist_results": results, "approval_count": len(ctx.approval_queue)},
    )


def step_summarize(
    ctx: CycleContext,
    bundle: HarnessBundle,
    llm: LLMClient,
) -> StepResult:
    """Step 5: Chief of Staff composes the daily brief."""
    chief = bundle.specialists.get("AGT-EXEC-CHIEFOFSTAFF")
    if not chief:
        return StepResult(step="summarize", status="error", error="Chief of Staff not found")

    # Gather all step outputs
    inputs = {
        "priority_list": ctx.get_step_output("prioritize") or {},
        "dispatch_summary": ctx.get_step_output("delegate") or {},
        "specialist_results": ctx.get_step_output("run_specialists") or {},
        "approval_queue": ctx.approval_queue,
        "dashboard": ctx.inputs.get("dashboard", ""),
        "blockers": ctx.inputs.get("blockers", ""),
    }

    return _run_agent(chief, bundle, "summarize", ctx, inputs, llm)


def step_approval_gates(
    ctx: CycleContext,
    bundle: HarnessBundle,
    llm: LLMClient,
) -> StepResult:
    """Step 6: Validate approval gates — bundle for founder."""
    chief = bundle.specialists.get("AGT-EXEC-CHIEFOFSTAFF")

    # Bundle approvals (no LLM needed — pure logic)
    bundled = {
        "total_pending": len(ctx.approval_queue),
        "items": ctx.approval_queue,
        "format": "approve_all | review_individually | reject",
        "delivery": "console_queue",
    }

    return StepResult(
        step="approval_gates",
        agent_id=chief.id if chief else None,
        status="success",
        output=bundled,
    )


def step_execute(
    ctx: CycleContext,
    bundle: HarnessBundle,
    llm: LLMClient,
) -> StepResult:
    """Step 7: Execute approved actions, create handoffs."""
    # For now, log what would execute. Real execution requires tool gateway.
    executed = []
    for handoff in ctx.handoffs:
        executed.append({"type": "handoff", "status": "queued", **handoff})

    return StepResult(
        step="execute",
        status="success",
        output={"executed": executed, "handoff_count": len(ctx.handoffs)},
    )


def step_log(
    ctx: CycleContext,
    bundle: HarnessBundle,
    llm: LLMClient,
) -> StepResult:
    """Step 8: Log decisions, review memory candidates, persist to disk."""
    # Build the cycle summary log entry
    log_entry = {
        "cycle_id": ctx.cycle_id,
        "timestamp": ctx.started_at.isoformat(),
        "harness_id": ctx.harness_id,
        "steps_completed": [r.step for r in ctx.step_results if r.status == "success"],
        "steps_failed": [r.step for r in ctx.step_results if r.status == "error"],
        "approval_queue_size": len(ctx.approval_queue),
        "handoffs_created": len(ctx.handoffs),
    }

    # Reflection engine: review pending memory candidates
    memory_summary = {}
    if ctx.memory_store:
        # Auto-review all pending candidates
        audit_records = ctx.memory_store.review_pending(auto_store=True)
        memory_summary = {
            "candidates_reviewed": len(audit_records),
            "audit_records_created": len(audit_records),
        }

        # Persist to disk if venture root is available
        if ctx.tool_gateway and ctx.tool_gateway.venture_root:
            try:
                persist_result = ctx.memory_store.persist_to_disk(
                    ctx.tool_gateway.venture_root,
                    cycle_id=ctx.cycle_id,
                )
                memory_summary["persisted_to"] = persist_result
            except Exception as e:
                memory_summary["persist_error"] = str(e)

    return StepResult(
        step="log",
        status="success",
        output={
            "decision_log_entry": log_entry,
            "memory_summary": memory_summary,
        },
    )


# ---------------------------------------------------------------------------
# Cycle executor — runs all steps in order
# ---------------------------------------------------------------------------

CYCLE_STEPS = [
    ("review", step_review),
    ("prioritize", step_prioritize),
    ("delegate", step_delegate),
    ("run_specialists", step_run_specialists),
    ("summarize", step_summarize),
    ("approval_gates", step_approval_gates),
    ("execute", step_execute),
    ("log", step_log),
]


def run_cycle(
    registry: Registry,
    venture_artifacts: dict[str, Path] | None = None,
    llm: LLMClient | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> CycleContext:
    """Execute the full daily harness cycle."""
    if llm is None:
        llm = create_llm_client(dry_run=dry_run, verbose=verbose)

    # Get the executive harness bundle
    bundle = registry.harnesses.get("HAR-EXEC-001")
    if not bundle:
        raise ValueError("Executive harness (HAR-EXEC-001) not found in registry")

    venture_id = registry.venture.id if registry.venture else "UNKNOWN"
    from datetime import date
    cycle_id = f"{date.today().isoformat()}-executive"

    # Initialize tool gateway with venture root for artifact access
    venture_root = None
    if venture_artifacts:
        # Derive venture root from artifact paths
        for path in venture_artifacts.values():
            venture_root = path.parent
            break

    # Build memory store if memory.yml manifest exists
    memory_store = None
    if bundle.memory:
        # bundle.memory is already a Memory Pydantic model
        # Convert it to dict for build_memory_from_manifest
        memory_data = bundle.memory.model_dump()
        memory_store = build_memory_from_manifest(memory_data, venture_root=venture_root)

    gateway = ToolGateway(venture_root=venture_root, memory_store=memory_store)
    # Register tools from harness tools.yml if available
    if bundle.tools:
        gateway.register_tools_from_dict(
            [t.model_dump() if hasattr(t, 'model_dump') else t
             for t in (bundle.tools.tools if hasattr(bundle.tools, 'tools') else [])]
        )

    usage_tracker = UsageTracker()

    ctx = CycleContext(
        venture_id=venture_id,
        harness_id="HAR-EXEC-001",
        cycle_id=cycle_id,
        venture_artifacts=venture_artifacts or {},
        tool_gateway=gateway,
        memory_store=memory_store,
        usage_tracker=usage_tracker,
    )

    # Run each step
    for step_name, step_fn in CYCLE_STEPS:
        result = step_fn(ctx, bundle, llm)
        ctx.add_result(result)
        if result.status == "error":
            ctx.errors.append(f"{step_name}: {result.error}")

    return ctx


# ---------------------------------------------------------------------------
# Convenience: run with just a harness dir path
# ---------------------------------------------------------------------------

def run_from_path(
    harness_dir: Path,
    venture_path: Path | None = None,
    venture_artifacts: dict[str, Path] | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> CycleContext:
    """Load registry from disk and run one cycle."""
    registry = load_registry(harness_dir, venture_path)

    if venture_artifacts is None:
        venture_artifacts = {}
        if registry.venture:
            venture_root = venture_path.parent.parent if venture_path else None
            if venture_root:
                for key, art in registry.venture.artifacts.items():
                    art_path = venture_root / art.path
                    if art_path.exists():
                        venture_artifacts[key] = art_path

    return run_cycle(registry, venture_artifacts, llm=None, dry_run=dry_run, verbose=verbose)
