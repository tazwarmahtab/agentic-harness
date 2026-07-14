"""Autonomous pipeline -- multi-phase milestone execution loop.

Orchestrates a discuss -> plan -> execute cycle for each phase discovered
from a roadmap file, with persistent state tracking and optional human gates.

Gating policy (from approvals.yml):
  POL-AUTO-001 — Phase Transition Gate: approval required before executing
                  each phase (auto-approved in dry-run / --auto mode).
  POL-AUTO-002 — Milestone Completion Gate: approval required when all
                  phases pass (sign-off before marking milestone done).
  POL-AUTO-003 — Phase Rollback Gate: if audit fails, approval required
                  before rolling back to retry the phase.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict
from aos.llm import RouterLLMClient
from aos.context import build_prompt
from aos.orchestrate.gates import Gate, GateDecision, GateManager
from aos.registry import load_registry, Registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class PhaseRecord:
    """Immutable record of a single phase outcome."""

    phase_id: str
    title: str
    status: PhaseStatus
    started_at: str = ""
    finished_at: str = ""
    duration_s: float = 0.0
    outputs: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class AutonomousState(TypedDict, total=False):
    """LangGraph state carried through the autonomous loop."""

    # Input
    roadmap_file: str
    dry_run: bool
    auto: bool
    max_retries: int

    # Phase bookkeeping
    phases: list[dict[str, Any]]
    current_phase_index: int
    phase_results: list[dict[str, Any]]

    # Rollback tracking
    retries: int

    # Gate tracking
    pending_gate_item_id: Optional[str]

    # Routing
    _next_action: str

    # Roadmap write-back (set to overwrite the roadmap file with status markers)
    writeback_file: Optional[str]

    # Control
    is_complete: bool
    error: Optional[str]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class AutonomousPipeline:
    """Encapsulates the LangGraph StateGraph for autonomous execution.

    Usage::

        pipeline = AutonomousPipeline(roadmap_file="ROADMAP.md", dry_run=True)
        rc = pipeline.run()
    """

    def __init__(
        self,
        roadmap_file: str = "ROADMAP.md",
        dry_run: bool = False,
        auto: bool = False,
        project_root: Optional[Path] = None,
        harness_id: str = "HAR-AUTO-001",
        gate_manager: Optional[GateManager] = None,
        gate_timeout_s: float = 300.0,
        max_retries: int = 3,
    ) -> None:
        self.roadmap_file = roadmap_file
        self.dry_run = dry_run
        self.auto = auto
        self.project_root = project_root or Path.cwd()
        self.harness_id = harness_id
        self.gate_timeout_s = gate_timeout_s
        self.max_retries = max_retries

        # Gate manager — create default if not supplied
        if gate_manager is not None:
            self.gate_manager = gate_manager
        else:
            queue_path = self.project_root / "aos" / "approvals.jsonl"
            log_path = self.project_root / "aos" / "decisions.jsonl"
            self.gate_manager = GateManager(
                persistence_path=queue_path,
                decision_log_path=log_path,
            )

        # Load registry and llm client — load from the autonomous subdirectory
        # so HAR-AUTO-001 and its specialists are found.
        self.registry = load_registry(
            self.project_root / "aos" / "harnesses" / "autonomous"
        )
        self.llm = RouterLLMClient()

        self.graph = self._build_graph()
        self.compiled_graph = self.graph.compile()

    # ------------------------------------------------------------------
    # Graph construction
    # ------------------------------------------------------------------

    def _build_graph(self) -> StateGraph:  # type: ignore[type-arg]
        g = StateGraph(AutonomousState)

        g.add_node("discover_phases", self._discover_phases)
        g.add_node("gate_phase", self._gate_phase)
        g.add_node("run_phase", self._run_phase)
        g.add_node("check_phase_result", self._check_phase_result)
        g.add_node("rollback_gate", self._rollback_gate)
        g.add_node("update_state", self._update_state)
        g.add_node("audit_complete", self._audit_complete)
        g.add_node("gate_milestone", self._gate_milestone)

        g.set_entry_point("discover_phases")

        g.add_conditional_edges(
            "discover_phases",
            self._should_continue_phases,
            {"continue": "gate_phase", "end": "audit_complete"},
        )
        g.add_conditional_edges(
            "gate_phase",
            self._after_gate_phase,
            {"approved": "run_phase", "rejected": "audit_complete"},
        )
        g.add_edge("run_phase", "check_phase_result")
        g.add_conditional_edges(
            "check_phase_result",
            self._after_check_phase,
            {"passed": "update_state", "failed": "rollback_gate", "error": "audit_complete"},
        )
        g.add_conditional_edges(
            "rollback_gate",
            self._after_rollback_gate,
            {"retry": "gate_phase", "stop": "audit_complete"},
        )
        g.add_conditional_edges(
            "update_state",
            self._should_continue_phases,
            {"continue": "gate_phase", "end": "gate_milestone"},
        )
        g.add_conditional_edges(
            "gate_milestone",
            self._after_gate_milestone,
            {"approved": "audit_complete", "rejected": "audit_complete"},
        )
        g.add_edge("audit_complete", END)

        return g

    # ------------------------------------------------------------------
    # Node implementations
    # ------------------------------------------------------------------

    def _discover_phases(self, state: AutonomousState) -> dict[str, Any]:
        """Parse the roadmap file and populate *phases* in state.

        Supports two roadmap formats:

        Simple (one-liner per phase)::

            ## Phase 1: Foundation
            Set up scaffolding.

        Rich (with acceptance criteria and deliverables)::

            ## Phase 1: Foundation
            Set up project scaffolding and core modules.

            **Acceptance Criteria:**
            - Directory structure created
            - pyproject.toml configured
            - CI pipeline passes

            **Deliverables:**
            - aos/ package skeleton
            - pyproject.toml
            - .github/workflows/ci.yml
        """
        roadmap_file = state.get("roadmap_file", self.roadmap_file)
        logger.info("discover_phases: reading %s", roadmap_file)
        print(f"[autonomous] discover_phases -- reading {roadmap_file}")

        roadmap_path = Path(roadmap_file)
        if not roadmap_path.is_absolute():
            roadmap_path = self.project_root / roadmap_file
        phases: list[dict[str, Any]] = []

        if roadmap_path.exists():
            text = roadmap_path.read_text()
            phases = self._parse_roadmap(text)

        if not phases:
            # Fallback: single synthetic phase so the loop has something to do.
            phases.append(
                {
                    "id": "phase-0",
                    "title": "Default phase (no roadmap phases found)",
                    "description": "",
                    "acceptance_criteria": [],
                    "deliverables": [],
                    "status": PhaseStatus.PENDING.value,
                }
            )

        print(f"[autonomous] discovered {len(phases)} phase(s)")
        for ph in phases:
            criteria = len(ph.get("acceptance_criteria", []))
            deliverables = len(ph.get("deliverables", []))
            print(f"  - {ph['id']}: {ph['title']} ({criteria} criteria, {deliverables} deliverables)")

        return {
            "phases": phases,
            "current_phase_index": 0,
            "phase_results": [],
            "retries": 0,
            "is_complete": False,
        }

    @staticmethod
    def _parse_roadmap(text: str) -> list[dict[str, Any]]:
        """Parse markdown roadmap into structured phase dicts."""
        import re

        phases: list[dict[str, Any]] = []
        # Split on ## Phase headings (prepend \n to ensure first heading is found)
        sections = re.split(r"\n(?=## Phase\b)", "\n" + text)
        # Filter out empty leading section from the prepend
        sections = [s for s in sections if s.strip()]

        phase_counter = 0
        for section in sections:
            lines = section.strip().splitlines()
            if not lines or not lines[0].lower().startswith("## phase"):
                continue

            title = lines[0].lstrip("#").strip()
            body = "\n".join(lines[1:]).strip()

            # Extract description (text before first ** block or bullet list)
            description_lines: list[str] = []
            acceptance_criteria: list[str] = []
            deliverables: list[str] = []

            current_section = "description"
            for line in lines[1:]:
                stripped = line.strip()
                if not stripped:
                    continue

                # Detect section headers
                lower = stripped.lower()
                if "**acceptance criteria**" in lower or "acceptance criteria:" in lower:
                    current_section = "criteria"
                    continue
                if "**deliverables**" in lower or "deliverables:" in lower:
                    current_section = "deliverables"
                    continue
                if "**dependencies**" in lower or "dependencies:" in lower:
                    current_section = "done"
                    continue

                # Strip bullet markers
                bullet = re.sub(r"^[-*]\s+", "", stripped)

                if current_section == "criteria":
                    acceptance_criteria.append(bullet)
                elif current_section == "deliverables":
                    deliverables.append(bullet)
                elif current_section == "description":
                    description_lines.append(stripped)

            phases.append(
                {
                    "id": f"phase-{phase_counter}",
                    "title": title,
                    "description": " ".join(description_lines),
                    "acceptance_criteria": acceptance_criteria,
                    "deliverables": deliverables,
                    "status": PhaseStatus.PENDING.value,
                }
            )
            phase_counter += 1

        return phases

    # ------------------------------------------------------------------
    # Gate nodes (POL-AUTO-001, POL-AUTO-002)
    # ------------------------------------------------------------------

    def _gate_phase(self, state: AutonomousState) -> dict[str, Any]:
        """Phase Transition Gate (POL-AUTO-001).

        Creates an approval item for the next phase and blocks until the
        founder approves or rejects.  Auto-approved in dry-run / --auto mode.
        """
        idx = state.get("current_phase_index", 0)
        phases = state.get("phases", [])
        if idx >= len(phases):
            return {}

        phase = phases[idx]
        phase_id = phase["id"]
        title = phase.get("title", phase_id)

        # Auto-approve in dry-run or --auto mode
        auto = state.get("dry_run") or state.get("auto")
        if auto:
            print(f"[autonomous] gate_phase -- {phase_id} auto-approved ({'dry-run' if state.get('dry_run') else '--auto'})")
            return {"pending_gate_item_id": None}

        # Check if this gate was already decided (e.g. after resume)
        existing = self.gate_manager.resolve_pending(Gate.SPEC)
        if existing and existing.decision == GateDecision.APPROVED:
            print(f"[autonomous] gate_phase -- {phase_id} previously approved")
            return {"pending_gate_item_id": None}
        if existing and existing.decision == GateDecision.REJECTED:
            print(f"[autonomous] gate_phase -- {phase_id} previously rejected")
            return {"error": f"Phase {phase_id} gate rejected by founder"}

        # Submit approval request
        result = self.gate_manager.check(
            gate=Gate.SPEC,
            summary=f"Approve phase: {title}",
            details={"phase_id": phase_id, "phase_index": idx},
        )

        if result.decision == GateDecision.APPROVED:
            print(f"[autonomous] gate_phase -- {phase_id} approved")
            return {"pending_gate_item_id": None}

        if result.decision == GateDecision.REJECTED:
            print(f"[autonomous] gate_phase -- {phase_id} rejected")
            return {"error": f"Phase {phase_id} gate rejected by founder"}

        # SKIPPED — block until founder decides
        print(f"[autonomous] gate_phase -- {phase_id} waiting for founder decision...")
        wait_result = self.gate_manager.wait_for_decision(
            result.item_id, Gate.SPEC, timeout_s=self.gate_timeout_s,
        )

        if wait_result.decision == GateDecision.APPROVED:
            print(f"[autonomous] gate_phase -- {phase_id} approved by founder")
            return {"pending_gate_item_id": None}

        if wait_result.decision == GateDecision.REJECTED:
            print(f"[autonomous] gate_phase -- {phase_id} rejected by founder")
            return {"error": f"Phase {phase_id} gate rejected by founder"}

        # Timeout
        print(f"[autonomous] gate_phase -- {phase_id} gate timed out")
        return {"error": f"Phase {phase_id} gate timed out after {self.gate_timeout_s:.0f}s"}

    def _gate_milestone(self, state: AutonomousState) -> dict[str, Any]:
        """Milestone Completion Gate (POL-AUTO-002).

        Requires founder sign-off when all phases pass.
        Auto-approved in dry-run / --auto mode or if any phase failed
        (milestone is incomplete — no sign-off needed, just report).
        """
        results = state.get("phase_results", [])
        failed = any(r.get("status") == PhaseStatus.FAILED.value for r in results)

        if failed:
            print("[autonomous] gate_milestone -- skipping (phases failed, no sign-off needed)")
            return {}

        auto = state.get("dry_run") or state.get("auto")
        if auto:
            mode = "dry-run" if state.get("dry_run") else "--auto"
            print(f"[autonomous] gate_milestone -- auto-approved ({mode})")
            return {}

        result = self.gate_manager.check(
            gate=Gate.SHIP,
            summary="Approve milestone completion sign-off",
            details={
                "total_phases": len(results),
                "passed": sum(1 for r in results if r.get("status") == PhaseStatus.PASSED.value),
            },
        )

        if result.decision == GateDecision.APPROVED:
            print("[autonomous] gate_milestone -- approved")
            return {}

        if result.decision == GateDecision.REJECTED:
            print("[autonomous] gate_milestone -- rejected by founder")
            return {"error": "Milestone completion rejected by founder"}

        # Block
        print("[autonomous] gate_milestone -- waiting for founder sign-off...")
        wait_result = self.gate_manager.wait_for_decision(
            result.item_id, Gate.SHIP, timeout_s=self.gate_timeout_s,
        )

        if wait_result.decision == GateDecision.APPROVED:
            print("[autonomous] gate_milestone -- approved by founder")
            return {}

        if wait_result.decision == GateDecision.REJECTED:
            print("[autonomous] gate_milestone -- rejected by founder")
            return {"error": "Milestone completion rejected by founder"}

        print("[autonomous] gate_milestone -- timed out")
        return {"error": f"Milestone gate timed out after {self.gate_timeout_s:.0f}s"}

    # ------------------------------------------------------------------
    # Execution nodes
    # ------------------------------------------------------------------

    def _run_phase(self, state: AutonomousState) -> dict[str, Any]:
        """Execute the discuss -> plan -> execute sub-loop for the current phase.

        Builds rich context from the phase plan (description, acceptance
        criteria, deliverables) and passes it to the executor and auditor
        specialists via ``build_prompt``.
        """
        idx = state.get("current_phase_index", 0)
        phases = state.get("phases", [])
        if idx >= len(phases):
            return {"is_complete": True}

        phase = phases[idx]
        phase_id = phase["id"]
        title = phase.get("title", phase_id)
        retries = state.get("retries", 0)

        started = datetime.now().isoformat()
        retry_tag = f" (retry {retries})" if retries else ""
        print(f"[autonomous] run_phase -- {phase_id}: {title}{retry_tag}")

        # Build rich phase context for specialists
        phase_context = self._build_phase_context(phase, state)

        error_msg: Optional[str] = None
        exec_output: Optional[str] = None
        audit_output: Optional[str] = None

        if state.get("dry_run"):
            print(f"[autonomous]   (dry-run, skipping execution for {phase_id})")
        else:
            bundle = self.registry.get_harness(self.harness_id)
            if not bundle:
                error_msg = f"Harness {self.harness_id} not found in registry"
            else:
                executor = bundle.specialists.get("AGT-AUTO-EXEC")
                auditor = bundle.specialists.get("AGT-AUTO-AUDIT")
                if not executor or not auditor:
                    error_msg = "Specialist agents not found"
                else:
                    try:
                        # --- Executor ---
                        exec_prompt = build_prompt(
                            executor, memory_context=phase_context,
                        )
                        resp = self.llm.complete(
                            model="default",
                            system=exec_prompt,
                            messages=[{
                                "role": "user",
                                "content": (
                                    f"Execute phase: {title}\n\n"
                                    f"{phase_context}\n\n"
                                    "Implement the deliverables listed above. "
                                    "Write tests. Output your result as JSON."
                                ),
                            }],
                        )
                        exec_output = resp.content
                        print(f"[autonomous]   executor output: {len(exec_output)} chars")

                        # --- Auditor ---
                        audit_prompt = build_prompt(
                            auditor,
                            memory_context=(
                                f"{phase_context}\n\n"
                                f"EXECUTOR OUTPUT:\n{exec_output}"
                            ),
                        )
                        audit_resp = self.llm.complete(
                            model="default",
                            system=audit_prompt,
                            messages=[{
                                "role": "user",
                                "content": (
                                    f"Audit the implementation of phase: {title}\n\n"
                                    "Verify each acceptance criterion against the "
                                    "executor's output. Output your audit as JSON "
                                    "with a 'verdict' field: PASS or FAIL."
                                ),
                            }],
                        )
                        audit_output = audit_resp.content
                        print(f"[autonomous]   auditor output: {len(audit_output)} chars")

                        # --- Check verdict ---
                        verdict = self._parse_audit_verdict(audit_output)
                        if verdict == "FAIL":
                            error_msg = f"Audit FAILED for {phase_id}"
                            print(f"[autonomous]   ✗ audit: FAIL")

                    except Exception as exc:
                        error_msg = f"LLM execution failed: {exc}"

        finished = datetime.now().isoformat()

        if error_msg:
            record = {
                "phase_id": phase_id,
                "title": title,
                "status": PhaseStatus.FAILED.value,
                "started_at": started,
                "finished_at": finished,
                "error": error_msg,
                "exec_output": exec_output,
                "audit_output": audit_output,
            }
            return {
                "phase_results": state.get("phase_results", []) + [record],
                "error": error_msg,
            }

        record = {
            "phase_id": phase_id,
            "title": title,
            "status": PhaseStatus.PASSED.value,
            "started_at": started,
            "finished_at": finished,
            "exec_output": exec_output,
            "audit_output": audit_output,
        }
        return {"phase_results": state.get("phase_results", []) + [record]}

    @staticmethod
    def _build_phase_context(
        phase: dict[str, Any], state: AutonomousState,
    ) -> str:
        """Build a rich context string for specialist agents."""
        parts: list[str] = []
        parts.append(f"PHASE: {phase.get('title', phase['id'])}")
        parts.append(f"PHASE ID: {phase['id']}")

        description = phase.get("description", "")
        if description:
            parts.append(f"\nDESCRIPTION:\n{description}")

        criteria = phase.get("acceptance_criteria", [])
        if criteria:
            parts.append("\nACCEPTANCE CRITERIA (you MUST satisfy all of these):")
            for i, c in enumerate(criteria, 1):
                parts.append(f"  {i}. {c}")

        deliverables = phase.get("deliverables", [])
        if deliverables:
            parts.append("\nDELIVERABLES (you MUST produce all of these):")
            for d in deliverables:
                parts.append(f"  - {d}")

        retries = state.get("retries", 0)
        if retries:
            parts.append(f"\nNOTE: This is retry #{retries}. The previous attempt "
                         f"failed. Review the prior error and avoid repeating it.")

        prior_results = state.get("phase_results", [])
        if prior_results:
            last = prior_results[-1]
            if last.get("error"):
                parts.append(f"\nPRIOR ATTEMPT ERROR:\n{last['error']}")

        return "\n".join(parts)

    @staticmethod
    def _parse_audit_verdict(audit_output: str) -> str:
        """Extract PASS/FAIL verdict from audit output."""
        import re
        # Look for "verdict": "PASS" or "verdict": "FAIL" in JSON-like output
        match = re.search(r'"verdict"\s*:\s*"(PASS|FAIL)"', audit_output, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        # Fallback: look for standalone PASS or FAIL
        if re.search(r"\bFAIL\b", audit_output):
            return "FAIL"
        return "PASS"

    # ------------------------------------------------------------------
    # Phase result + rollback nodes (POL-AUTO-003)
    # ------------------------------------------------------------------

    def _check_phase_result(self, state: AutonomousState) -> dict[str, Any]:
        """Inspect the last phase result and route accordingly.

        Returns a routing key via ``_next_action`` so the conditional edge
        can choose between update_state (passed), rollback_gate (failed),
        or audit_complete (hard error with no result).
        """
        results = state.get("phase_results", [])
        if not results:
            return {"_next_action": "error"}

        last = results[-1]
        status = last.get("status")

        if status == PhaseStatus.FAILED.value:
            retries = state.get("retries", 0)
            max_retries = state.get("max_retries", 3)
            print(
                f"[autonomous] check_phase_result -- FAILED "
                f"(retries: {retries}/{max_retries})"
            )
            return {"_next_action": "failed"}

        print("[autonomous] check_phase_result -- PASSED")
        return {"_next_action": "passed"}

    def _rollback_gate(self, state: AutonomousState) -> dict[str, Any]:
        """Phase Rollback Gate (POL-AUTO-003).

        When a phase fails, asks founder for approval to retry.
        Auto-approved in dry-run / --auto mode. Rejects automatically
        when max_retries is exhausted.
        """
        idx = state.get("current_phase_index", 0)
        phases = state.get("phases", [])
        retries = state.get("retries", 0)
        max_retries = state.get("max_retries", 3)

        phase_id = phases[idx]["id"] if idx < len(phases) else "unknown"
        title = phases[idx].get("title", phase_id) if idx < len(phases) else phase_id

        # Max retries exhausted — hard stop
        if retries >= max_retries:
            print(
                f"[autonomous] rollback_gate -- {phase_id} max retries "
                f"({max_retries}) exhausted, stopping"
            )
            return {"error": f"Phase {phase_id} failed after {max_retries} retries"}

        # Auto-approve rollback in dry-run / --auto mode
        auto = state.get("dry_run") or state.get("auto")
        if auto:
            mode = "dry-run" if state.get("dry_run") else "--auto"
            print(
                f"[autonomous] rollback_gate -- {phase_id} auto-approved "
                f"({mode}, retry {retries + 1}/{max_retries})"
            )
            return {"retries": retries + 1, "error": None}

        # Check for existing decision
        existing = self.gate_manager.resolve_pending(Gate.DOUBT)
        if existing and existing.decision == GateDecision.APPROVED:
            print(f"[autonomous] rollback_gate -- {phase_id} previously approved")
            return {"retries": retries + 1, "error": None}
        if existing and existing.decision == GateDecision.REJECTED:
            print(f"[autonomous] rollback_gate -- {phase_id} rollback rejected")
            return {"error": f"Rollback of phase {phase_id} rejected by founder"}

        # Submit approval request
        result = self.gate_manager.check(
            gate=Gate.DOUBT,
            summary=f"Approve rollback: {title}",
            details={
                "phase_id": phase_id,
                "retries": retries,
                "max_retries": max_retries,
            },
        )

        if result.decision == GateDecision.APPROVED:
            print(f"[autonomous] rollback_gate -- {phase_id} approved (retry {retries + 1}/{max_retries})")
            return {"retries": retries + 1}

        if result.decision == GateDecision.REJECTED:
            print(f"[autonomous] rollback_gate -- {phase_id} rollback rejected")
            return {"error": f"Rollback of phase {phase_id} rejected by founder"}

        # Block until founder decides
        print(f"[autonomous] rollback_gate -- {phase_id} waiting for rollback approval...")
        wait_result = self.gate_manager.wait_for_decision(
            result.item_id, Gate.DOUBT, timeout_s=self.gate_timeout_s,
        )

        if wait_result.decision == GateDecision.APPROVED:
            print(f"[autonomous] rollback_gate -- {phase_id} approved (retry {retries + 1}/{max_retries})")
            return {"retries": retries + 1, "error": None}

        if wait_result.decision == GateDecision.REJECTED:
            print(f"[autonomous] rollback_gate -- {phase_id} rollback rejected")
            return {"error": f"Rollback of phase {phase_id} rejected by founder"}

        # Timeout
        print(f"[autonomous] rollback_gate -- {phase_id} gate timed out")
        return {"error": f"Rollback gate for {phase_id} timed out after {self.gate_timeout_s:.0f}s"}

    def _update_state(self, state: AutonomousState) -> dict[str, Any]:
        """Persist progress and advance the phase index."""
        idx = state.get("current_phase_index", 0)
        phases = state.get("phases", [])
        next_index = idx + 1
        done = next_index >= len(phases)

        print(
            f"[autonomous] update_state -- advanced to index {next_index} "
            f"({'complete' if done else 'next phase'})"
        )
        # Reset retry counter when advancing to a new phase
        return {"current_phase_index": next_index, "is_complete": done, "retries": 0}

    def _audit_complete(self, state: AutonomousState) -> dict[str, Any]:
        """Synthesise final results and produce a summary."""
        results = state.get("phase_results", [])
        passed = sum(
            1 for r in results if r.get("status") == PhaseStatus.PASSED.value
        )
        failed = sum(
            1 for r in results if r.get("status") == PhaseStatus.FAILED.value
        )

        print("[autonomous] audit_complete -- summary:")
        print(f"[autonomous]   total: {len(results)}, passed: {passed}, failed: {failed}")

        if state.get("error"):
            print(f"[autonomous]   error: {state['error']}")

        # Write-back: update the roadmap file with status markers
        writeback_file = state.get("writeback_file")
        if writeback_file and results:
            self._write_back_roadmap(writeback_file, results)

        return {}

    # ------------------------------------------------------------------
    # Roadmap write-back
    # ------------------------------------------------------------------

    @staticmethod
    def _write_back_roadmap(
        writeback_file: str,
        results: list[dict[str, Any]],
    ) -> None:
        """Overwrite the roadmap file with phase status markers (✓/✗).

        Reads the original roadmap, strips any existing markers, then
        appends the current run's status to each ``## Phase`` heading.
        Idempotent — re-running the pipeline re-marks phases cleanly.
        """
        import re

        path = Path(writeback_file)
        if not path.exists():
            logger.warning("write_back_roadmap: %s not found", writeback_file)
            return

        text = path.read_text()

        # Build lookup: phase_id -> status
        status_map: dict[str, str] = {}
        for r in results:
            pid = r.get("phase_id", "")
            status = r.get("status", "")
            if pid:
                status_map[pid] = status

        # Strip existing markers from all ## Phase lines (idempotent)
        # Handles: "## Phase 1: Title ✓", "## Phase 1: Title ✗ (failed)", etc.
        marker_re = re.compile(r"\s+[✓✗]\s*(?:\(.*\))?\s*$")

        lines = text.splitlines(keepends=True)
        phase_index = 0
        new_lines: list[str] = []

        for line in lines:
            stripped = line.rstrip("\n")

            # Check if this is a ## Phase heading
            if re.match(r"^## Phase\b", stripped):
                # Strip any existing marker
                clean = marker_re.sub("", stripped)

                # Look up status by index
                phase_id = f"phase-{phase_index}"
                status = status_map.get(phase_id, "")

                if status == PhaseStatus.PASSED.value:
                    clean = f"{clean} ✓"
                elif status == PhaseStatus.FAILED.value:
                    clean = f"{clean} ✗"

                new_lines.append(f"{clean}\n")
                phase_index += 1
            else:
                new_lines.append(line)

        path.write_text("".join(new_lines))
        print(f"[autonomous] write_back_roadmap -- updated {writeback_file} ({phase_index} phases)")

    # ------------------------------------------------------------------
    # Conditional edge functions
    # ------------------------------------------------------------------

    @staticmethod
    def _should_continue_phases(state: AutonomousState) -> str:
        """Return 'continue' if more phases remain, else 'end'."""
        if state.get("error"):
            return "end"
        if state.get("is_complete"):
            return "end"
        phases = state.get("phases", [])
        idx = state.get("current_phase_index", 0)
        return "continue" if idx < len(phases) else "end"

    @staticmethod
    def _after_gate_phase(state: AutonomousState) -> str:
        """After phase gate: 'approved' to run, 'rejected' to stop."""
        if state.get("error"):
            return "rejected"
        return "approved"

    @staticmethod
    def _after_check_phase(state: AutonomousState) -> str:
        """After check_phase_result: route based on result status.

        Reads the ``_next_action`` key written by ``_check_phase_result``.
        Falls back to 'error' if absent.
        """
        return state.get("_next_action", "error")

    @staticmethod
    def _after_rollback_gate(state: AutonomousState) -> str:
        """After rollback gate: 'retry' to re-run the phase, 'stop' to end."""
        if state.get("error"):
            return "stop"
        return "retry"

    @staticmethod
    def _after_gate_milestone(state: AutonomousState) -> str:
        """After milestone gate: always go to audit_complete (to report)."""
        return "approved"

    # ------------------------------------------------------------------
    # Public runner
    # ------------------------------------------------------------------

    def run(self) -> int:
        """Execute the autonomous graph.  Returns 0 on success, 1 on failure."""
        print("=" * 60)
        print("  AUTONOMOUS PIPELINE")
        print("=" * 60)
        print(f"  Roadmap:      {self.roadmap_file}")
        print(f"  Dry run:      {self.dry_run}")
        print(f"  Auto:         {self.auto}")
        print(f"  Max retries:  {self.max_retries}")
        print("=" * 60)
        print()

        initial: AutonomousState = {
            "roadmap_file": self.roadmap_file,
            "dry_run": self.dry_run,
            "auto": self.auto,
            "max_retries": self.max_retries,
            "writeback_file": self.roadmap_file,
            "phases": [],
            "current_phase_index": 0,
            "phase_results": [],
            "retries": 0,
            "is_complete": False,
        }

        try:
            final_state = self.compiled_graph.invoke(initial)
        except Exception as exc:
            logger.exception("Autonomous pipeline crashed")
            print(f"[autonomous] PIPELINE ERROR: {exc}")
            return 1

        error = final_state.get("error")
        if error:
            print(f"\n[autonomous] Finished with error: {error}")
            return 1

        print()
        print("=" * 60)
        print("  AUTONOMOUS PIPELINE COMPLETE")
        print("=" * 60)
        return 0
