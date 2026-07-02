"""LangGraph-based event-driven orchestrator for TAZ OS.

Migrates the linear 8-phase cycle (runtime.py) to a StateGraph with:
  - Typed state shared between nodes
  - Conditional edge for approval/execution gating
  - Parallel specialist fan-out
  - Pure open-source LangGraph (no LangSmith / Cloud dependencies)

Graph topology:
    review → prioritize → delegate → specialists → summarize → approval_gates
                                                              ├─(handoffs)─→ execute → log → END
                                                              └─(empty)────→ log → END

Usage:
    from tazos.graph import build_graph, run_cycle_graph, format_state_summary
    compiled = build_graph(bundle, llm, tool_gateway=gw)
    state = compiled.invoke(initial_state, config=config)
"""

from __future__ import annotations

import concurrent.futures
import json
import operator
import re
import time
import warnings
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Any, TypedDict

from langgraph.config import RunnableConfig
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables import RunnableConfig

from tazos.constants import NETSO_FINANCIAL
from tazos.context import build_prompt
from tazos.evaluator import validate_output
from tazos.llm import LLMClient, create_llm_client, resolve_model
from tazos.memory import MemoryStore, build_memory_from_manifest
from tazos.registry import HarnessBundle
from tazos.schemas.agent import Agent
from tazos.schemas.harness import AgentTeam, TeamMember
from tazos.tools import ToolGateway
from tazos.usage import UsageTracker


# ---------------------------------------------------------------------------
# Graph state — TypedDict with reducers for accumulating fields
# ---------------------------------------------------------------------------

class CycleState(TypedDict, total=False):
    """LangGraph state for one execution cycle.

    Fields with ``Annotated[..., operator.add]`` use list concatenation as
    their reducer — each node returns a single-element list that gets
    appended to the accumulated list.  Scalar / dict fields are overwritten
    by each node's partial return.
    """

    # --- Identity (set once at init) ---
    venture_id: str
    harness_id: str
    cycle_id: str

    # --- Input data ---
    venture_artifacts: dict[str, Any]   # key → str(Path)
    inputs: dict[str, Any]

    # --- Accumulated results (reducer: list concat) ---
    step_results: Annotated[list[dict[str, Any]], operator.add]
    approval_queue: Annotated[list[dict[str, Any]], operator.add]
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


# ---------------------------------------------------------------------------
# Infrastructure config — passed via RunnableConfig.configurable
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GraphConfig:
    """Infrastructure objects that nodes need but don't belong in state."""

    bundle: HarnessBundle
    llm: LLMClient
    tool_gateway: ToolGateway | None = None
    memory_store: MemoryStore | None = None
    usage_tracker: UsageTracker | None = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from text that may contain markdown."""
    # Raw parse
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Extract from ```json ... ``` blocks
    code_blocks = re.findall(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    for block in code_blocks:
        try:
            result = json.loads(block.strip())
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            continue

    # Find first complete { ... }
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


def _build_task_prompt(
    step_name: str,
    agent: Agent,
    cycle_id: str,
    venture_id: str,
    inputs: dict[str, Any],
    approval_count: int = 0,
) -> str:
    """Build the user-facing task prompt for one execution step."""
    parts = [
        f"[Step: {step_name}]",
        f"Cycle: {cycle_id}",
        f"Venture: {venture_id}",
        "",
        "Inputs:",
    ]
    for key, value in inputs.items():
        if isinstance(value, str) and len(value) > 500:
            parts.append(f"  {key}: {value[:500]}...")
        else:
            parts.append(f"  {key}: {value}")
    if approval_count:
        parts.append(f"\nPending approvals: {approval_count} items")
    parts.append("\nExecute your role for this step. Output structured results.")
    return "\n".join(parts)


def _run_agent_node(
    agent: Agent,
    bundle: HarnessBundle,
    step_name: str,
    cycle_id: str,
    venture_id: str,
    inputs: dict[str, Any],
    llm: LLMClient,
    memory_store: MemoryStore | None = None,
    usage_tracker: UsageTracker | None = None,
    approval_count: int = 0,
) -> dict[str, Any]:
    """Run a single agent and return a step result dict."""
    start = time.monotonic()

    # Memory context
    memory_context = None
    if memory_store:
        try:
            memory_context = memory_store.retrieve_for_agent(agent.id, step_name)
        except AttributeError:
            pass

    # Build prompts via context builder (full contract serialization)
    netso_financial = NETSO_FINANCIAL if agent.financial_rules else None
    system_prompt = build_prompt(
        agent, netso_financial=netso_financial, memory_context=memory_context,
    )
    task_prompt = _build_task_prompt(
        step_name, agent, cycle_id, venture_id, inputs, approval_count,
    )

    # Model resolution
    agent_model = None
    if agent.models and agent.models.preferred:
        agent_model = agent.models.preferred
    model = resolve_model(agent.criticality.value, override=agent_model)
    temperature = 0.1 if agent.id == "AGT-EXEC-DISPATCH" else 0.3

    try:
        response = llm.complete(
            model=model,
            system=system_prompt,
            messages=[{"role": "user", "content": task_prompt}],
            temperature=temperature,
        )

        extracted = _extract_json(response.content)
        output: dict[str, Any] = extracted if extracted else {"raw_response": response.content}

        # Track usage
        if usage_tracker:
            usage_tracker.record(agent.id, model, response.usage)

        # Validate against ground truth
        validation = validate_output(output, agent.id, NETSO_FINANCIAL)
        output["_validation"] = {
            "passed": validation.passed,
            "violations": validation.violations,
            "warnings": validation.warnings,
        }

        elapsed = int((time.monotonic() - start) * 1000)
        result: dict[str, Any] = {
            "step": step_name,
            "agent_id": agent.id,
            "status": "success",
            "output": output,
            "duration_ms": elapsed,
        }
        if validation.violations:
            result["_errors"] = [f"{agent.id}: {v}" for v in validation.violations]
        return result

    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        return {
            "step": step_name,
            "agent_id": agent.id,
            "status": "error",
            "error": str(e),
            "output": {},
            "duration_ms": elapsed,
            "_errors": [f"{agent.id}: {e}"],
        }


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


def _expand_team_assignments(
    assignments: list[dict[str, Any]],
    bundle: HarnessBundle,
) -> list[dict[str, Any]]:
    """Expand team routes into individual member assignments.

    When dispatcher routes to TEAM-XXX, expand to all team members so
    specialists_node can detect 2+ members and trigger team coordination.
    """
    expanded: list[dict[str, Any]] = []

    for assignment in assignments:
        route_to = assignment.get("agent_id") or assignment.get("route_to")

        if route_to and route_to.startswith("TEAM-") and bundle.teams:
            team = bundle.teams.get(route_to)
            if team:
                for member in team.members:
                    member_assignment = assignment.copy()
                    member_assignment["agent_id"] = member.agent_id
                    member_assignment["team_id"] = team.id
                    member_assignment["team_role"] = member.role
                    member_assignment["team_weight"] = member.weight
                    expanded.append(member_assignment)
            else:
                expanded.append(assignment)
        else:
            expanded.append(assignment)

    return expanded


def _run_team(
    team: AgentTeam,
    assignments: list[dict[str, Any]],
    bundle: HarnessBundle,
    step_name: str,
    cycle_id: str,
    venture_id: str,
    llm: LLMClient,
    memory_store: MemoryStore | None = None,
    usage_tracker: UsageTracker | None = None,
) -> dict[str, Any]:
    """Execute a team of specialists with shared context.

    Coordination strategies:
      - sequential: lead runs first, reviewer gets lead's output as input
      - parallel: all members run simultaneously, results merged
      - voting: all run, consensus required (2/3 weight agreement)
    """
    strategy = team.coordination_strategy
    lead_agent = bundle.specialists.get(team.lead)
    if not lead_agent:
        return {
            "team_id": team.id,
            "status": "error",
            "error": f"Team lead {team.lead} not found",
            "results": [],
        }

    task_context = "\n".join(
        f"- {a.get('agent_id', '?')}: {a.get('task', '')[:200]}"
        for a in assignments
    )
    shared_context = f"Team: {team.name}\nTask: {task_context}"

    team_results: list[dict[str, Any]] = []
    team_errors: list[str] = []

    if strategy == "sequential":
        lead_inputs = {
            "task": shared_context,
            "role": "lead",
            "team_members": [m.agent_id for m in team.members],
        }
        lead_result = _run_agent_node(
            lead_agent, bundle, f"{step_name}:team:{team.id}:lead",
            cycle_id, venture_id, lead_inputs, llm,
            memory_store=memory_store, usage_tracker=usage_tracker,
        )
        team_results.append({
            "agent_id": team.lead,
            "role": "lead",
            "status": lead_result.get("status", "error"),
            "output": lead_result.get("output", {}),
        })
        team_errors.extend(_get_errors(lead_result))

        lead_output = lead_result.get("output", {})
        for member in team.members:
            if member.agent_id == team.lead:
                continue
            member_agent = bundle.specialists.get(member.agent_id)
            if not member_agent:
                continue
            member_inputs = {
                "task": shared_context,
                "role": member.role,
                "lead_output": lead_output,
                "weight": member.weight,
            }
            member_result = _run_agent_node(
                member_agent, bundle, f"{step_name}:team:{team.id}:{member.agent_id}",
                cycle_id, venture_id, member_inputs, llm,
                memory_store=memory_store, usage_tracker=usage_tracker,
            )
            team_results.append({
                "agent_id": member.agent_id,
                "role": member.role,
                "status": member_result.get("status", "error"),
                "output": member_result.get("output", {}),
            })
            team_errors.extend(_get_errors(member_result))

    elif strategy == "parallel":
        def _run_member(member: TeamMember) -> tuple[str, dict[str, Any]]:
            member_agent = bundle.specialists.get(member.agent_id)
            if not member_agent:
                return member.agent_id, {
                    "status": "error",
                    "error": f"Agent {member.agent_id} not found",
                }
            member_inputs = {
                "task": shared_context,
                "role": member.role,
                "weight": member.weight,
            }
            result = _run_agent_node(
                member_agent, bundle, f"{step_name}:team:{team.id}:{member.agent_id}",
                cycle_id, venture_id, member_inputs, llm,
                memory_store=memory_store, usage_tracker=usage_tracker,
            )
            return member.agent_id, {
                "status": result.get("status", "error"),
                "output": result.get("output", {}),
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(team.members)) as pool:
            futures = {pool.submit(_run_member, m): m for m in team.members}
            for future in concurrent.futures.as_completed(futures):
                try:
                    agent_id, result = future.result()
                    team_results.append({"agent_id": agent_id, **result})
                except Exception as exc:
                    team_errors.append(f"team:{team.id}:{exc}")

    elif strategy == "voting":
        def _run_voter(member: TeamMember) -> tuple[str, dict[str, Any], float]:
            member_agent = bundle.specialists.get(member.agent_id)
            if not member_agent:
                return member.agent_id, {"status": "error"}, 0.0
            member_inputs = {
                "task": shared_context,
                "role": member.role,
                "voting": True,
                "weight": member.weight,
            }
            result = _run_agent_node(
                member_agent, bundle, f"{step_name}:team:{team.id}:{member.agent_id}",
                cycle_id, venture_id, member_inputs, llm,
                memory_store=memory_store, usage_tracker=usage_tracker,
            )
            return member.agent_id, {
                "status": result.get("status", "error"),
                "output": result.get("output", {}),
            }, member.weight

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(team.members)) as pool:
            futures = {pool.submit(_run_voter, m): m for m in team.members}
            total_weight = 0.0
            agree_weight = 0.0
            for future in concurrent.futures.as_completed(futures):
                try:
                    agent_id, result, weight = future.result()
                    team_results.append({"agent_id": agent_id, **result})
                    total_weight += weight
                    if result.get("status") == "success":
                        agree_weight += weight
                except Exception as exc:
                    team_errors.append(f"team:{team.id}:{exc}")

            consensus = agree_weight / total_weight >= 0.67 if total_weight > 0 else False
            team_results.append({
                "agent_id": "TEAM-CONSENSUS",
                "status": "success" if consensus else "failed",
                "output": {"consensus": consensus, "agree_weight": agree_weight, "total_weight": total_weight},
            })

    return {
        "team_id": team.id,
        "status": "success" if not team_errors else "partial",
        "results": team_results,
        "errors": team_errors,
    }


# ---------------------------------------------------------------------------
# Graph nodes — one function per cycle step
# ---------------------------------------------------------------------------

def review_node(state: CycleState, config: RunnableConfig | None = None) -> dict:
    """Step 1: Review all inputs — dashboard, blockers, calendar, email.

    Reads venture artifacts via tool gateway (or direct file read as
    fallback) and delegates the initial scan to the COO specialist.
    """
    cfg = config.get("configurable", {}) if isinstance(config, dict) else getattr(config, "configurable", {}) if config else {}
    bundle: HarnessBundle = cfg.get("bundle") # type: ignore
    llm: LLMClient = cfg.get("llm") # type: ignore
    tool_gateway: ToolGateway | None = cfg.get("tool_gateway")
    memory_store: MemoryStore | None = cfg.get("memory_store")
    usage_tracker: UsageTracker | None = cfg.get("usage_tracker")

    # Read venture artifacts
    inputs: dict[str, Any] = {}
    artifacts = state.get("venture_artifacts", {})
    if tool_gateway:
        for key, path_str in artifacts.items():
            result = tool_gateway.call(
                "read_dashboard",
                {"path": path_str},
                agent_id="AGT-EXEC-COO",
            )
            if result.ok:
                content = result.output.get("content", "")
                inputs[key] = content[:2000] if content else f"(empty: {path_str})"
            else:
                inputs[key] = f"(could not read {path_str}: {result.error})"
    else:
        for key, path_str in artifacts.items():
            try:
                p = Path(path_str)
                if p.exists():
                    inputs[key] = p.read_text()[:2000]
                else:
                    inputs[key] = f"(could not read {path_str})"
            except Exception:
                inputs[key] = f"(could not read {path_str})"

    coo = bundle.specialists.get("AGT-EXEC-COO") if bundle and bundle.specialists else None
    if not coo:
        err = "review: COO specialist not found"
        return {
            "step_results": _step_result_to_list({
                "step": "review", "agent_id": None,
                "status": "error", "error": err,
                "output": {}, "duration_ms": 0,
            }),
            "errors": [err],
        }

    result = _run_agent_node(
        coo, bundle, "review",
        state["cycle_id"], state["venture_id"],
        inputs, llm,
        memory_store=memory_store, usage_tracker=usage_tracker,
    )

    update: dict[str, Any] = {
        "step_results": _step_result_to_list(result),
        "review_output": result.get("output", {}),
    }
    if _get_errors(result):
        update["errors"] = _get_errors(result)
    return update


def prioritize_node(state: CycleState, config: RunnableConfig | None = None) -> dict:
    """Step 2: Planner generates priority list from review."""
    cfg = config.get("configurable", {}) if isinstance(config, dict) else getattr(config, "configurable", {}) if config else {}
    bundle: HarnessBundle = cfg.get("bundle") # type: ignore
    llm: LLMClient = cfg.get("llm") # type: ignore
    memory_store: MemoryStore | None = cfg.get("memory_store")
    usage_tracker: UsageTracker | None = cfg.get("usage_tracker")

    if not bundle or not bundle.planner:
        err = "prioritize: Planner not loaded"
        return {
            "step_results": _step_result_to_list({
                "step": "prioritize", "agent_id": None,
                "status": "error", "error": err,
                "output": {}, "duration_ms": 0,
            }),
            "errors": [err],
        }

    review_output = _get_step_output(state, "review")
    inputs = {
        "review_summary": review_output,
        "backlog": state.get("inputs", {}).get("backlog", ""),
        "weekly_plan": state.get("inputs", {}).get("weekly_plan", ""),
    }

    result = _run_agent_node(
        bundle.planner, bundle, "prioritize",
        state["cycle_id"], state["venture_id"],
        inputs, llm,
        memory_store=memory_store, usage_tracker=usage_tracker,
    )

    update: dict[str, Any] = {
        "step_results": _step_result_to_list(result),
        "prioritize_output": result.get("output", {}),
    }
    if _get_errors(result):
        update["errors"] = _get_errors(result)
    return update


def delegate_node(state: CycleState, config: RunnableConfig | None = None) -> dict:
    """Step 3: Dispatcher routes priorities to specialist agents."""
    cfg = config.get("configurable", {}) if isinstance(config, dict) else getattr(config, "configurable", {}) if config else {}
    bundle: HarnessBundle = cfg.get("bundle") # type: ignore
    llm: LLMClient = cfg.get("llm") # type: ignore
    memory_store: MemoryStore | None = cfg.get("memory_store")
    usage_tracker: UsageTracker | None = cfg.get("usage_tracker")

    if not bundle or not bundle.dispatcher:
        err = "delegate: Dispatcher not loaded"
        return {
            "step_results": _step_result_to_list({
                "step": "delegate", "agent_id": None,
                "status": "error", "error": err,
                "output": {}, "duration_ms": 0,
            }),
            "errors": [err],
        }

    prioritize_output = _get_step_output(state, "prioritize")
    inputs = {
        "priority_list": prioritize_output,
        "routing_table": (
            bundle.dispatcher.routing_table.model_dump()
            if bundle.dispatcher.routing_table else {}
        ),
        "available_agents": [a.id for a in bundle.specialists.values()],
        "available_teams": list(bundle.teams.keys()) if bundle.teams else [],
    }

    result = _run_agent_node(
        bundle.dispatcher, bundle, "delegate",
        state["cycle_id"], state["venture_id"],
        inputs, llm,
        memory_store=memory_store, usage_tracker=usage_tracker,
    )

    output = result.get("output", {})

    # Expand team routes to individual member assignments
    if output.get("assignments") and bundle:
        output["assignments"] = _expand_team_assignments(
            output["assignments"], bundle
        )

    update: dict[str, Any] = {
        "step_results": _step_result_to_list(result),
        "delegate_output": output,
    }
    if _get_errors(result):
        update["errors"] = _get_errors(result)
    return update


def specialists_node(state: CycleState, config: RunnableConfig | None = None) -> dict:
    """Step 4: Fan-out — run assigned specialist agents concurrently.

    Reads dispatcher output for structured assignments.  Falls back to
    regex extraction of ``AGT-EXEC-XXX`` mentions from raw text.
    Specialists run in a thread pool (max 6 workers).
    """
    cfg = config.get("configurable", {}) if isinstance(config, dict) else getattr(config, "configurable", {}) if config else {}
    bundle: HarnessBundle = cfg.get("bundle") # type: ignore
    llm: LLMClient = cfg.get("llm") # type: ignore
    memory_store: MemoryStore | None = cfg.get("memory_store")
    usage_tracker: UsageTracker | None = cfg.get("usage_tracker")

    delegate_output = _get_step_output(state, "delegate")
    assignments = delegate_output.get("assignments", [])

    # Fallback: extract agent mentions from raw response
    if not assignments and "raw_response" in delegate_output:
        raw = delegate_output["raw_response"]
        agent_mentions = re.findall(r"AGT-EXEC-[A-Z]+", raw)
        seen: set[str] = set()
        for agent_id in agent_mentions:
            if bundle and bundle.specialists and agent_id not in seen and agent_id in bundle.specialists:
                seen.add(agent_id)
                assignments.append({
                    "agent_id": agent_id,
                    "task": raw[:500],
                    "input": "",
                })

    if not assignments:
        return {
            "step_results": _step_result_to_list({
                "step": "run_specialists", "agent_id": None,
                "status": "skipped",
                "output": {"reason": "No structured assignments from dispatcher"},
                "duration_ms": 0,
            }),
            "specialists_output": {"specialist_results": [], "approval_count": 0},
        }

    # Group assignments by team membership
    assigned_agent_ids: set[str] = set()
    for a in assignments:
        aid = a.get("agent_id") or a.get("route_to")
        if aid:
            assigned_agent_ids.add(aid)

    teams_to_run: list[tuple[AgentTeam, list[dict[str, Any]]]] = []
    team_member_ids: set[str] = set()

    if bundle and bundle.teams:
        for team in bundle.teams.values():
            team_members_in_assignments = [
                m for m in team.members if m.agent_id in assigned_agent_ids
            ]
            if len(team_members_in_assignments) >= 2:
                team_assignments = [
                    a for a in assignments
                    if (a.get("agent_id") or a.get("route_to")) in {m.agent_id for m in team_members_in_assignments}
                ]
                teams_to_run.append((team, team_assignments))
                for m in team_members_in_assignments:
                    team_member_ids.add(m.agent_id)

    solo_assignments = [
        a for a in assignments
        if (a.get("agent_id") or a.get("route_to")) not in team_member_ids
    ]

    # Execute teams
    specialist_results: list[dict[str, Any]] = []
    new_errors: list[str] = []
    new_approvals: list[dict[str, Any]] = []
    new_handoffs: list[dict[str, Any]] = []

    for team, team_assignments in teams_to_run:
        team_result = _run_team(
            team, team_assignments, bundle,
            "specialists",
            state["cycle_id"], state["venture_id"],
            llm,
            memory_store=memory_store, usage_tracker=usage_tracker,
        )
        specialist_results.append({
            "agent_id": f"TEAM:{team.id}",
            "status": team_result.get("status", "error"),
            "output": team_result,
        })
        new_errors.extend(team_result.get("errors", []))

        for tr in team_result.get("results", []):
            output = tr.get("output", {})
            if "approval_required" in output:
                new_approvals.append(output["approval_required"])
            if "handoff" in output:
                new_handoffs.append(output["handoff"])
            if "handoffs" in output:
                new_handoffs.extend(output["handoffs"])

    # Prepare solo specialist assignments
    def _prepare(a: dict[str, Any]) -> tuple[str, Agent, dict[str, Any]] | None:
        agent_id = a.get("agent_id") or a.get("route_to")
        if not bundle or not bundle.specialists or not agent_id or agent_id not in bundle.specialists:
            return None
        agent = bundle.specialists[agent_id]
        inputs = {
            "task": a.get("task", ""),
            "context": a.get("input", "") or delegate_output,
            "priority": a.get("priority", ""),
            "sla": a.get("sla", ""),
        }
        return agent_id, agent, inputs

    prepared = [p for p in (_prepare(a) for a in assignments) if p]

    def _run_one(item: tuple[str, Agent, dict[str, Any]]) -> tuple[str, dict[str, Any]]:
        agent_id, agent, inputs = item
        return agent_id, _run_agent_node(
            agent, bundle, f"specialist:{agent_id}",
            state["cycle_id"], state["venture_id"],
            inputs, llm,
            memory_store=memory_store, usage_tracker=usage_tracker,
        )

    # Fan-out via thread pool
    specialist_results: list[dict[str, Any]] = []
    new_errors: list[str] = []
    new_approvals: list[dict[str, Any]] = []
    new_handoffs: list[dict[str, Any]] = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_run_one, item) for item in prepared]
        for future in concurrent.futures.as_completed(futures):
            try:
                agent_id, agent_result = future.result()
            except Exception as exc:
                agent_id = "unknown"
                agent_result = {
                    "step": "run_specialists", "status": "error",
                    "error": str(exc), "output": {}, "duration_ms": 0,
                    "_errors": [f"specialist: {exc}"],
                }

            specialist_results.append({
                "agent_id": agent_id,
                "status": agent_result.get("status", "error"),
                "output": agent_result.get("output", {}),
            })

            new_errors.extend(_get_errors(agent_result))

            output = agent_result.get("output", {})
            # Collect approval requests
            if "approval_required" in output:
                new_approvals.append(output["approval_required"])
            # Collect handoff directives
            if "handoff" in output:
                new_handoffs.append(output["handoff"])
            if "handoffs" in output:
                new_handoffs.extend(output["handoffs"])

    update: dict[str, Any] = {
        "step_results": _step_result_to_list({
            "step": "run_specialists", "agent_id": None,
            "status": "success" if specialist_results else "skipped",
            "output": {
                "specialist_results": specialist_results,
                "teams_run": len(teams_to_run),
                "solo_run": len(prepared),
                "approval_count": len(new_approvals),
            },
            "duration_ms": 0,
        }),
        "specialists_output": {
            "specialist_results": specialist_results,
            "teams_run": len(teams_to_run),
            "solo_run": len(prepared),
            "approval_count": len(new_approvals),
        },
    }
    if new_approvals:
        update["approval_queue"] = new_approvals
    if new_handoffs:
        update["handoffs"] = new_handoffs
    if new_errors:
        update["errors"] = new_errors
    return update


def summarize_node(state: CycleState, config: RunnableConfig | None = None) -> dict:
    """Step 5: Chief of Staff composes the daily brief."""
    cfg = config.get("configurable", {}) if isinstance(config, dict) else getattr(config, "configurable", {}) if config else {}
    bundle: HarnessBundle = cfg.get("bundle") # type: ignore
    llm: LLMClient = cfg.get("llm") # type: ignore
    memory_store: MemoryStore | None = cfg.get("memory_store")
    usage_tracker: UsageTracker | None = cfg.get("usage_tracker")

    chief = bundle.specialists.get("AGT-EXEC-CHIEFOFSTAFF") if bundle and bundle.specialists else None
    if not chief:
        err = "summarize: Chief of Staff not found"
        return {
            "step_results": _step_result_to_list({
                "step": "summarize", "agent_id": None,
                "status": "error", "error": err,
                "output": {}, "duration_ms": 0,
            }),
            "errors": [err],
        }

    inputs = {
        "priority_list": _get_step_output(state, "prioritize"),
        "dispatch_summary": _get_step_output(state, "delegate"),
        "specialist_results": _get_step_output(state, "run_specialists"),
        "approval_queue": state.get("approval_queue", []),
        "dashboard": state.get("inputs", {}).get("dashboard", ""),
        "blockers": state.get("inputs", {}).get("blockers", ""),
    }

    result = _run_agent_node(
        chief, bundle, "summarize",
        state["cycle_id"], state["venture_id"],
        inputs, llm,
        memory_store=memory_store, usage_tracker=usage_tracker,
    )

    update: dict[str, Any] = {
        "step_results": _step_result_to_list(result),
        "summarize_output": result.get("output", {}),
    }
    if _get_errors(result):
        update["errors"] = _get_errors(result)
    return update


def approval_gates_node(state: CycleState, config: RunnableConfig | None = None) -> dict:
    """Step 6: Validate and bundle approval gates for the founder.

    Pure logic — no LLM call.  Bundles pending approvals into a
    structured format for console delivery.
    """
    cfg = config.get("configurable", {}) if isinstance(config, dict) else getattr(config, "configurable", {}) if config else {}
    bundle: HarnessBundle = cfg.get("bundle") # type: ignore
    chief = bundle.specialists.get("AGT-EXEC-CHIEFOFSTAFF") if bundle and bundle.specialists else None

    approval_items = state.get("approval_queue", [])
    bundled = {
        "total_pending": len(approval_items),
        "items": approval_items,
        "format": "approve_all | review_individually | reject",
        "delivery": "console_queue",
    }

    return {
        "step_results": _step_result_to_list({
            "step": "approval_gates",
            "agent_id": chief.id if chief else None,
            "status": "success",
            "output": bundled,
            "duration_ms": 0,
        }),
        "approval_gates_output": bundled,
    }


# ---------------------------------------------------------------------------
# Conditional edge — routes after approval_gates
# ---------------------------------------------------------------------------

def should_execute(state: CycleState) -> str:
    """Conditional edge: route to execute if handoffs exist, else skip to log.

    In the default flow, handoffs are populated by specialist outputs.
    When no handoffs are queued, the execute step is skipped entirely —
    this is the key improvement over the linear runtime which always
    ran every step.
    """
    handoffs = state.get("handoffs", [])
    if handoffs:
        return "execute"
    return "log"


# ---------------------------------------------------------------------------
# Remaining nodes
# ---------------------------------------------------------------------------

def execute_node(state: CycleState, config: RunnableConfig | None = None) -> dict:
    """Step 7: Execute approved actions via tool gateway.

    Dispatches each handoff through ``ToolGateway.execute()`` and records
    real results.  Without a gateway, handoffs stay in *queued* state.
    """
    cfg = config.get("configurable", {}) if isinstance(config, dict) else getattr(config, "configurable", {}) if config else {}
    tool_gateway: ToolGateway | None = cfg.get("tool_gateway")

    executed: list[dict[str, Any]] = []
    new_errors: list[str] = []

    for handoff in state.get("handoffs", []):
        if tool_gateway is not None:
            result = tool_gateway.execute(handoff)
            executed.append({
                "type": "handoff",
                "status": "success" if result.get("ok") else "error",
                "result": result,
                **handoff,
            })
            if not result.get("ok"):
                new_errors.append(f"execute: {result.get('error', 'unknown error')}")
        else:
            executed.append({"type": "handoff", "status": "queued", **handoff})

    output = {"executed": executed, "handoff_count": len(state.get("handoffs", []))}
    update: dict[str, Any] = {
        "step_results": _step_result_to_list({
            "step": "execute", "agent_id": None,
            "status": "success", "output": output, "duration_ms": 0,
        }),
        "execute_output": output,
    }
    if new_errors:
        update["errors"] = new_errors
    return update


def log_node(state: CycleState, config: RunnableConfig | None = None) -> dict:
    """Step 8: Log decisions, review memory candidates, persist to disk.

    Builds the decision log entry, runs the memory reflection engine,
    and persists memory to disk if a venture root is available.
    """
    cfg = config.get("configurable", {}) if isinstance(config, dict) else getattr(config, "configurable", {}) if config else {}
    memory_store: MemoryStore | None = cfg.get("memory_store")
    tool_gateway: ToolGateway | None = cfg.get("tool_gateway")

    results = state.get("step_results", [])
    log_entry = {
        "cycle_id": state.get("cycle_id", ""),
        "timestamp": datetime.now().isoformat(),
        "harness_id": state.get("harness_id", ""),
        "steps_completed": [r["step"] for r in results if r.get("status") == "success"],
        "steps_failed": [r["step"] for r in results if r.get("status") == "error"],
        "approval_queue_size": len(state.get("approval_queue", [])),
        "handoffs_created": len(state.get("handoffs", [])),
    }

    memory_summary: dict[str, Any] = {}
    if memory_store:
        audit_records = memory_store.review_pending(auto_store=True)
        memory_summary = {
            "candidates_reviewed": len(audit_records),
            "audit_records_created": len(audit_records),
        }
        if tool_gateway and tool_gateway.venture_root:
            try:
                persist_result = memory_store.persist_to_disk(
                    tool_gateway.venture_root,
                    cycle_id=state.get("cycle_id", ""),
                )
                memory_summary["persisted_to"] = persist_result
            except Exception as exc:
                memory_summary["persist_error"] = str(exc)

    output = {"decision_log_entry": log_entry, "memory_summary": memory_summary}
    return {
        "step_results": _step_result_to_list({
            "step": "log", "agent_id": None,
            "status": "success", "output": output, "duration_ms": 0,
        }),
        "log_output": output,
    }


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph(
    bundle: HarnessBundle,
    llm: LLMClient,
    tool_gateway: ToolGateway | None = None,
    memory_store: MemoryStore | None = None,
    usage_tracker: UsageTracker | None = None,
) -> CompiledStateGraph:
    """Build and compile the TAZ OS LangGraph StateGraph.

    Returns a compiled graph ready for ``.invoke()`` or ``.stream()``.

    Graph topology::

        review ─→ prioritize ─→ delegate ─→ specialists ─→ summarize ─→ approval_gates
                                                                          ├─(handoffs)─→ execute ─→ log ─→ END
                                                                          └─(empty)────→ log ─→ END

    Pure open-source LangGraph — no LangSmith or LangGraph Cloud
    dependencies.  No checkpointer (in-memory state only).
    """
    graph = StateGraph(CycleState)

    # --- Nodes ---
    graph.add_node("review", review_node)
    graph.add_node("prioritize", prioritize_node)
    graph.add_node("delegate", delegate_node)
    graph.add_node("specialists", specialists_node)
    graph.add_node("summarize", summarize_node)
    graph.add_node("approval_gates", approval_gates_node)
    graph.add_node("execute", execute_node)
    graph.add_node("log", log_node)

    # --- Entry ---
    graph.set_entry_point("review")

    # --- Linear edges (phase 1-5) ---
    graph.add_edge("review", "prioritize")
    graph.add_edge("prioritize", "delegate")
    graph.add_edge("delegate", "specialists")
    graph.add_edge("specialists", "summarize")
    graph.add_edge("summarize", "approval_gates")

    # --- Conditional edge: approval_gates → execute OR log ---
    graph.add_conditional_edges(
        "approval_gates",
        should_execute,
        {
            "execute": "execute",
            "log": "log",
        },
    )

    # --- execute → log ---
    graph.add_edge("execute", "log")

    # --- Terminal ---
    graph.add_edge("log", END)

    # Compile (no checkpointer — pure local state)
    return graph.compile()


# ---------------------------------------------------------------------------
# Convenience: run cycle via graph (drop-in for runtime.run_cycle)
# ---------------------------------------------------------------------------

def run_cycle_graph(
    bundle: HarnessBundle,
    venture_id: str = "UNKNOWN",
    harness_id: str = "HAR-EXEC-001",
    venture_artifacts: dict[str, Path] | None = None,
    llm: LLMClient | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> CycleState:
    """Execute the full daily harness cycle via LangGraph.

    Drop-in replacement for ``runtime.run_cycle`` — same inputs, same
    logical flow, but executed as a compiled StateGraph with conditional
    routing.
    """
    if llm is None:
        llm = create_llm_client(dry_run=dry_run, verbose=verbose)

    # Derive venture root from artifact paths
    venture_root = None
    if venture_artifacts:
        for path in venture_artifacts.values():
            venture_root = path.parent
            break

    # Build memory store if manifest exists
    memory_store = None
    if bundle.memory:
        memory_data = bundle.memory.model_dump()
        memory_store = build_memory_from_manifest(memory_data, venture_root=venture_root)

    # Build tool gateway
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

    # Build and compile the graph
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
        }
    }

    result_state = compiled.invoke(initial_state, config=config)
    return result_state


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_state_summary(state: CycleState) -> str:
    """Format a CycleState dict into a human-readable summary.

    Mirrors ``runtime.CycleContext.summary()`` for backward compatibility
    with CLI output.
    """
    results = state.get("step_results", [])
    errors = state.get("errors", [])
    approvals = state.get("approval_queue", [])

    lines = [
        f"Cycle: {state.get('cycle_id', '?')}",
        f"Harness: {state.get('harness_id', '?')}",
        f"Venture: {state.get('venture_id', '?')}",
        f"Steps completed: "
        f"{sum(1 for r in results if r.get('status') == 'success')}/{len(results)}",
        f"Errors: {len(errors)}",
        f"Approvals pending: {len(approvals)}",
    ]

    if errors:
        lines.append("\nErrors:")
        for e in errors:
            lines.append(f"  - {e}")

    lines.append("\nStep details:")
    icon_map = {"success": "✓", "error": "✗", "skipped": "○", "pending": "·"}
    for r in results:
        icon = icon_map.get(r.get("status", ""), "?")
        agent_str = f" ({r['agent_id']})" if r.get("agent_id") else ""
        step = r.get("step", "?")
        status = r.get("status", "?")
        ms = r.get("duration_ms", 0)
        lines.append(f"  [{icon}] {step}{agent_str}: {status} ({ms}ms)")
        if r.get("error"):
            lines.append(f"      Error: {r['error']}")

    return "\n".join(lines)
