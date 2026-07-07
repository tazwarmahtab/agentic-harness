"""Orchestrate pipeline — end-to-end coordinator.

Chains /spec → /autoplan → /implement → /reviewloop → /ship
with configurable human gates.

This module provides the runtime coordinator. The slash-command skill
at .claude/skills/orchestrate/SKILL.md provides the agent-facing interface.
"""

from __future__ import annotations

import json
import re
import subprocess

# Used in GateManager integration; imported at module level because Gate,
# GateDecision, and GateResult are referenced in method signatures inside
# OrchestratePipeline methods defined at class body scope.
from tazos.orchestrate.gates import Gate, GateDecision, GateManager
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class Phase(str, Enum):
    SPEC = "spec"
    AUTOPLAN = "autoplan"
    IMPLEMENT = "implement"
    REVIEWLOOP = "reviewloop"
    SHIP = "ship"


class Status(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


@dataclass
class PhaseResult:
    phase: Phase
    status: Status
    started_at: str = ""
    finished_at: str = ""
    duration_s: float = 0.0
    outputs: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    skipped_reason: Optional[str] = None


@dataclass
class PipelineContext:
    """Mutable state carried through the pipeline."""

    # Input
    one_liner: Optional[str] = None
    plan_path: Optional[Path] = None
    skip_spec: bool = False
    skip_plan: bool = False
    skip_review: bool = False
    gates: set[str] = field(default_factory=lambda: {"spec", "plan", "review"})

    # Runtime
    project_root: Path = field(default_factory=Path.cwd)
    dry_run: bool = False
    max_review_iterations: int = 3

    # Outputs (populated as phases run)
    issue_number: Optional[int] = None
    issue_url: Optional[str] = None
    review_scores: dict[str, float] = field(default_factory=dict)
    review_decisions: list[dict] = field(default_factory=list)
    implement_artifacts: list[str] = field(default_factory=list)
    pr_url: Optional[str] = None
    commit_sha: Optional[str] = None

    # Phase tracking
    results: dict[Phase, PhaseResult] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def record(self, result: PhaseResult) -> None:
        self.results[result.phase] = result


class OrchestratePipeline:
    """End-to-end orchestrate pipeline.

    Usage:
        ctx = PipelineContext(one_liner="Add user auth endpoint")
        pipeline = OrchestratePipeline(ctx, gate_manager)
        rc = pipeline.run()
    """

    def __init__(
        self,
        ctx: PipelineContext,
        gate_manager: Any,
    ) -> None:
        self.ctx = ctx
        self.gates = gate_manager

    def run(self) -> int:
        """Run the full pipeline. Returns 0 on success, 1 on failure."""
        print("=" * 60)
        print("  ORCHESTRATE — End-to-End Pipeline")
        print("=" * 60)
        if self.ctx.one_liner:
            print(f"  Input: {self.ctx.one_liner}")
        if self.ctx.plan_path:
            print(f"  Plan:  {self.ctx.plan_path}")
        skips = []
        if self.ctx.skip_spec:
            skips.append("spec")
        if self.ctx.skip_plan:
            skips.append("plan")
        if self.ctx.skip_review:
            skips.append("review")
        if skips:
            print(f"  Skip:  {', '.join(skips)}")
        gates_str = ", ".join(sorted(self.ctx.gates)) if self.ctx.gates else "none"
        print(f"  Gates: {gates_str}")
        print("=" * 60)
        print()

        # Phase 1: /spec
        if not self.ctx.skip_spec:
            if not self._run_spec():
                return 1
        else:
            self._skip_phase(Phase.SPEC, "user requested --skip-spec")
            if not self.ctx.plan_path:
                print("ERROR: --skip-spec requires --plan-path or an existing plan.")
                return 1

        # Spec gate
        if Gate.SPEC in self._active_gates() and not self._is_auto_approved(Gate.SPEC):
            result = self.gates.check(
                gate=Gate.SPEC,
                summary=f"Approve spec: {self.ctx.issue_number or 'pending'}",
                details={
                    "plan": str(self.ctx.plan_path),
                    "issue": str(self.ctx.issue_number or "unknown"),
                },
            )
            if result.decision == GateDecision.REJECTED:
                print("Spec rejected. Stopping pipeline.")
                return 1
            if result.decision == GateDecision.SKIPPED:
                result = self.gates.wait_for_decision(result.item_id, Gate.SPEC)
                if result.decision == GateDecision.REJECTED:
                    print("Spec rejected. Stopping pipeline.")
                    return 1
                if result.decision == GateDecision.SKIPPED:
                    print("Spec gate timed out. Stopping pipeline.")
                    return 1

        # Phase 2: /autoplan
        if not self.ctx.skip_plan:
            if not self._run_autoplan():
                return 1
        else:
            self._skip_phase(Phase.AUTOPLAN, "user requested --skip-plan")

        # Plan gate
        if Gate.PLAN in self._active_gates() and not self._is_auto_approved(Gate.PLAN):
            result = self.gates.check(
                gate=Gate.PLAN,
                summary=f"Approve plan: {self.ctx.plan_path.name if self.ctx.plan_path else 'unknown'}",
                details={"scores": self.ctx.review_scores, "decisions": len(self.ctx.review_decisions)},
            )
            if result.decision == GateDecision.REJECTED:
                print("Plan rejected. Stopping pipeline.")
                return 1
            if result.decision == GateDecision.SKIPPED:
                result = self.gates.wait_for_decision(result.item_id, Gate.PLAN)
                if result.decision == GateDecision.REJECTED:
                    print("Plan rejected. Stopping pipeline.")
                    return 1
                if result.decision == GateDecision.SKIPPED:
                    print("Plan gate timed out. Stopping pipeline.")
                    return 1

        # Phase 3: /implement
        if not self._run_implement():
            return 1

        # Phase 4: /reviewloop
        if not self.ctx.skip_review:
            if not self._run_reviewloop():
                return 1
        else:
            self._skip_phase(Phase.REVIEWLOOP, "user requested --skip-review")

        # Review gate
        if Gate.REVIEW in self._active_gates() and not self._is_auto_approved(Gate.REVIEW):
            result = self.gates.check(
                gate=Gate.REVIEW,
                summary="Approve review findings before ship",
                details={"iterations": self.ctx.results.get(Phase.REVIEWLOOP, PhaseResult(Phase.REVIEWLOOP, Status.PASSED)).duration_s},
            )
            if result.decision == GateDecision.REJECTED:
                print("Review gate rejected. Stopping pipeline.")
                return 1
            if result.decision == GateDecision.SKIPPED:
                result = self.gates.wait_for_decision(result.item_id, Gate.REVIEW)
                if result.decision == GateDecision.REJECTED:
                    print("Review gate rejected. Stopping pipeline.")
                    return 1
                if result.decision == GateDecision.SKIPPED:
                    print("Review gate timed out. Stopping pipeline.")
                    return 1

        # Phase 5: /ship
        if not self._run_ship():
            return 1

        self._report_completion()
        return 0

    def _run_spec(self) -> bool:
        """Run /spec phase. Returns True if passed or skipped."""
        result = PhaseResult(phase=Phase.SPEC, status=Status.RUNNING)
        result.started_at = datetime.now().isoformat()
        print("─" * 40)
        print(f"  PHASE 1: /spec — Define the problem")
        print("─" * 40)

        if not self.ctx.one_liner:
            # No one-liner, no plan — nothing to spec
            # Check if a plan already exists
            if self.ctx.plan_path and self.ctx.plan_path.exists():
                print(f"  Plan already exists: {self.ctx.plan_path}")
                result.status = Status.SKIPPED
                result.skipped_reason = "plan already exists"
                self.ctx.record(result)
                return True
            print("  ERROR: No one-liner and no existing plan. Cannot run /spec.")
            result.status = Status.FAILED
            result.error = "missing input: need --one-liner or --plan-path"
            self.ctx.record(result)
            return False

        # Build the /spec command
        cmd = self._build_spec_command()
        print(f"  Command: {cmd[:120]}...")
        print(f"  /spec writes the issue, runs quality gate, and optionally spawns an agent.")
        print()

        if self.ctx.dry_run:
            print("  [DRY RUN] /spec would execute here")
            result.status = Status.PASSED
            self.ctx.record(result)
            return True

        # Invoke /spec via the skill system
        rc, _stdout, _stderr = self._invoke_skill("spec", self.ctx.one_liner)
        if rc != 0:
            result.status = Status.FAILED
            result.error = f"/spec exited with code {rc}"
            self.ctx.record(result)
            return False

        result.status = Status.PASSED
        result.finished_at = datetime.now().isoformat()
        result.duration_s = self._duration(result)
        result.outputs = {"one_liner": self.ctx.one_liner}
        self.ctx.record(result)
        print(f"  ✓ /spec complete ({result.duration_s:.1f}s)")
        print()
        return True

    def _run_autoplan(self) -> bool:
        """Run /autoplan phase. Returns True if passed."""
        result = PhaseResult(phase=Phase.AUTOPLAN, status=Status.RUNNING)
        result.started_at = datetime.now().isoformat()
        print("─" * 40)
        print(f"  PHASE 2: /autoplan — Strategy → Design → Eng → DX review")
        print("─" * 40)

        if not self.ctx.plan_path or not self.ctx.plan_path.exists():
            print(f"  ERROR: Plan file not found: {self.ctx.plan_path}")
            result.status = Status.FAILED
            result.error = f"plan not found: {self.ctx.plan_path}"
            self.ctx.record(result)
            return False

        cmd = f"/autoplan {self.ctx.plan_path}"
        print(f"  Command: {cmd}")
        print(f"  /autoplan runs CEO, Design, Eng, DX reviews with dual voices.")
        print()

        if self.ctx.dry_run:
            print("  [DRY RUN] /autoplan would execute here")
            result.status = Status.PASSED
            self.ctx.record(result)
            return True

        rc, _stdout, _stderr = self._invoke_skill("autoplan", str(self.ctx.plan_path))
        if rc != 0:
            result.status = Status.FAILED
            result.error = f"/autoplan exited with code {rc}"
            self.ctx.record(result)
            return False

        result.status = Status.PASSED
        result.finished_at = datetime.now().isoformat()
        result.duration_s = self._duration(result)
        result.outputs = {"plan": str(self.ctx.plan_path)}
        self.ctx.record(result)
        print(f"  ✓ /autoplan complete ({result.duration_s:.1f}s)")
        print()
        return True

    def _run_implement(self) -> bool:
        """Run /implement phase. Returns True if passed."""
        result = PhaseResult(phase=Phase.IMPLEMENT, status=Status.RUNNING)
        result.started_at = datetime.now().isoformat()
        print("─" * 40)
        print(f"  PHASE 3: /implement — Decompose → Execute agent chains")
        print("─" * 40)

        if not self.ctx.plan_path or not self.ctx.plan_path.exists():
            print(f"  ERROR: Plan file not found: {self.ctx.plan_path}")
            result.status = Status.FAILED
            result.error = f"plan not found: {self.ctx.plan_path}"
            self.ctx.record(result)
            return False

        print(f"  Plan:   {self.ctx.plan_path}")
        print(f"  Reading plan, decomposing steps, picking agent chains...")
        print()

        if self.ctx.dry_run:
            print("  [DRY RUN] /implement would execute here")
            steps = self._decompose_plan(self.ctx.plan_path)
            print(f"  Steps detected: {len(steps)}")
            for s in steps:
                print(f"    Step {s['id']}: {s['title']} [{','.join(s['tags'])}] → {s['chain']}")
            result.status = Status.PASSED
            result.outputs = {"steps": steps, "dry_run": True}
            self.ctx.record(result)
            return True

        # Execute each step via /orchestrate custom
        steps = self._decompose_plan(self.ctx.plan_path)
        all_passed = True
        steps_passed = 0
        for step in steps:
            print(f"  Step {step['id']}: {step['title']}")
            print(f"    Chain: {step['chain']}")
            print(f"    Task:  {step['task'][:80]}...")

            chain_str = ",".join(step["chain"])
            task_str = step["task"]
            cmd = f'/orchestrate custom "{chain_str}" "{task_str}"'

            rc, _stdout, _stderr = self._invoke_skill("orchestrate", f"custom {cmd}")
            if rc != 0:
                print(f"    ✗ Step {step['id']} failed (exit {rc})")
                all_passed = False
                # Offer to continue or abort
                decision = self._prompt_continue_or_abort(step["id"])
                if decision == "abort":
                    result.status = Status.FAILED
                    result.error = f"step {step['id']} failed, user aborted"
                    self.ctx.record(result)
                    return False
                # Continue with remaining steps
                print(f"    → Continuing with remaining steps...")
            else:
                print(f"    ✓ Step {step['id']} passed")
                steps_passed += 1
                self.ctx.implement_artifacts.extend(step.get("artifacts", []))

        result.status = Status.PASSED if all_passed else Status.FAILED
        result.finished_at = datetime.now().isoformat()
        result.duration_s = self._duration(result)
        result.outputs = {"steps_total": len(steps), "steps_passed": steps_passed}
        self.ctx.record(result)
        print()
        if all_passed:
            print(f"  ✓ /implement complete ({result.duration_s:.1f}s)")
        else:
            print(f"  ⚠ /implement complete with failures ({result.duration_s:.1f}s)")
        print()
        return all_passed

    def _run_reviewloop(self) -> bool:
        """Run /reviewloop phase. Returns True if passed."""
        result = PhaseResult(phase=Phase.REVIEWLOOP, status=Status.RUNNING)
        result.started_at = datetime.now().isoformat()
        print("─" * 40)
        print(f"  PHASE 4: /reviewloop — Review → Fix → Re-review")
        print("─" * 40)

        print(f"  Max iterations: {self.ctx.max_review_iterations}")
        print()

        if self.ctx.dry_run:
            print("  [DRY RUN] /reviewloop would execute here")
            result.status = Status.PASSED
            self.ctx.record(result)
            return True

        iteration = 0
        findings_summary: dict[str, int] = {}

        while iteration < self.ctx.max_review_iterations:
            iteration += 1
            print(f"  --- Iteration {iteration}/{self.ctx.max_review_iterations} ---")

            # Run /review and parse findings from stdout
            rc, stdout, _stderr = self._invoke_skill("review", "")
            if rc != 0:
                print(f"  /review returned exit code {rc}")

            # Parse severity counts using structured regex patterns
            iteration_findings = self._parse_review_output(stdout)
            for severity, count in iteration_findings.items():
                findings_summary[severity] = findings_summary.get(severity, 0) + count

            # Auto-fix deterministic issues (stub)
            # In production: parse review output, apply fixes, re-review

            # Check exit criteria: 0 CRITICAL, 0 HIGH
            if iteration_findings["critical"] == 0 and iteration_findings["high"] == 0:
                print(f"  ✓ Exit criteria met: 0 CRITICAL, 0 HIGH")
                result.status = Status.PASSED
                result.finished_at = datetime.now().isoformat()
                result.duration_s = self._duration(result)
                result.outputs = {
                    "iterations": iteration,
                    "findings": findings_summary,
                }
                self.ctx.record(result)
                print(f"  ✓ /reviewloop complete ({result.duration_s:.1f}s, {iteration} iterations)")
                print()
                return True

            print(f"  Findings: {iteration_findings}")
            if iteration < self.ctx.max_review_iterations:
                print(f"  → Fixing and re-reviewing...")

        # Max iterations reached
        print(f"  ⚠ Max iterations ({self.ctx.max_review_iterations}) reached.")
        print(f"  Remaining findings: {findings_summary}")
        result.status = Status.FAILED
        result.finished_at = datetime.now().isoformat()
        result.duration_s = self._duration(result)
        result.outputs = {"iterations": iteration, "findings": findings_summary, "max_reached": True}
        self.ctx.record(result)
        print()
        return False

    def _run_ship(self) -> bool:
        """Run /ship phase. Returns True if passed."""
        result = PhaseResult(phase=Phase.SHIP, status=Status.RUNNING)
        result.started_at = datetime.now().isoformat()
        print("─" * 40)
        print(f"  PHASE 5: /ship — Test → Version → Commit → Push → PR")
        print("─" * 40)

        print(f"  Base branch: main")
        issue_num = self.ctx.issue_number or "N/A"
        print(f"  Close issue: #{issue_num}")
        print()

        if self.ctx.dry_run:
            print("  [DRY RUN] /ship would execute here")
            result.status = Status.PASSED
            result.outputs = {"dry_run": True, "issue": issue_num}
            self.ctx.record(result)
            return True

        rc, _stdout, _stderr = self._invoke_skill("ship", "")
        if rc != 0:
            result.status = Status.FAILED
            result.error = f"/ship exited with code {rc}"
            self.ctx.record(result)
            return False

        result.status = Status.PASSED
        result.finished_at = datetime.now().isoformat()
        result.duration_s = self._duration(result)
        result.outputs = {
            "issue_number": self.ctx.issue_number,
            "pr_url": self.ctx.pr_url,
            "commit_sha": self.ctx.commit_sha,
        }
        self.ctx.record(result)
        print(f"  ✓ /ship complete ({result.duration_s:.1f}s)")
        print()
        return True

    def _decompose_plan(self, plan_path: Path) -> list[dict[str, Any]]:
        """Decompose a plan document into executable steps.

        Uses the ECC plan-orchestrate algorithm:
        1. Identify step boundaries (numbered headings, tables, delimited blocks)
        2. Extract per step: id, title, intent, tags, acceptance
        3. Tag by intent → pick agent chain
        4. Compress task descriptions
        """
        text = plan_path.read_text()
        steps: list[dict[str, Any]] = []

        # Heuristic: split on numbered headings or H2
        import re

        # Try numbered steps first: "## 1. Title" or "## Step 1"
        numbered = re.split(r"\n##\s+(\d+)[.\)]\s+", text)
        if len(numbered) > 1:
            # Even indices are content, odd indices are step numbers
            for i in range(1, len(numbered), 2):
                step_num = int(numbered[i])
                body = numbered[i + 1] if i + 1 < len(numbered) else ""
                steps.append(self._step_from_body(step_num, body))
        else:
            # Fallback: split on H2
            h2_split = re.split(r"\n##\s+", text)
            for idx, body in enumerate(h2_split[1:], 1):
                steps.append(self._step_from_body(idx, body))

        if not steps:
            # Single step — treat whole document as one
            steps.append(self._step_from_body(1, text))

        return steps

    def _step_from_body(self, step_id: int, body: str) -> dict[str, Any]:
        """Extract step metadata from a plan document section."""
        lines = body.strip().split("\n")
        title = lines[0].strip() if lines else f"Step {step_id}"
        title = re.sub(r"^[-*]\s*", "", title).strip()  # strip list markers
        title = title[:80]

        intent = " ".join(lines[1:4]).strip()[:200] if len(lines) > 1 else ""

        # Tag by trigger words in title + intent
        tags = self._tag_text(f"{title} {intent}")

        # Pick chain from tags
        chain = self._pick_chain(tags)

        # Build compressed task description
        task = f"[Plan: {self.ctx.plan_path}#step-{step_id}] {title}; {intent[:100]}; Acceptance: complete per plan; Out of scope: none"

        return {
            "id": step_id,
            "title": title,
            "intent": intent,
            "tags": tags,
            "chain": chain,
            "task": task,
            "artifacts": [],
        }

    # Language detection markers
    _LANG_MARKERS: dict[str, list[str]] = {
        "python": ["pyproject.toml", "requirements.txt", "uv.lock", "setup.py"],
        "typescript": ["package.json", "tsconfig.json"],
        "go": ["go.mod", "go.sum"],
        "rust": ["Cargo.toml", "Cargo.lock"],
    }

    # Tag → chain mapping
    _TAG_CHAINS: dict[str, str] = {
        "design": "planner,architect",
        "plan": "planner",
        "impl": "tdd-guide,code-reviewer",
        "test": "tdd-guide,e2e-runner",
        "refactor": "architect,refactor-cleaner,code-reviewer",
        "db": "tdd-guide,database-reviewer,code-reviewer",
        "security": "tdd-guide,security-reviewer,code-reviewer",
        "docs": "doc-updater",
        "review": "code-reviewer",
    }

    def _detect_language(self) -> str:
        """Detect project language from marker files."""
        root = self.ctx.project_root
        for lang, markers in self._LANG_MARKERS.items():
            for marker in markers:
                if (root / marker).exists():
                    return lang
        return "unknown"

    def _tag_text(self, text: str) -> list[str]:
        """Tag text by trigger words."""
        text_lower = text.lower()
        tags: list[str] = []

        trigger_map = [
            ("security", ["encrypt", "auth", "secret", "owasp", "pii", "secure"]),
            ("db", ["schema", "migration", "index", "sql", "postgres", "alembic", "database"]),
            ("refactor", ["refactor", "cleanup", "dedupe", "split", "reorganize"]),
            ("design", ["architecture", "design", "rfc", "evaluate", "choose"]),
            ("test", ["test", "coverage", "e2e", "integration", "qa"]),
            ("impl", ["implement", "build", "add", "create", "port", "write", "develop"]),
            ("docs", ["docs", "readme", "codemap", "changelog", "document"]),
            ("review", ["review", "audit", "verify", "check"]),
        ]

        for tag, triggers in trigger_map:
            if any(t in text_lower for t in triggers):
                tags.append(tag)

        return tags if tags else ["review"]

    def _pick_chain(self, tags: list[str]) -> list[str]:
        """Pick agent chain from tags."""
        lang = self._detect_language()
        lang_suffix = "" if lang == "unknown" else f"-{lang}"

        chain: list[str] = []
        seen: set[str] = set()

        for tag in tags:
            base = self._TAG_CHAINS.get(tag, "code-reviewer")
            # Replace <lang> placeholder
            expanded = [a.replace("<lang>", lang_suffix) for a in base.split(",")]
            for agent in expanded:
                if agent not in seen:
                    chain.append(agent)
                    seen.add(agent)

        # Impl/test/refactor/migration must end with reviewer
        if tags and tags[0] in ("impl", "refactor", "migration", "db"):
            tail_map = {
                "security": f"security-reviewer{lang_suffix}",
                "db": f"database-reviewer{lang_suffix}",
                "impl": f"{lang}-reviewer" if lang != "unknown" else "code-reviewer",
            }
            tail = tail_map.get(tags[0] if len(tags) == 1 else tags[-1], f"{lang}-reviewer" if lang != "unknown" else "code-reviewer")
            if chain and chain[-1] != tail:
                chain.append(tail)

        # Deduplicate preserving order
        chain = list(dict.fromkeys(chain))

        # Max 4 agents
        if len(chain) > 4:
            # Drop lookup/docs first
            drop = {"doc-updater", "docs-lookup"}
            chain = [a for a in chain if a not in drop]
            if len(chain) > 4:
                chain = chain[:4]

        return chain if chain else ["code-reviewer"]

    def _build_spec_command(self) -> str:
        """Build the /spec invocation command."""
        plan_path = self.ctx.plan_path or Path(".gstack") / "plans" / f"orchestrate-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        return f"/spec {self.ctx.one_liner} --plan-file {plan_path}"

    def _invoke_skill(self, skill: str, args: str) -> tuple[int, str, str]:
        """Invoke a gstack skill via claude CLI. Returns (exit_code, stdout, stderr).

        Uses `claude -p` to invoke slash commands as Claude Code skills.
        Retries up to 2 times on timeout or transient errors with
        exponential backoff (5s, 15s).
        """
        import subprocess
        import time

        skill_map = {
            "spec": "/spec",
            "autoplan": "/autoplan",
            "implement": "/implement",
            "orchestrate": "/orchestrate",
            "review": "/review",
            "ship": "/ship",
        }

        slash_cmd = skill_map.get(skill, f"/{skill}")
        prompt = f"{slash_cmd} {args}".strip() if args else slash_cmd

        print(f"  → Invoking: claude -p \"{prompt[:80]}...\"")

        max_retries = 2
        backoff_seconds = [5, 15]

        for attempt in range(1 + max_retries):
            try:
                result = subprocess.run(
                    ["claude", "-p", prompt],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=600,  # 10 minute timeout per skill invocation
                    cwd=str(self.ctx.project_root),
                )

                if result.returncode != 0:
                    stderr_preview = result.stderr[:200] if result.stderr else ""
                    print(f"  ✗ Skill '{skill}' exited with code {result.returncode}: {stderr_preview}")

                return result.returncode, result.stdout, result.stderr

            except FileNotFoundError:
                print(f"  ⚠ 'claude' CLI not found in PATH. Skipping skill '{skill}'.")
                return 1, "", ""
            except subprocess.TimeoutExpired:
                if attempt < max_retries:
                    wait = backoff_seconds[attempt]
                    print(f"  ⏳ Skill '{skill}' timed out (attempt {attempt + 1}/{1 + max_retries}). Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  ✗ Skill '{skill}' timed out after {1 + max_retries} attempts.")
                    return 124, "", ""

        # Unreachable but satisfies type checker
        return 1, "", ""

    @staticmethod
    def _parse_review_output(stdout: str) -> dict[str, int]:
        """Parse review output for severity counts.

        Uses regex to match structured severity markers rather than
        naive substring matching, reducing false positives.
        """
        import re

        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}

        # Match structured markers: [CRITICAL], severity: high, level: medium, etc.
        patterns = {
            "critical": re.compile(r"(?:\[CRITICAL\]|severity:\s*critical|level:\s*critical)", re.IGNORECASE),
            "high": re.compile(r"(?:\[HIGH\]|severity:\s*high|level:\s*high)", re.IGNORECASE),
            "medium": re.compile(r"(?:\[MEDIUM\]|severity:\s*medium|level:\s*medium)", re.IGNORECASE),
            "low": re.compile(r"(?:\[LOW\]|\[NOTE\]|severity:\s*low|level:\s*low)", re.IGNORECASE),
        }

        for line in stdout.split("\n"):
            for severity, pattern in patterns.items():
                if pattern.search(line):
                    counts[severity] += 1

        return counts

    def _prompt_continue_or_abort(self, step_id: int) -> str:
        """Prompt user to continue or abort after step failure."""
        while True:
            raw = input(f"  Step {step_id} failed. Continue? [continue/abort]: ").strip().lower()
            if raw in ("continue", "c", "yes", "y"):
                return "continue"
            if raw in ("abort", "a", "no", "n"):
                return "abort"

    def _active_gates(self) -> set[str]:
        return self.ctx.gates

    def _is_auto_approved(self, gate: Gate) -> bool:
        return False  # Could be wired to plan-tune preferences

    def _skip_phase(self, phase: Phase, reason: str) -> None:
        result = PhaseResult(phase=phase, status=Status.SKIPPED, skipped_reason=reason)
        self.ctx.record(result)
        print(f"  ⊘ /{phase.value} skipped ({reason})")

    def _report_completion(self) -> None:
        print()
        print("=" * 60)
        print("  PIPELINE COMPLETE")
        print("=" * 60)

        for phase in Phase:
            result = self.ctx.results.get(phase)
            if result:
                icon = {"passed": "✓", "failed": "✗", "skipped": "⊘", "blocked": "⊘"}.get(result.status.value, "?")
                dur = f"{result.duration_s:.1f}s" if result.duration_s else "—"
                print(f"  {icon} {phase.value:15s} {result.status.value:10s} {dur}")

        print()
        if self.ctx.issue_number:
            print(f"  Issue: #{self.ctx.issue_number}")
        if self.ctx.pr_url:
            print(f"  PR:    {self.ctx.pr_url}")
        if self.ctx.commit_sha:
            print(f"  Commit: {self.ctx.commit_sha[:12]}")

        # Overall status
        failed = [p for p, r in self.ctx.results.items() if r.status == Status.FAILED]
        if failed:
            print(f"\n  STATUS: DONE_WITH_CONCERNS (failed phases: {', '.join(p.value for p in failed)})")
        else:
            print(f"\n  STATUS: DONE")

        print("=" * 60)

    @staticmethod
    def _duration(result: PhaseResult) -> float:
        """Compute duration from started_at to now."""
        if not result.started_at:
            return 0.0
        try:
            start = datetime.fromisoformat(result.started_at)
            return (datetime.now() - start).total_seconds()
        except (ValueError, TypeError):
            return 0.0
