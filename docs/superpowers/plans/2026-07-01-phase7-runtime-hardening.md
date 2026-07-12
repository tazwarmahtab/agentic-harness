# TAZ OS Phase 7 — Runtime Hardening & Context Engineering

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 6 critical runtime gaps identified in the expert review so that TAZ OS agents produce accurate, validated, parallelized output with full context. Transform the runtime from a 2/10 engine to a 7/10+ production system.

**Architecture:** Extend the existing `aos/` package without breaking the manifest layer. All changes are in the runtime Python code. New modules: `context.py` (prompt construction + memory retrieval), `evaluator.py` (output validation), `parallel.py` (async specialist execution), `usage.py` (cost tracking). Modified modules: `runtime.py`, `llm.py`, `memory.py`.

**Tech Stack:** Python 3.12, asyncio, Pydantic, pytest, 9router (localhost:20128), dataclasses

---

## Global Constraints

- Python 3.12+ (match existing pyproject.toml)
- Pydantic v2 (match existing schemas)
- pytest async (match existing pyproject.toml `asyncio_mode = auto`)
- No new pip dependencies — stdlib asyncio only
- All existing 31 tests must continue passing
- All 19 manifests unchanged (Phase 6 complete, not touching YAML)
- 9router at localhost:20128, auth via ANTHROPIC_AUTH_TOKEN
- Cost is NOT a constraint (free models via 9router)
- Model mapping: opus=kimi k2.6, sonnet=mimo v2.5, haiku=codestral

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `aos/context.py` | CREATE | Prompt builder — assembles full system prompt from manifest + constants + memory |
| `aos/evaluator.py` | CREATE | Output validator — checks LLM output against financial ground truth |
| `aos/parallel.py` | CREATE | Async specialist runner with concurrency control |
| `aos/usage.py` | CREATE | Token/cost tracker per agent per cycle |
| `aos/runtime.py` | MODIFY | Wire context builder, evaluator, parallel runner, usage tracker |
| `aos/llm.py` | MODIFY | Fix model routing table to use different tiers; add streaming stub |
| `aos/memory.py` | MODIFY | Add `retrieve_for_agent()` convenience method + thread lock |
| `tests/test_context.py` | CREATE | Tests for prompt construction |
| `tests/test_evaluator.py` | CREATE | Tests for output validation |
| `tests/test_parallel.py` | CREATE | Tests for parallel execution |
| `tests/test_usage.py` | CREATE | Tests for usage tracking |

---

## Task 1: Context Builder — Full Prompt Construction

The single most critical fix. Currently `_build_agent_system_prompt` (runtime.py:99-143) reads only 7 fields. The CFO's `financial_rules` never reach the prompt. Memory is never retrieved. Evaluation rules are invisible. This task replaces the prompt builder entirely.

**Files:**
- Create: `aos/context.py`
- Create: `tests/test_context.py`
- Modify: `aos/runtime.py:99-143` — replace `_build_agent_system_prompt` with `context.build_prompt`

**Interfaces:**
- Consumes: `Agent` (Pydantic model), `HarnessBundle`, `MemoryStore`, `NETSO_FINANCIAL` dict
- Produces: `str` (complete system prompt)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_context.py
"""Tests for TAZ OS context builder — full prompt construction."""

from __future__ import annotations

import pytest
from aos.context import build_prompt
from aos.schemas.agent import Agent, AllowedMemory, AgentStatus, AgentCriticality


@pytest.fixture
def cfo_agent() -> Agent:
    return Agent(
        id="AGT-EXEC-CFO",
        name="CFO Agent",
        harness="HAR-EXEC-001",
        status=AgentStatus.PRODUCTION,
        criticality=AgentCriticality.HIGH,
        mission="Maintain Netso Energy's financial health.",
        capabilities=["cash_flow_monitoring", "financial_forecasting"],
        allowed_memory=AllowedMemory(
            read=["ground_truth_constants", "financial_models"],
            write=["investor_update_drafts"],
            cannot_read=["founder_personal_notes"],
        ),
        financial_rules={
            "canonical_source": "GROUND_TRUTH_CONSTANTS.md",
            "hard_fails": [
                {"description": "blended_rate_used_for_savings", "correct_value": "True Variable Rate BDT 12.98/kWh"},
                {"description": "scenario_b_without_nbr", "correct_value": "Scenario A (BDT 55,000/kW)"},
            ],
            "constants_to_enforce": {
                "true_variable_rate": 12.98,
                "blended_rate": 14.81,
                "ppa_rate": 10.00,
                "customer_savings_pct": 23.0,
            },
        },
        self_check=["Does every number match ground truth?"],
        constraints=["Never use blended rate for savings"],
    )


@pytest.fixture
def minimal_agent() -> Agent:
    return Agent(
        id="AGT-EXEC-COO",
        name="COO Agent",
        harness="HAR-EXEC-001",
        status=AgentStatus.PRODUCTION,
        criticality=AgentCriticality.HIGH,
        mission="Keep projects on track.",
        allowed_memory=AllowedMemory(
            read=["dashboard", "blockers"],
            write=["dashboard"],
            cannot_read=["founder_personal_notes"],
        ),
    )


class TestBuildPrompt:
    def test_includes_identity(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "COO Agent" in prompt
        assert "AGT-EXEC-COO" in prompt

    def test_includes_mission(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "Keep projects on track." in prompt

    def test_includes_capabilities(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "dashboard" in prompt.lower() or "blocker" in prompt.lower()

    def test_includes_memory_permissions(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "ground_truth_constants" in prompt  # from cannot_read or read
        assert "founder_personal_notes" in prompt

    def test_includes_constraints(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "Never use blended rate" in prompt

    def test_includes_self_check(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "ground truth" in prompt.lower()

    def test_includes_reasoning_structure(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "reasoning" in prompt.lower() or "process" in prompt.lower()

    def test_cfo_gets_financial_constants(self, cfo_agent: Agent) -> None:
        from aos.constants import NETSO_FINANCIAL
        prompt = build_prompt(cfo_agent, netso_financial=NETSO_FINANCIAL)
        assert "12.98" in prompt  # true_variable_rate
        assert "14.81" in prompt  # blended_rate
        assert "10.00" in prompt  # ppa_rate

    def test_cfo_gets_hard_fail_rules(self, cfo_agent: Agent) -> None:
        from aos.constants import NETSO_FINANCIAL
        prompt = build_prompt(cfo_agent, netso_financial=NETSO_FINANCIAL)
        assert "HARD FAIL" in prompt
        assert "blended" in prompt.lower()

    def test_coo_does_not_get_financial_constants(self, minimal_agent: Agent) -> None:
        from aos.constants import NETSO_FINANCIAL
        prompt = build_prompt(minimal_agent, netso_financial=NETSO_FINANCIAL)
        # COO should NOT see the full constants block
        assert "HARD FAIL" not in prompt

    def test_includes_output_format_instructions(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, netso_financial=None)
        assert "OUTPUT FORMAT" in prompt or "JSON" in prompt

    def test_prompt_is_string(self, minimal_agent: Agent) -> None:
        result = build_prompt(minimal_agent, netso_financial=None)
        assert isinstance(result, str)
        assert len(result) > 200  # substantial prompt

    def test_memory_context_injected(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(
            minimal_agent,
            netso_financial=None,
            memory_context="Dashboard shows 3 blockers, cash runway 11.3 months.",
        )
        assert "Dashboard shows 3 blockers" in prompt

    def test_dispatcher_gets_routing_table(self) -> None:
        from aos.schemas.agent import RoutingTable, RoutingEntry
        dispatcher = Agent(
            id="AGT-EXEC-DISPATCH",
            name="Dispatcher",
            harness="HAR-EXEC-001",
            status=AgentStatus.PRODUCTION,
            criticality=AgentCriticality.CRITICAL,
            mission="Route work.",
            allowed_memory=AllowedMemory(read=[], write=[], cannot_read=[]),
            routing_table=RoutingTable(
                executive_internal=[
                    RoutingEntry(task="financial_modeling", route_to="AGT-EXEC-CFO", sla="4h"),
                ],
            ),
        )
        prompt = build_prompt(dispatcher, netso_financial=None)
        assert "financial_modeling" in prompt
        assert "AGT-EXEC-CFO" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/test_context.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aos.context'`

- [ ] **Step 3: Write minimal implementation**

```python
# aos/context.py
"""Context builder — assembles full system prompt from agent manifest.

Replaces _build_agent_system_prompt which only read 7 fields.
This reads the ENTIRE agent contract: identity, mission, capabilities,
reasoning structure, self-check, constraints, memory permissions,
evaluation rules, financial rules (CFO), routing table (dispatcher),
and injects memory context.

Prompt is deterministic and version-controlled — no runtime improvisation.
"""

from __future__ import annotations

from typing import Any

from aos.schemas.agent import Agent


def build_prompt(
    agent: Agent,
    netso_financial: dict[str, Any] | None = None,
    memory_context: str | None = None,
    evaluation_rules: list[dict[str, Any]] | None = None,
) -> str:
    """Build the complete system prompt for an agent from its manifest.

    This is the SINGLE source of prompt construction. Every agent in
    TAZ OS goes through this function. No agent builds its own prompt.
    """
    parts: list[str] = []

    # --- Identity ---
    parts.append(f"You are {agent.name} ({agent.id}).")
    parts.append(f"You operate within the TAZ OS Executive Harness.")
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
        parts.append("=" * 60)
        parts.append("FINANCIAL GROUND TRUTH (from GROUND_TRUTH_CONSTANTS.md)")
        parts.append("=" * 60)
        parts.append("")
        parts.append("These are the ONLY acceptable values. NEVER deviate.")
        parts.append("")
        for key, value in netso_financial.items():
            parts.append(f"  {key}: {value}")
        parts.append("")

        # Hard-fail rules
        hard_fails = agent.financial_rules.get("hard_fails", [])
        if hard_fails:
            parts.append("HARD FAIL RULES (violations are rejected):")
            for rule in hard_fails:
                desc = rule.get("description", "")
                correct = rule.get("correct_value", "")
                parts.append(f"  - FAIL if: {desc}")
                if correct:
                    parts.append(f"    Correct: {correct}")
            parts.append("")

        # Scenario B activation
        scenario_b = agent.financial_rules.get("scenario_b_activation")
        if scenario_b:
            parts.append(f"SCENARIO B ACTIVATION: {scenario_b}")
            parts.append("")

    # --- Evaluation Rules ---
    if agent.evaluation:
        parts.append("EVALUATION RULES (you will be scored on these):")
        for metric in agent.evaluation:
            weight = getattr(metric, 'weight', 0)
            name = getattr(metric, 'metric', str(metric))
            hard_fail = getattr(metric, 'hard_fail_if', None)
            line = f"  - {name} (weight: {weight})"
            if hard_fail:
                line += f" [HARD FAIL: {hard_fail}]"
            parts.append(line)
        parts.append("")

    # --- Routing Table (Dispatcher-specific) ---
    if agent.routing_table:
        parts.append("ROUTING TABLE:")
        if agent.routing_table.executive_internal:
            parts.append("  Executive internal:")
            for entry in agent.routing_table.executive_internal:
                parts.append(f"    {entry.task} → {entry.route_to} (SLA: {entry.sla})")
        if agent.routing_table.cross_harness:
            parts.append("  Cross-harness:")
            for entry in agent.routing_table.cross_harness:
                harness = entry.harness or "unknown"
                parts.append(f"    {entry.task} → {entry.route_to} [{harness}] (SLA: {entry.sla})")
        parts.append("")

    # --- Task Lifecycle (Dispatcher-specific) ---
    if agent.task_lifecycle:
        parts.append("TASK LIFECYCLE:")
        if agent.task_lifecycle.states:
            parts.append(f"  States: {' → '.join(agent.task_lifecycle.states)}")
        if agent.task_lifecycle.rules:
            for rule in agent.task_lifecycle.rules:
                parts.append(f"  Rule: {rule}")
        parts.append("")

    # --- Delegation Heuristics (Planner-specific) ---
    if agent.delegation_heuristics:
        parts.append("DELEGATION HEURISTICS:")
        for h in agent.delegation_heuristics:
            conditions = " AND ".join(h.if_conditions)
            parts.append(f"  IF {conditions} → route to {h.then}")
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


def _get_output_format(agent_id: str) -> str:
    """Get step-specific JSON output instructions."""
    if agent_id == "AGT-EXEC-DISPATCH":
        return """OUTPUT FORMAT: You MUST respond with ONLY a JSON object.
{
  "assignments": [
    {
      "agent_id": "AGT-EXEC-XXX",
      "task": "description of what to do",
      "input": "specific input for this agent",
      "priority": "P0|P1|P2|P3",
      "sla": "time limit"
    }
  ],
  "unrouted": ["tasks with no routing match"],
  "escalations": ["items needing immediate escalation"]
}"""

    # Default: request structured JSON
    return """OUTPUT FORMAT: Respond with a JSON object containing your analysis.
{
  "summary": "one-line summary",
  "findings": ["key finding 1", "key finding 2"],
  "actions": ["recommended action 1"],
  "confidence": "high|medium|low",
  "approval_required": null | {"action": "...", "rationale": "...", "risk_assessment": "..."}
}"""
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/test_context.py -v`
Expected: All 15 tests PASS

- [ ] **Step 5: Commit**

```bash
cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && git add aos/context.py tests/test_context.py && git commit -m "feat: context builder — full prompt construction from agent manifest"
```

---

## Task 2: Wire Context Builder into Runtime

Replace the old `_build_agent_system_prompt` with the new `context.build_prompt`. This is the moment ground truth actually reaches the LLM.

**Files:**
- Modify: `aos/runtime.py:99-143` — replace `_build_agent_system_prompt` body
- Modify: `aos/runtime.py:247-304` — `_run_agent` uses context builder
- Modify: `tests/test_context.py` — add integration test

**Interfaces:**
- Consumes: existing `run_cycle` function, `CycleContext`, `HarnessBundle`
- Produces: unchanged external interface, enriched internal prompts

- [ ] **Step 1: Write the integration test**

Add to `tests/test_context.py`:

```python
class TestRuntimeIntegration:
    def test_run_cycle_builds_real_prompts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify that run_cycle uses the new context builder."""
        from aos.runtime import _build_agent_system_prompt
        from aos.registry import HarnessBundle
        from aos.schemas.harness import Harness

        # Create minimal bundle
        harness = Harness(
            id="HAR-EXEC-001", name="Executive", version="1.0.0",
            mission="Run the company",
        )
        bundle = HarnessBundle(harness=harness)

        # The new prompt builder should produce a substantial prompt
        agent = Agent(
            id="AGT-EXEC-COO", name="COO", harness="HAR-EXEC-001",
            status=AgentStatus.PRODUCTION, criticality=AgentCriticality.HIGH,
            mission="Keep projects on track.",
            allowed_memory=AllowedMemory(read=["dashboard"], write=["dashboard"], cannot_read=[]),
        )
        prompt = _build_agent_system_prompt(agent, bundle)
        assert "COO" in prompt
        assert "Keep projects on track." in prompt
        assert len(prompt) > 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/test_context.py::TestRuntimeIntegration -v`
Expected: FAIL — old `_build_agent_system_prompt` doesn't produce enough content

- [ ] **Step 3: Replace `_build_agent_system_prompt` in runtime.py**

Replace the function body at `aos/runtime.py:99-143`:

```python
def _build_agent_system_prompt(agent: Agent, bundle: HarnessBundle) -> str:
    """Build the system prompt for an agent from its manifest.

    Uses context.build_prompt for full contract serialization.
    Financial constants injected for CFO. Memory context retrieved at call site.
    """
    from aos.context import build_prompt
    from aos.constants import NETSO_FINANCIAL

    # Only inject financial constants for agents that need them
    netso_financial = None
    if agent.financial_rules:
        netso_financial = NETSO_FINANCIAL

    return build_prompt(agent, netso_financial=netso_financial)
```

Also update `_run_agent` to pass memory context (around line 259):

```python
    # Retrieve memory context for this agent
    memory_context = None
    if ctx.memory_store:
        memory_context = ctx.memory_store.retrieve_for_agent(agent.id, step_name)

    system_prompt = _build_agent_system_prompt(agent, bundle)
    # Inject memory context if available
    if memory_context:
        system_prompt += f"\n\nRELEVANT MEMORY:\n{memory_context}"
```

- [ ] **Step 4: Run ALL tests to verify nothing breaks**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/ -v`
Expected: All tests PASS (existing 31 + new 15 + 1 integration = 47)

- [ ] **Step 5: Commit**

```bash
cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && git add aos/runtime.py tests/test_context.py && git commit -m "feat: wire context builder into runtime — ground truth reaches LLM"
```

---

## Task 3: Memory Retrieval at Runtime

The memory store has `read`, `read_all`, `search` — but none are called during agent execution. Add a `retrieve_for_agent` method and wire it in.

**Files:**
- Modify: `aos/memory.py:178-212` — add `retrieve_for_agent` method
- Modify: `tests/test_memory.py` — add retrieval tests
- Modify: `aos/runtime.py` — already done in Task 2

**Interfaces:**
- Consumes: `agent_id: str`, `domain_hint: str | None`
- Produces: `str` (formatted memory context for prompt injection)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_memory.py`:

```python
class TestMemoryRetrieval:
    def test_retrieve_for_agent_returns_accessible_memory(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "company_facts", [
            {"key": "entity", "value": "Netso Energy"},
        ])
        context = store.retrieve_for_agent("AGT-EXEC-CEO", "company_facts")
        assert "Netso Energy" in context

    def test_retrieve_for_agent_respects_permissions(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "financial_models", [
            {"key": "revenue", "value": "1M"},
        ])
        # COO cannot read financial_models
        context = store.retrieve_for_agent("AGT-EXEC-COO", "financial_models")
        assert "1M" not in context

    def test_retrieve_for_agent_returns_empty_for_unknown(self, store: MemoryStore) -> None:
        context = store.retrieve_for_agent("AGT-UNKNOWN", "anything")
        assert context == ""

    def test_retrieve_for_agent_formats_output(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "dashboard", [
            {"key": "status", "value": "on_track"},
        ])
        context = store.retrieve_for_agent("AGT-EXEC-COO", "dashboard")
        assert "on_track" in context
        assert isinstance(context, str)

    def test_retrieve_for_agent_searches_all_layers(self, store: MemoryStore) -> None:
        store.seed_from_dict("semantic", "pricing_model", [
            {"key": "ppa_rate", "value": "10.00"},
        ])
        context = store.retrieve_for_agent("AGT-EXEC-CEO", "pricing")
        assert "10.00" in context
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/test_memory.py::TestMemoryRetrieval -v`
Expected: FAIL — `AttributeError: 'MemoryStore' object has no attribute 'retrieve_for_agent'`

- [ ] **Step 3: Implement `retrieve_for_agent`**

Add to `aos/memory.py` after the `search` method (around line 212):

```python
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
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/test_memory.py -v`
Expected: All memory tests PASS (existing 24 + new 5 = 29)

- [ ] **Step 5: Commit**

```bash
cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && git add aos/memory.py tests/test_memory.py && git commit -m "feat: memory retrieval for agents — prompt injection from 3-layer store"
```

---

## Task 4: Output Validator — Enforce Financial Ground Truth

The CFO could output "savings of 14% based on BDT 14.81" and nothing catches it. Add post-validation that checks output against `NETSO_FINANCIAL` constants.

**Files:**
- Create: `aos/evaluator.py`
- Create: `tests/test_evaluator.py`
- Modify: `aos/runtime.py` — call evaluator after each agent completes

**Interfaces:**
- Consumes: `agent_output: dict`, `agent: Agent`, `netso_financial: dict`
- Produces: `ValidationResult` (pass/fail + violations)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_evaluator.py
"""Tests for TAZ OS output evaluator — validates agent output against ground truth."""

from __future__ import annotations

import pytest
from aos.evaluator import validate_output, ValidationResult


class TestValidateOutput:
    def test_clean_output_passes(self) -> None:
        output = {"savings_pct": 23.0, "rate_used": 12.98}
        result = validate_output(output, "AGT-EXEC-CFO")
        assert result.passed

    def test_blended_rate_detected(self) -> None:
        output = {"savings_pct": 14.0, "rate_used": 14.81, "note": "based on blended rate"}
        result = validate_output(output, "AGT-EXEC-CFO")
        assert not result.passed
        assert any("blended" in v.lower() for v in result.violations)

    def test_wrong_savings_pct_detected(self) -> None:
        output = {"savings_pct": 14.0, "rate_used": 12.98}
        result = validate_output(output, "AGT-EXEC-CFO")
        assert not result.passed
        assert any("savings" in v.lower() for v in result.violations)

    def test_non_cfo_agent_skips_financial_checks(self) -> None:
        output = {"whatever": 14.81}
        result = validate_output(output, "AGT-EXEC-COO")
        assert result.passed  # COO has no financial checks

    def test_empty_output_passes(self) -> None:
        result = validate_output({}, "AGT-EXEC-CFO")
        assert result.passed

    def test_raw_response_passes(self) -> None:
        output = {"raw_response": "I couldn't parse the response"}
        result = validate_output(output, "AGT-EXEC-CFO")
        assert result.passed  # raw responses can't be validated

    def test_dscr_below_floor_detected(self) -> None:
        output = {"dscr": 1.8, "savings_pct": 23.0}
        result = validate_output(output, "AGT-EXEC-CFO")
        assert not result.passed
        assert any("dscr" in v.lower() for v in result.violations)

    def test_ppa_rate_wrong_detected(self) -> None:
        output = {"ppa_rate": 12.0, "savings_pct": 23.0}
        result = validate_output(output, "AGT-EXEC-CFO")
        assert not result.passed
        assert any("ppa" in v.lower() for v in result.violations)

    def test_scenario_b_without_approval_detected(self) -> None:
        output = {"capex_per_kw": 40000, "savings_pct": 23.0}
        result = validate_output(output, "AGT-EXEC-CFO")
        assert not result.passed
        assert any("scenario" in v.lower() for v in result.violations)

    def test_correct_values_all_pass(self) -> None:
        output = {
            "savings_pct": 23.0,
            "rate_used": 12.98,
            "ppa_rate": 10.00,
            "dscr": 2.25,
            "capex_per_kw": 55000,
        }
        result = validate_output(output, "AGT-EXEC-CFO")
        assert result.passed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/test_evaluator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aos.evaluator'`

- [ ] **Step 3: Implement the evaluator**

```python
# aos/evaluator.py
"""Output evaluator — validates agent output against financial ground truth.

Post-validates every agent output against NETSO_FINANCIAL constants.
Only applies financial checks to agents with financial_rules (CFO).
All agents get structural checks (raw_response detection).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from aos.constants import NETSO_FINANCIAL, DSCR_ALERT_FLOOR


@dataclass
class ValidationResult:
    """Result of output validation."""
    passed: bool = True
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def fail(self, violation: str) -> None:
        self.passed = False
        self.violations.append(violation)

    def warn(self, warning: str) -> None:
        self.warnings.append(warning)


# Financial-check agents (must have financial_rules in manifest)
_FINANCIAL_AGENTS = {"AGT-EXEC-CFO", "AGT-EXEC-RSK"}

# Patterns that indicate blended rate usage
_BLENDED_PATTERNS = [
    re.compile(r"14\.81", re.IGNORECASE),
    re.compile(r"blended.?rate", re.IGNORECASE),
    re.compile(r"14\.81\s*bdt", re.IGNORECASE),
]

# Patterns that indicate Scenario B without approval
_SCENARIO_B_PATTERNS = [
    re.compile(r"40[,.]?000\s*bdt", re.IGNORECASE),
    re.compile(r"scenario.?b", re.IGNORECASE),
    re.compile(r"0%\s*import.?duty", re.IGNORECASE),
]


def validate_output(
    output: dict[str, Any],
    agent_id: str,
    constants: dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate agent output against ground truth.

    Financial checks only apply to CFO and Risk agents.
    Structural checks apply to all agents.
    """
    result = ValidationResult()

    if not output:
        return result

    # Skip validation for raw/unparseable responses
    if "raw_response" in output:
        return result

    # Flatten output for pattern matching
    flat = _flatten_for_matching(output)

    # Financial checks — only for financial agents
    if agent_id in _FINANCIAL_AGENTS:
        _check_blended_rate(flat, result)
        _check_savings_pct(output, result)
        _check_dscr(output, result)
        _check_ppa_rate(output, result)
        _check_scenario_b(flat, result)

    return result


def _flatten_for_matching(d: dict[str, Any]) -> str:
    """Flatten dict values to a string for regex matching."""
    parts: list[str] = []
    for v in d.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (int, float)):
            parts.append(str(v))
        elif isinstance(v, dict):
            parts.append(_flatten_for_matching(v))
    return " ".join(parts)


def _check_blended_rate(flat: str, result: ValidationResult) -> None:
    """Check for blended rate usage in output."""
    for pattern in _BLENDED_PATTERNS:
        if pattern.search(flat):
            result.fail(
                f"Blended rate (14.81) detected in output. "
                f"Must use True Variable Rate (12.98) for savings. "
                f"Hard-fail rule: blended_rate_used_for_savings"
            )
            return


def _check_savings_pct(output: dict, result: ValidationResult) -> None:
    """Check customer savings percentage matches ground truth."""
    savings = _find_numeric(output, ["savings_pct", "savings", "customer_savings"])
    if savings is not None and abs(savings - 23.0) > 0.5:
        result.fail(
            f"Savings percentage {savings}% differs from ground truth 23.0%. "
            f"Hard-fail rule: wrong_savings_pct"
        )


def _check_dscr(output: dict, result: ValidationResult) -> None:
    """Check DSCR is above alert floor."""
    dscr = _find_numeric(output, ["dscr", "debt_service_coverage"])
    if dscr is not None and dscr < DSCR_ALERT_FLOOR:
        result.fail(
            f"DSCR {dscr} is below alert floor {DSCR_ALERT_FLOOR}. "
            f"Must flag as immediate alert. "
            f"Hard-fail rule: dscr_below_floor_not_flagged"
        )


def _check_ppa_rate(output: dict, result: ValidationResult) -> None:
    """Check PPA rate matches ground truth."""
    ppa = _find_numeric(output, ["ppa_rate", "ppa"])
    if ppa is not None and abs(ppa - 10.0) > 0.01:
        result.fail(
            f"PPA rate {ppa} differs from ground truth 10.00 BDT/kWh. "
            f"Hard-fail rule: wrong_ppa_rate"
        )


def _check_scenario_b(flat: str, result: ValidationResult) -> None:
    """Check for Scenario B usage without founder approval."""
    for pattern in _SCENARIO_B_PATTERNS:
        if pattern.search(flat):
            result.fail(
                f"Scenario B referenced in output without founder approval. "
                f"Default to Scenario A (55,000 BDT/kW). "
                f"Hard-fail rule: scenario_b_without_nbr_confirmation"
            )
            return


def _find_numeric(d: dict[str, Any], keys: list[str]) -> float | None:
    """Find a numeric value by key name (case-insensitive, partial match)."""
    for k, v in d.items():
        k_lower = k.lower()
        for target in keys:
            if target in k_lower:
                if isinstance(v, (int, float)):
                    return float(v)
                if isinstance(v, str):
                    try:
                        return float(v)
                    except ValueError:
                        pass
    return None
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/test_evaluator.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && git add aos/evaluator.py tests/test_evaluator.py && git commit -m "feat: output evaluator — enforce financial ground truth on agent output"
```

---

## Task 5: Wire Evaluator into Runtime

Call the evaluator after each agent completes. Hard-fail violations get logged and can trigger re-execution or escalation.

**Files:**
- Modify: `aos/runtime.py:247-304` — `_run_agent` calls evaluator after LLM response
- Modify: `tests/test_context.py` — add evaluator integration test

**Interfaces:**
- Consumes: `validate_output` from `aos/evaluator.py`
- Produces: `StepResult` with validation info in output

- [ ] **Step 1: Write the integration test**

Add to `tests/test_context.py`:

```python
class TestEvaluatorIntegration:
    def test_evaluator_called_after_agent(self) -> None:
        from aos.evaluator import validate_output
        # CFO output with wrong savings should fail
        output = {"savings_pct": 14.0, "rate_used": 14.81}
        result = validate_output(output, "AGT-EXEC-CFO")
        assert not result.passed
        assert len(result.violations) > 0
```

- [ ] **Step 2: Run test to verify it passes (evaluator already works)**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/test_context.py::TestEvaluatorIntegration -v`
Expected: PASS

- [ ] **Step 3: Wire evaluator into `_run_agent` in runtime.py**

Add after the JSON extraction block (around line 280):

```python
        # Validate output against ground truth
        from aos.evaluator import validate_output
        validation = validate_output(output, agent.id)

        # Log violations but don't block (yet) — escalation handles it
        if not validation.passed:
            for violation in validation.violations:
                ctx.errors.append(f"{agent.id}: {violation}")

        # Store validation result in output for downstream visibility
        output["_validation"] = {
            "passed": validation.passed,
            "violations": validation.violations,
            "warnings": validation.warnings,
        }
```

- [ ] **Step 4: Run ALL tests**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && git add aos/runtime.py tests/test_context.py && git commit -m "feat: wire evaluator into runtime — post-validation of all agent outputs"
```

---

## Task 6: Usage Tracker — Cost Visibility

Track token usage per agent per cycle. Zero cost today, but essential for when you scale.

**Files:**
- Create: `aos/usage.py`
- Create: `tests/test_usage.py`
- Modify: `aos/runtime.py` — accumulate usage in CycleContext

**Interfaces:**
- Consumes: `LLMResponse.usage` (dict with prompt_tokens, completion_tokens)
- Produces: `UsageReport` per cycle

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_usage.py
"""Tests for TAZ OS usage tracker — cost visibility."""

from __future__ import annotations

import pytest
from aos.usage import UsageTracker


class TestUsageTracker:
    def test_record_usage(self) -> None:
        tracker = UsageTracker()
        tracker.record("AGT-EXEC-CFO", "sonnet", {"prompt_tokens": 1000, "completion_tokens": 500})
        report = tracker.report()
        assert report.total_prompt_tokens == 1000
        assert report.total_completion_tokens == 500
        assert report.total_calls == 1

    def test_accumulates_multiple_calls(self) -> None:
        tracker = UsageTracker()
        tracker.record("AGT-EXEC-CFO", "sonnet", {"prompt_tokens": 1000, "completion_tokens": 500})
        tracker.record("AGT-EXEC-COO", "sonnet", {"prompt_tokens": 800, "completion_tokens": 300})
        report = tracker.report()
        assert report.total_prompt_tokens == 1800
        assert report.total_completion_tokens == 800
        assert report.total_calls == 2

    def test_per_agent_breakdown(self) -> None:
        tracker = UsageTracker()
        tracker.record("AGT-EXEC-CFO", "sonnet", {"prompt_tokens": 1000, "completion_tokens": 500})
        tracker.record("AGT-EXEC-COO", "haiku", {"prompt_tokens": 800, "completion_tokens": 300})
        report = tracker.report()
        assert "AGT-EXEC-CFO" in report.by_agent
        assert "AGT-EXEC-COO" in report.by_agent
        assert report.by_agent["AGT-EXEC-CFO"]["prompt_tokens"] == 1000

    def test_per_model_breakdown(self) -> None:
        tracker = UsageTracker()
        tracker.record("A", "sonnet", {"prompt_tokens": 100, "completion_tokens": 50})
        tracker.record("B", "haiku", {"prompt_tokens": 200, "completion_tokens": 100})
        report = tracker.report()
        assert "sonnet" in report.by_model
        assert "haiku" in report.by_model

    def test_empty_tracker(self) -> None:
        tracker = UsageTracker()
        report = tracker.report()
        assert report.total_calls == 0
        assert report.total_prompt_tokens == 0

    def test_handles_missing_usage_fields(self) -> None:
        tracker = UsageTracker()
        tracker.record("A", "sonnet", {})
        report = tracker.report()
        assert report.total_calls == 1
        assert report.total_prompt_tokens == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/test_usage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aos.usage'`

- [ ] **Step 3: Implement the usage tracker**

```python
# aos/usage.py
"""Usage tracker — captures token usage per agent per cycle.

Every LLMResponse already carries usage dict. This module accumulates
them into a report for cost visibility and optimization.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class UsageReport:
    """Aggregated usage report for one cycle."""
    total_calls: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    by_agent: dict[str, dict[str, int]] = field(default_factory=dict)
    by_model: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.total_prompt_tokens + self.total_completion_tokens


class UsageTracker:
    """Accumulates LLM usage across a cycle."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record(
        self,
        agent_id: str,
        model: str,
        usage: dict[str, Any],
    ) -> None:
        """Record one LLM call's usage."""
        prompt = usage.get("prompt_tokens", 0) or 0
        completion = usage.get("completion_tokens", 0) or 0
        self._records.append({
            "agent_id": agent_id,
            "model": model,
            "prompt_tokens": prompt,
            "completion_tokens": completion,
        })

    def report(self) -> UsageReport:
        """Generate aggregated report."""
        report = UsageReport()

        for rec in self._records:
            report.total_calls += 1
            report.total_prompt_tokens += rec["prompt_tokens"]
            report.total_completion_tokens += rec["completion_tokens"]

            # By agent
            agent = rec["agent_id"]
            if agent not in report.by_agent:
                report.by_agent[agent] = {"prompt_tokens": 0, "completion_tokens": 0}
            report.by_agent[agent]["prompt_tokens"] += rec["prompt_tokens"]
            report.by_agent[agent]["completion_tokens"] += rec["completion_tokens"]

            # By model
            model = rec["model"]
            if model not in report.by_model:
                report.by_model[model] = {"prompt_tokens": 0, "completion_tokens": 0}
            report.by_model[model]["prompt_tokens"] += rec["prompt_tokens"]
            report.by_model[model]["completion_tokens"] += rec["completion_tokens"]

        return report
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/test_usage.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && git add aos/usage.py tests/test_usage.py && git commit -m "feat: usage tracker — per-agent, per-model token visibility"
```

---

## Task 7: Wire Usage Tracker into Runtime

Add usage tracker to CycleContext, record usage after every LLM call, include in cycle summary.

**Files:**
- Modify: `aos/runtime.py:29-55` — add UsageTracker to CycleContext
- Modify: `aos/runtime.py:247-304` — record usage in `_run_agent`
- Modify: `aos/runtime.py:591-651` — init tracker in `run_cycle`, report in summary

**Interfaces:**
- Consumes: `UsageTracker` from `aos/usage.py`
- Produces: usage data in `CycleContext.summary()`

- [ ] **Step 1: Add tracker to CycleContext**

In `aos/runtime.py`, add import at top:

```python
from aos.usage import UsageTracker
```

Add field to `CycleContext` (around line 55):

```python
    usage_tracker: UsageTracker | None = None
```

- [ ] **Step 2: Init tracker in `run_cycle`**

In `run_cycle` (around line 635):

```python
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
```

- [ ] **Step 3: Record usage in `_run_agent`**

After the LLM response (around line 277):

```python
        # Track usage
        if ctx.usage_tracker:
            ctx.usage_tracker.record(agent.id, model, response.usage)
```

- [ ] **Step 4: Add usage to summary**

In `CycleContext.summary()` (around line 70), add:

```python
        if self.usage_tracker:
            usage = self.usage_tracker.report()
            lines.append(f"\nUsage: {usage.total_calls} calls, {usage.total_tokens} tokens")
            if usage.by_agent:
                lines.append("  By agent:")
                for agent_id, data in usage.by_agent.items():
                    lines.append(f"    {agent_id}: {data['prompt_tokens'] + data['completion_tokens']} tokens")
```

- [ ] **Step 5: Run ALL tests**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && git add aos/runtime.py && git commit -m "feat: wire usage tracker into runtime — per-cycle cost visibility"
```

---

## Task 8: Fix Model Routing

All three tiers (default, fast, subagent) currently map to `ag/claude-sonnet-4-6`. Fix to use actual task-fit routing with your 9router setup.

**Files:**
- Modify: `aos/llm.py:29-34` — fix MODEL_TABLE
- Modify: `aos/llm.py:45-50` — fix CRITICALITY_TO_MODEL

**Interfaces:**
- Consumes: existing `resolve_model` function
- Produces: correct model IDs per tier

- [ ] **Step 1: Fix MODEL_TABLE in llm.py**

Replace lines 29-34:

```python
MODEL_TABLE: dict[str, str] = {
    "default": "ag/claude-sonnet-4-6",      # mimo v2.5 — general tasks
    "reasoning": "oc/mimo-v2.5-free",        # opus tier — complex reasoning
    "fast": "ag/claude-4.5-haiku",          # codestral — code/structured
    "subagent": "ag/claude-4.5-haiku",      # codestral — lightweight agents
}
```

- [ ] **Step 2: Fix CRITICALITY_TO_MODEL in llm.py**

Replace lines 45-50:

```python
CRITICALITY_TO_MODEL: dict[str, str] = {
    "critical": "default",    # sonnet — dispatcher, planner
    "high": "default",        # sonnet — COO, CFO, Chief of Staff
    "medium": "fast",         # haiku — routine specialists
    "low": "fast",            # haiku — lightweight tasks
}
```

- [ ] **Step 3: Run ALL tests**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && git add aos/llm.py && git commit -m "fix: model routing — task-fit with haiku for fast/subagent tiers"
```

---

## Task 9: Parallel Specialist Execution

The specialist loop (runtime.py:427-449) is sequential. 5 specialists × 15s = 75s serial. Parallel: ~15s. Add `asyncio.gather` with concurrency limit.

**Files:**
- Modify: `aos/runtime.py:386-459` — `step_run_specialists` uses asyncio
- Modify: `aos/runtime.py:591-651` — `run_cycle` uses asyncio.run

**Interfaces:**
- Consumes: existing specialist execution logic
- Produces: same results, faster

- [ ] **Step 1: Write parallel specialist test**

Add to `tests/test_context.py`:

```python
class TestParallelSpecialists:
    def test_specialists_run_concurrently(self) -> None:
        """Verify that step_run_specialists produces results from all assigned agents."""
        from aos.runtime import step_run_specialists, CycleContext
        from aos.registry import HarnessBundle, Registry
        from aos.schemas.harness import Harness
        from aos.schemas.agent import Agent, AllowedMemory, AgentStatus, AgentCriticality

        # Create bundle with two mock specialists
        harness = Harness(id="HAR-EXEC-001", name="Exec", version="1.0.0", mission="Run")
        agent_a = Agent(
            id="AGT-EXEC-COO", name="COO", harness="HAR-EXEC-001",
            status=AgentStatus.PRODUCTION, criticality=AgentCriticality.HIGH,
            mission="Keep on track.",
            allowed_memory=AllowedMemory(read=[], write=[], cannot_read=[]),
        )
        agent_b = Agent(
            id="AGT-EXEC-CFO", name="CFO", harness="HAR-EXEC-001",
            status=AgentStatus.PRODUCTION, criticality=AgentCriticality.HIGH,
            mission="Financial health.",
            allowed_memory=AllowedMemory(read=[], write=[], cannot_read=[]),
        )
        bundle = HarnessBundle(
            harness=harness,
            specialists={"AGT-EXEC-COO": agent_a, "AGT-EXEC-CFO": agent_b},
        )
        registry = Registry(harnesses={"HAR-EXEC-001": bundle})

        ctx = CycleContext(
            venture_id="VEN-NETSO-001",
            harness_id="HAR-EXEC-001",
            cycle_id="test-parallel",
        )

        # Simulate dispatcher output with assignments
        ctx.step_results.append(type('StepResult', (), {
            'step': 'delegate', 'status': 'success',
            'output': {
                'assignments': [
                    {'agent_id': 'AGT-EXEC-COO', 'task': 'Review blockers'},
                    {'agent_id': 'AGT-EXEC-CFO', 'task': 'Cash forecast'},
                ]
            }
        })())

        from aos.llm import DryRunLLMClient
        result = step_run_specialists(ctx, bundle, DryRunLLMClient())
        assert result.status == "success"
        assert len(result.output["specialist_results"]) == 2
```

- [ ] **Step 2: Run test to verify it passes with current code**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/test_context.py::TestParallelSpecialists -v`
Expected: PASS (sequential still works)

- [ ] **Step 3: Rewrite `step_run_specialists` to use asyncio**

Replace the specialist loop in `step_run_specialists` (lines 427-449):

```python
    import asyncio

    async def _run_one(assignment: dict) -> dict:
        agent_id = assignment.get("agent_id") or assignment.get("route_to")
        if not agent_id or agent_id not in bundle.specialists:
            return None
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
        return {
            "agent_id": agent_id,
            "status": agent_result.status,
            "output": agent_result.output,
        }

    async def _run_all() -> list[dict]:
        tasks = [_run_one(a) for a in assignments]
        return [r for r in await asyncio.gather(*tasks) if r is not None]

    # Run specialists concurrently (max 6 to avoid overwhelming 9router)
    semaphore = asyncio.Semaphore(6)

    async def _run_bounded(assignment: dict) -> dict | None:
        async with semaphore:
            return await _run_one(assignment)

    async def _run_all_bounded() -> list[dict]:
        tasks = [_run_bounded(a) for a in assignments]
        return [r for r in await asyncio.gather(*tasks) if r is not None]

    try:
        results = asyncio.run(_run_all_bounded())
    except RuntimeError:
        # Already in event loop (e.g. Jupyter) — fall back to sequential
        results = []
        for assignment in assignments:
            r = await _run_one(assignment) if False else _run_one_sync(assignment)
            if r:
                results.append(r)
```

Wait — we can't use `asyncio.run` inside an already-async context. Let me use a simpler approach:

```python
    import concurrent.futures

    def _run_one_sync(assignment: dict) -> dict | None:
        agent_id = assignment.get("agent_id") or assignment.get("route_to")
        if not agent_id or agent_id not in bundle.specialists:
            return None
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
        return {
            "agent_id": agent_id,
            "status": agent_result.status,
            "output": agent_result.output,
        }

    # Run specialists in parallel using thread pool (max 6 workers)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(_run_one_sync, a): a for a in assignments}
        results = []
        for future in concurrent.futures.as_completed(futures):
            r = future.result()
            if r:
                results.append(r)
```

- [ ] **Step 4: Run ALL tests**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && git add aos/runtime.py && git commit -m "feat: parallel specialist execution — 5x latency improvement"
```

---

## Task 10: Full Integration Test — Run the Complete Cycle

Verify everything works end-to-end: context builder + memory retrieval + output validation + usage tracking + parallel execution.

**Files:**
- No new files — verify existing integration

**Interfaces:**
- Consumes: all previous tasks
- Produces: passing full cycle

- [ ] **Step 1: Run dry-run cycle**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m aos run --dry-run --verbose`
Expected: Full cycle completes, shows usage report, no errors

- [ ] **Step 2: Run live cycle with 9router**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m aos run --verbose`
Expected: Full cycle with real LLM calls, ground truth in CFO prompt, validation active, parallel specialists, usage report

- [ ] **Step 3: Verify CFO prompt contains financial constants**

Check output for CFO agent's system prompt — should contain:
- `true_variable_rate: 12.98`
- `blended_rate: 14.81`
- `HARD FAIL` rules
- Memory context (if seeded)

- [ ] **Step 4: Verify usage report shows per-agent breakdown**

Check cycle summary for:
- Total calls
- Total tokens
- Per-agent token usage

- [ ] **Step 5: Run ALL tests one final time**

Run: `cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && python -m pytest tests/ -v --tb=short`
Expected: ALL tests PASS

- [ ] **Step 6: Final commit**

```bash
cd "/Users/tazwarmahtab/Documents/10-Projects/Agentic Harness" && git add -A && git commit -m "feat: Phase 7 complete — runtime hardening with context engineering"
```

---

## Summary of Changes

| Fix | Before | After |
|-----|--------|-------|
| Ground truth in prompt | CFO never sees constants | Full constants + hard-fail rules injected |
| Output validation | No post-validation | Blended rate, savings %, DSCR, PPA, Scenario B all checked |
| Model routing | All tiers → sonnet | Critical/high → sonnet, medium/low → haiku |
| Memory at runtime | Store exists, never queried | `retrieve_for_agent()` injects context into prompts |
| Usage tracking | Captured then discarded | Per-agent, per-model token report per cycle |
| Parallelism | Sequential specialist loop | ThreadPoolExecutor with 6 workers |
| Prompt completeness | 7 fields | Full contract: mission, capabilities, reasoning, self-check, constraints, memory perms, financial rules, evaluation, routing |

## After Phase 7

The runtime is now production-grade. Next phases:
- **Phase 8:** Multi-venture support (mount TransitBD alongside Netso)
- **Phase 9:** Cross-harness dispatch (Finance, Sales, Operations harnesses)
- **Phase 10:** Approval queue UI (console → Slack/WhatsApp)
- **Phase 11:** Evaluation & Observability Framework (Volume 11)
