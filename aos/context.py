"""Context builder — assembles full system prompt from agent manifest.

Replaces _build_agent_system_prompt which only read 7 fields.
This reads the ENTIRE agent contract: identity, mission, capabilities,
reasoning structure, self-check, constraints, memory permissions,
evaluation rules, financial rules (CFO), routing table (dispatcher),
task lifecycle, delegation heuristics, daily brief format, and KPIs.

Prompt is deterministic and version-controlled — no runtime improvisation.
"""

from __future__ import annotations

from typing import Any

from aos.schemas.agent import Agent


def build_prompt(
    agent: Agent,
    netso_financial: dict[str, Any] | None = None,
    memory_context: str | None = None,
) -> str:
    """Build the complete system prompt for an agent from its manifest.

    This is the SINGLE source of prompt construction. Every agent in
    AOS goes through this function. No agent builds its own prompt.
    """
    parts: list[str] = []

    # --- Identity ---
    parts.append(f"You are {agent.name} ({agent.id}).")
    parts.append("You operate within the AOS Executive Harness.")
    parts.append("")

    # --- Mission ---
    parts.append(f"MISSION: {agent.mission}")
    parts.append("")

    # --- Capabilities ---
    if agent.capabilities:
        parts.append("YOUR CAPABILITIES:")
        for cap in agent.capabilities:
            parts.append(f"  - {cap}")
        parts.append("")

    # --- Reasoning Structure ---
    if agent.reasoning_structure:
        parts.append("REASONING PROCESS (follow these steps in order):")
        for i, step in enumerate(agent.reasoning_structure, 1):
            parts.append(f"  {i}. {step}")
        parts.append("")

    # --- Self-Check ---
    if agent.self_check:
        parts.append("BEFORE OUTPUTTING YOUR RESULT, VERIFY:")
        for item in agent.self_check:
            parts.append(f"  - {item}")
        parts.append("")

    # --- Constraints ---
    if agent.constraints:
        parts.append("CONSTRAINTS (NON-NEGOTIABLE):")
        for c in agent.constraints:
            parts.append(f"  - {c}")
        parts.append("")

    # --- Memory Permissions ---
    if agent.allowed_memory:
        parts.append("MEMORY ACCESS:")
        parts.append(f"  Can read: {', '.join(agent.allowed_memory.read)}")
        parts.append(f"  Can write: {', '.join(agent.allowed_memory.write)}")
        parts.append(f"  Cannot read: {', '.join(agent.allowed_memory.cannot_read)}")
        parts.append("")

    # --- Financial Rules (CFO-specific) ---
    if agent.financial_rules and netso_financial:
        parts.append(_build_financial_block(netso_financial, agent.financial_rules))

    # --- Evaluation Rules ---
    if agent.evaluation:
        parts.append("EVALUATION RULES (you will be scored on these):")
        for metric in agent.evaluation:
            weight = getattr(metric, "weight", 0)
            name = getattr(metric, "metric", str(metric))
            hard_fail = getattr(metric, "hard_fail_if", None)
            line = f"  - {name} (weight: {weight})"
            if hard_fail:
                line += f" [HARD FAIL: {hard_fail}]"
            parts.append(line)
        parts.append("")

    # --- Routing Table (Dispatcher-specific) ---
    if agent.routing_table:
        parts.append(_build_routing_block(agent.routing_table))

    # --- Task Lifecycle (Dispatcher-specific) ---
    if agent.task_lifecycle:
        parts.append(_build_task_lifecycle_block(agent.task_lifecycle))

    # --- Delegation Heuristics (Planner-specific) ---
    if agent.delegation_heuristics:
        parts.append("DELEGATION HEURISTICS:")
        for h in agent.delegation_heuristics:
            conditions = " AND ".join(h.if_conditions)
            target = h.then.get("route_to") or h.then.get("harness") or str(h.then)
            parts.append(f"  IF {conditions} -> {target}")
        parts.append("")

    # --- Daily Brief Format (Chief of Staff) ---
    if agent.daily_brief_format:
        parts.append("DAILY BRIEF FORMAT:")
        parts.append(f"  {agent.daily_brief_format}")
        parts.append("")

    # --- KPIs (Performance Analyst) ---
    if agent.tracked_kpis:
        parts.append("TRACKED KPIs:")
        for category, metrics in agent.tracked_kpis.items():
            parts.append(f"  {category}: {', '.join(metrics)}")
        parts.append("")

    # --- Memory Context (runtime-injected) ---
    if memory_context:
        parts.append("RELEVANT MEMORY CONTEXT:")
        parts.append(memory_context)
        parts.append("")

    # --- Output Format ---
    parts.append(_get_output_format(agent.id))

    return "\n".join(parts)


def _build_financial_block(
    netso_financial: dict[str, Any],
    financial_rules: dict[str, Any],
) -> str:
    """Build the financial ground truth block for CFO agents."""
    lines: list[str] = [
        "=" * 60,
        "FINANCIAL GROUND TRUTH (from GROUND_TRUTH_CONSTANTS.md)",
        "=" * 60,
        "",
        "These are the ONLY acceptable values. NEVER deviate.",
        "",
    ]
    for key, value in netso_financial.items():
        lines.append(f"  {key}: {value}")
    lines.append("")

    # Hard-fail rules
    hard_fails = financial_rules.get("hard_fails", [])
    if hard_fails:
        lines.append("HARD FAIL RULES (violations are rejected):")
        for rule in hard_fails:
            desc = rule.get("description", "")
            correct = rule.get("correct_value", "")
            lines.append(f"  - FAIL if: {desc}")
            if correct:
                lines.append(f"    Correct: {correct}")
        lines.append("")

    # Scenario B activation
    scenario_b = financial_rules.get("scenario_b_activation")
    if scenario_b:
        lines.append(f"SCENARIO B ACTIVATION: {scenario_b}")
        lines.append("")

    return "\n".join(lines)


def _build_routing_block(routing_table: Any) -> str:
    """Build routing table instructions for the dispatcher."""
    lines: list[str] = ["ROUTING TABLE:"]
    if routing_table.executive_internal:
        lines.append("  Executive internal:")
        for entry in routing_table.executive_internal:
            lines.append(f"    {entry.task} -> {entry.route_to} (SLA: {entry.sla})")
    if routing_table.cross_harness:
        lines.append("  Cross-harness:")
        for entry in routing_table.cross_harness:
            harness = entry.harness or "unknown"
            lines.append(
                f"    {entry.task} -> {entry.route_to} [{harness}] (SLA: {entry.sla})"
            )
    lines.append("")
    return "\n".join(lines)


def _build_task_lifecycle_block(task_lifecycle: Any) -> str:
    """Build task lifecycle instructions."""
    lines: list[str] = ["TASK LIFECYCLE:"]
    if task_lifecycle.states:
        lines.append(f"  States: {' -> '.join(task_lifecycle.states)}")
    if task_lifecycle.rules:
        for rule in task_lifecycle.rules:
            lines.append(f"  Rule: {rule}")
    lines.append("")
    return "\n".join(lines)


def _get_output_format(agent_id: str) -> str:
    """Get step-specific JSON output instructions."""
    if agent_id == "AGT-EXEC-DISPATCH":
        return (
            "OUTPUT FORMAT: You MUST respond with ONLY a JSON object.\n"
            "{\n"
            '  "assignments": [\n'
            "    {\n"
            '      "agent_id": "AGT-EXEC-XXX",\n'
            '      "task": "description of what to do",\n'
            '      "input": "specific input for this agent",\n'
            '      "priority": "P0|P1|P2|P3",\n'
            '      "sla": "time limit"\n'
            "    }\n"
            "  ],\n"
            '  "unrouted": ["tasks with no routing match"],\n'
            '  "escalations": ["items needing immediate escalation"]\n'
            "}"
        )

    # Default: request structured JSON
    return (
        "OUTPUT FORMAT: Respond with a JSON object containing your analysis.\n"
        "{\n"
        '  "summary": "one-line summary",\n'
        '  "findings": ["key finding 1", "key finding 2"],\n'
        '  "actions": ["recommended action 1"],\n'
        '  "confidence": "high|medium|low",\n'
        '  "approval_required": null\n'
        "}"
    )
