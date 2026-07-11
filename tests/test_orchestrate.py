"""Tests for the orchestrate pipeline and gate manager."""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from aos.orchestrate.gates import (
    ApprovalDecision,
    Gate,
    GateDecision,
    GateManager,
    GateResult,
)
from aos.orchestrate.pipeline import (
    OrchestratePipeline,
    PhaseResult,
    PipelineContext,
    Phase,
    Status,
)


# ── GateManager tests ────────────────────────────────────────────────


class TestGateManager:
    """Unit tests for the human-in-the-loop gate manager."""

    def test_auto_approve_returns_approved(self):
        """auto_approve=True should return APPROVED without touching queue."""
        gm = GateManager()
        result = gm.check(Gate.SPEC, "test", {}, auto_approve=True)

        assert result.decision == GateDecision.APPROVED
        assert result.gate == Gate.SPEC
        assert result.item_id is None

    def test_first_check_creates_pending_item(self):
        """First call for a gate should create an approval item."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.jsonl"
            gm = GateManager(persistence_path=queue_path)

            result = gm.check(Gate.SPEC, "Approve spec", {"issue": "42"})

            assert result.decision == GateDecision.SKIPPED
            assert result.item_id is not None

            # Verify item was persisted
            lines = queue_path.read_text().strip().split("\n")
            assert len(lines) == 1
            item = json.loads(lines[0])
            assert item["action"].startswith("[spec gate]")
            assert item["status"] == "pending"

    def test_rejected_gate_returns_rejected(self):
        """When item is rejected, resolve_pending returns REJECTED."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.jsonl"
            gm = GateManager(persistence_path=queue_path)

            result = gm.check(Gate.SPEC, "Reject me", {})
            assert result.item_id

            gm._queue.decide(result.item_id, ApprovalDecision.REJECT)

            resolved = gm.resolve_pending(Gate.SPEC)
            assert resolved is not None
            assert resolved.decision == GateDecision.REJECTED

    def test_is_approved_true_after_approve(self):
        """is_approved returns True after a manual approve."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.jsonl"
            gm = GateManager(persistence_path=queue_path)

            result = gm.check(Gate.PLAN, "Approve plan", {})
            gm._queue.decide(result.item_id, ApprovalDecision.APPROVE)

            assert gm.is_approved(Gate.PLAN) is True
            assert gm.is_rejected(Gate.PLAN) is False

    def test_is_rejected_true_after_reject(self):
        """is_rejected returns True after a manual reject."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.jsonl"
            gm = GateManager(persistence_path=queue_path)

            result = gm.check(Gate.REVIEW, "Reject review", {})
            gm._queue.decide(result.item_id, ApprovalDecision.REJECT)

            assert gm.is_rejected(Gate.REVIEW) is True
            assert gm.is_approved(Gate.REVIEW) is False

    def test_gates_are_independent(self):
        """Deciding on one gate should not affect another."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.jsonl"
            gm = GateManager(persistence_path=queue_path)

            spec_result = gm.check(Gate.SPEC, "spec", {})
            plan_result = gm.check(Gate.PLAN, "plan", {})

            gm._queue.decide(spec_result.item_id, ApprovalDecision.APPROVE)

            assert gm.is_approved(Gate.SPEC) is True
            assert gm.is_approved(Gate.PLAN) is False  # still pending

    def test_persistence_across_instances(self):
        """Gate state should survive GateManager reconstruction."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.jsonl"
            gm1 = GateManager(persistence_path=queue_path)
            result = gm1.check(Gate.SPEC, "persist me", {})
            gm1._queue.decide(result.item_id, ApprovalDecision.APPROVE)

            # New instance loads from disk
            gm2 = GateManager(persistence_path=queue_path)
            assert gm2.is_approved(Gate.SPEC) is True


# ── PipelineContext tests ────────────────────────────────────────────


class TestPipelineContext:
    def test_defaults(self):
        ctx = PipelineContext()
        assert ctx.skip_spec is False
        assert ctx.skip_plan is False
        assert ctx.skip_review is False
        assert ctx.gates == {"spec", "plan", "review"}
        assert ctx.max_review_iterations == 3
        assert ctx.dry_run is False

    def test_record_phase_result(self):
        ctx = PipelineContext()
        result = PhaseResult(phase=Phase.SPEC, status=Status.PASSED)
        ctx.record(result)

        assert Phase.SPEC in ctx.results
        assert ctx.results[Phase.SPEC].status == Status.PASSED
        assert ctx.results[Phase.SPEC].phase == Phase.SPEC


# ── OrchestratePipeline tests ────────────────────────────────────────


def _make_ctx(**kwargs) -> PipelineContext:
    """Create a PipelineContext with a real temp plan file that persists."""
    import tempfile

    fd, plan_path_str = tempfile.mkstemp(suffix=".md")
    with open(fd, "w") as f:
        f.write("# Test Plan\n\n## 1. Do the thing\n\nDetails.\n")
    plan_path = Path(plan_path_str)

    defaults = dict(
        one_liner="Add user auth",
        plan_path=plan_path,
        skip_spec=True,
        skip_plan=True,
        skip_review=True,
        gates=set(),
        project_root=Path("/tmp"),
        dry_run=True,
        max_review_iterations=2,
    )
    defaults.update(kwargs)
    return PipelineContext(**defaults)


class TestOrchestratePipeline:
    """Integration-style tests for the pipeline coordinator."""

    def test_dry_run_all_non_skipped_phases_pass(self):
        """dry_run=True should pass all non-skipped phases."""
        mock_gates = MagicMock()
        ctx = _make_ctx(dry_run=True, gates=set())
        pipeline = OrchestratePipeline(ctx, mock_gates)

        rc = pipeline.run()
        assert rc == 0

        # SPEC is SKIPPED because default _make_ctx sets skip_spec=True
        assert ctx.results[Phase.SPEC].status == Status.SKIPPED
        # AUTOPLAN is SKIPPED because skip_plan=True
        assert ctx.results[Phase.AUTOPLAN].status == Status.SKIPPED
        # REVIEWLOOP is SKIPPED because skip_review=True
        assert ctx.results[Phase.REVIEWLOOP].status == Status.SKIPPED
        # IMPLEMENT and SHIP should PASS
        assert ctx.results[Phase.IMPLEMENT].status == Status.PASSED
        assert ctx.results[Phase.SHIP].status == Status.PASSED

    def test_gate_rejection_stops_pipeline(self):
        """When a gate rejects, pipeline should stop."""
        mock_gates = MagicMock()
        mock_gates.check.return_value = GateResult(
            gate=Gate.SPEC, decision=GateDecision.REJECTED
        )
        mock_gates._active_gates.return_value = {Gate.SPEC}
        mock_gates._is_auto_approved.return_value = False

        # Need spec enabled but since skip_spec=True, the gate check
        # only runs if the phase actually ran. Let's run with skip_spec=False.
        ctx = _make_ctx(skip_spec=False, gates={"spec"}, one_liner="test")
        pipeline = OrchestratePipeline(ctx, mock_gates)

        rc = pipeline.run()
        assert rc == 1  # stopped at spec gate

    def test_skip_spec_flags_skipped_phase(self):
        """When skip_spec=True, spec phase is SKIPPED in results."""
        mock_gates = MagicMock()
        ctx = _make_ctx(skip_spec=True, gates=set())
        pipeline = OrchestratePipeline(ctx, mock_gates)

        rc = pipeline.run()
        assert rc == 0
        assert ctx.results[Phase.SPEC].status == Status.SKIPPED

    def test_skip_plan_flags_skipped_phase(self):
        """When skip_plan=True, autoplan phase is SKIPPED."""
        mock_gates = MagicMock()
        ctx = _make_ctx(skip_spec=True, skip_plan=True, gates=set())
        pipeline = OrchestratePipeline(ctx, mock_gates)

        rc = pipeline.run()
        assert rc == 0
        assert ctx.results[Phase.AUTOPLAN].status == Status.SKIPPED

    def test_completion_report_printed(self, capsys=None):
        """Pipeline should record all phases and return 0."""
        mock_gates = MagicMock()
        ctx = _make_ctx(skip_spec=True, skip_plan=True, skip_review=True, gates=set())
        pipeline = OrchestratePipeline(ctx, mock_gates)

        rc = pipeline.run()
        assert rc == 0
        assert Phase.SHIP in ctx.results
        assert ctx.results[Phase.SHIP].status == Status.PASSED


# ── Step decomposition tests ─────────────────────────────────────────


class TestStepDecomposition:
    """Tests for plan document step decomposition."""

    def test_decompose_numbered_steps(self):
        """Numbered headings should split into 3 steps."""
        plan_content = """\
# Test Plan

## 1. Create User model

Implement the User model with name and email fields.

## 2. Add auth endpoint

Create POST /auth/login with JWT validation.

## 3. Write tests

Add unit tests for the auth flow.
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            ctx = PipelineContext(plan_path=plan_path, project_root=Path("/tmp"))
            pipeline = OrchestratePipeline(ctx, MagicMock())
            steps = pipeline._decompose_plan(plan_path)

            assert len(steps) == 3
            assert steps[0]["id"] == 1
            assert "User model" in steps[0]["title"]
            assert steps[1]["id"] == 2
            assert "auth" in steps[1]["title"].lower()
        finally:
            plan_path.unlink()

    def test_decompose_empty_document(self):
        """Empty-ish document should produce at least one step."""
        plan_content = "# Empty Plan\n\nNo steps here."
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write(plan_content)
            f.flush()
            plan_path = Path(f.name)

        try:
            ctx = PipelineContext(plan_path=plan_path, project_root=Path("/tmp"))
            pipeline = OrchestratePipeline(ctx, MagicMock())
            steps = pipeline._decompose_plan(plan_path)

            assert len(steps) >= 1
        finally:
            plan_path.unlink()

    def test_tagging_impl_step(self):
        """Steps with 'implement' should get impl tag."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        tags = pipeline._tag_text("Implement user authentication endpoint")
        assert "impl" in tags

    def test_tagging_security_step(self):
        """Steps with 'auth' should get security tag."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        tags = pipeline._tag_text("Add OAuth2 authentication for API")
        assert "security" in tags

    def test_tagging_db_step(self):
        """Steps with 'migration' should get db tag."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        tags = pipeline._tag_text("Create database migration for users table")
        assert "db" in tags

    def test_tagging_test_step(self):
        """Steps with 'test' should get test tag."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        tags = pipeline._tag_text("Write integration tests for auth flow")
        assert "test" in tags

    def test_tagging_multiple_tags(self):
        """Steps can have multiple tags."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        tags = pipeline._tag_text(
            "Implement encrypted user authentication with database migration"
        )
        assert "impl" in tags
        assert "security" in tags
        assert "db" in tags

    def test_tagging_refactor_step(self):
        """Steps with 'refactor' should get refactor tag."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        tags = pipeline._tag_text("Refactor the user service into smaller modules")
        assert "refactor" in tags

    def test_chain_for_impl_security(self):
        """impl+security should include tdd-guide and security-reviewer."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        chain = pipeline._pick_chain(["impl", "security"])
        assert "tdd-guide" in chain
        assert "security-reviewer" in chain

    def test_chain_for_impl_db(self):
        """impl+db should include tdd-guide and database-reviewer."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        chain = pipeline._pick_chain(["impl", "db"])
        assert "tdd-guide" in chain
        assert "database-reviewer" in chain

    def test_chain_max_four_agents(self):
        """Chain length should be capped at 4 regardless of tags."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        chain = pipeline._pick_chain(["impl", "security", "db", "test", "refactor"])
        assert len(chain) <= 4

    def test_chain_dedup_preserves_order(self):
        """Duplicate agents should be removed, order preserved."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        chain = pipeline._pick_chain(["impl", "security"])
        # Should not have duplicates
        assert len(chain) == len(set(chain))

    def test_step_task_description_format(self):
        """Task descriptions should start with [Plan:...]."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())
        step = pipeline._step_from_body(1, "Test step\n\nDo the thing.")

        assert step["task"].startswith("[Plan:")
        assert "step-1" in step["task"]
        assert step["id"] == 1


# ── FIX-06: _invoke_skill + _parse_review_output tests ────────────────


class TestInvokeSkill:
    """Tests for _invoke_skill hardened subprocess invocation."""

    def test_invoke_skill_returns_three_tuple(self):
        """_invoke_skill should return (exit_code, stdout, stderr)."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "done"
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            rc, stdout, stderr = pipeline._invoke_skill("spec", "test input")

            assert rc == 0
            assert stdout == "done"
            assert stderr == ""
            mock_run.assert_called_once()
            args = mock_run.call_args
            assert args[0][0] == ["claude", "-p", "/spec test input"]

    def test_invoke_skill_handles_file_not_found(self):
        """_invoke_skill should handle missing claude CLI gracefully."""
        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        with patch("subprocess.run", side_effect=FileNotFoundError):
            rc, stdout, stderr = pipeline._invoke_skill("review", "")

            assert rc == 1
            assert stdout == ""
            assert stderr == ""

    def test_invoke_skill_handles_timeout_with_retry(self):
        """_invoke_skill should retry on timeout then return 124."""
        import subprocess as sp

        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        timeout_error = sp.TimeoutExpired(cmd=["claude"], timeout=600)

        with patch("subprocess.run", side_effect=timeout_error) as mock_run, \
             patch("time.sleep"):
            rc, stdout, stderr = pipeline._invoke_skill("review", "")

            assert rc == 124
            assert stdout == ""
            # 1 initial + 2 retries = 3 calls
            assert mock_run.call_count == 3

    def test_invoke_skill_retries_on_transient_error(self):
        """_invoke_skill should retry on timeout then succeed."""
        import subprocess as sp

        ctx = PipelineContext(project_root=Path("/tmp"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        timeout_error = sp.TimeoutExpired(cmd=["claude"], timeout=600)
        success = MagicMock(returncode=0, stdout="ok", stderr="")

        with patch("subprocess.run", side_effect=[timeout_error, success]) as mock_run, \
             patch("time.sleep"):
            rc, stdout, stderr = pipeline._invoke_skill("spec", "hello")

            assert rc == 0
            assert stdout == "ok"
            assert mock_run.call_count == 2

    def test_invoke_skill_passes_correct_cwd(self):
        """_invoke_skill should use project_root as cwd."""
        ctx = PipelineContext(project_root=Path("/workspace"))
        pipeline = OrchestratePipeline(ctx, MagicMock())

        mock_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            pipeline._invoke_skill("ship", "")

            cwd = mock_run.call_args.kwargs.get("cwd") or mock_run.call_args[1].get("cwd")
            assert cwd == "/workspace"


class TestParseReviewOutput:
    """Tests for _parse_review_output structured severity parsing."""

    def test_parse_structured_markers(self):
        """Should count [CRITICAL], [HIGH], [MEDIUM], [LOW] markers."""
        stdout = (
            "Line 1: [CRITICAL] SQL injection vulnerability found\n"
            "Line 2: [HIGH] Missing input validation\n"
            "Line 3: [MEDIUM] Inconsistent error handling\n"
            "Line 4: [LOW] Deprecated API usage\n"
            "Line 5: [NOTE] Consider adding logging\n"
        )
        counts = OrchestratePipeline._parse_review_output(stdout)

        assert counts["critical"] == 1
        assert counts["high"] == 1
        assert counts["medium"] == 1
        assert counts["low"] == 2  # [LOW] + [NOTE]

    def test_parse_severity_colon_format(self):
        """Should match severity: level and level: level formats."""
        stdout = (
            "severity: critical — no auth check\n"
            "Level: high — XSS vulnerability\n"
            "severity: medium — verbose errors\n"
        )
        counts = OrchestratePipeline._parse_review_output(stdout)

        assert counts["critical"] == 1
        assert counts["high"] == 1
        assert counts["medium"] == 1
        assert counts["low"] == 0

    def test_parse_no_false_positives(self):
        """Should not match 'critical' in prose context."""
        stdout = (
            "This is a critical review of the codebase.\n"
            "The high-level architecture looks good.\n"
            "A medium priority item was noted.\n"
        )
        counts = OrchestratePipeline._parse_review_output(stdout)

        assert counts["critical"] == 0
        assert counts["high"] == 0
        assert counts["medium"] == 0
        assert counts["low"] == 0

    def test_parse_empty_output(self):
        """Empty string should return all zeros."""
        counts = OrchestratePipeline._parse_review_output("")
        assert counts == {"critical": 0, "high": 0, "medium": 0, "low": 0}

    def test_parse_multiple_findings_per_severity(self):
        """Should count multiple findings of the same severity."""
        stdout = (
            "[CRITICAL] Finding 1\n"
            "[CRITICAL] Finding 2\n"
            "[CRITICAL] Finding 3\n"
            "[HIGH] Finding A\n"
            "[HIGH] Finding B\n"
        )
        counts = OrchestratePipeline._parse_review_output(stdout)

        assert counts["critical"] == 3
        assert counts["high"] == 2


# ── Gate blocking (wait_for_decision) tests ──────────────────────


class TestGateBlocking:
    """Tests for the wait_for_decision mechanism that blocks on pending gates."""

    def test_wait_for_decision_approve(self):
        """wait_for_decision returns APPROVED when item is decided."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.jsonl"
            gm = GateManager(persistence_path=queue_path)

            # Create a pending gate item
            result = gm.check(Gate.SPEC, "Approve spec", {})
            assert result.decision == GateDecision.SKIPPED
            assert result.item_id is not None

            # Approve it via the queue
            gm._queue.decide(result.item_id, ApprovalDecision.APPROVE)

            # wait_for_decision should immediately resolve
            resolved = gm.wait_for_decision(result.item_id, Gate.SPEC, timeout_s=5, poll_interval=0.1)
            assert resolved.decision == GateDecision.APPROVED

    def test_wait_for_decision_reject(self):
        """wait_for_decision returns REJECTED when item is rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.jsonl"
            gm = GateManager(persistence_path=queue_path)

            result = gm.check(Gate.PLAN, "Approve plan", {})
            gm._queue.decide(result.item_id, ApprovalDecision.REJECT)

            resolved = gm.wait_for_decision(result.item_id, Gate.PLAN, timeout_s=5, poll_interval=0.1)
            assert resolved.decision == GateDecision.REJECTED

    def test_wait_for_decision_timeout(self):
        """wait_for_decision returns SKIPPED on timeout if no decision made."""
        with tempfile.TemporaryDirectory() as tmp:
            queue_path = Path(tmp) / "queue.jsonl"
            gm = GateManager(persistence_path=queue_path)

            result = gm.check(Gate.REVIEW, "Approve review", {})

            # Don't decide — let it timeout
            resolved = gm.wait_for_decision(result.item_id, Gate.REVIEW, timeout_s=0.5, poll_interval=0.1)
            assert resolved.decision == GateDecision.SKIPPED

    def test_pipeline_stops_on_gate_timeout(self):
        """Pipeline returns 1 (stop) when a gate times out."""
        mock_gates = MagicMock()
        # First call returns SKIPPED (creates pending item)
        mock_gates.check.return_value = GateResult(
            gate=Gate.SPEC, decision=GateDecision.SKIPPED, item_id="GATE-001"
        )
        # wait_for_decision also times out
        mock_gates.wait_for_decision.return_value = GateResult(
            gate=Gate.SPEC, decision=GateDecision.SKIPPED, item_id="GATE-001"
        )

        ctx = _make_ctx(skip_spec=False, gates={"spec"}, one_liner="test")
        pipeline = OrchestratePipeline(ctx, mock_gates)

        rc = pipeline.run()
        assert rc == 1  # stopped at spec gate timeout
        mock_gates.wait_for_decision.assert_called_once()

    def test_pipeline_continues_on_gate_approve(self):
        """Pipeline continues when wait_for_decision returns APPROVED."""
        mock_gates = MagicMock()
        mock_gates.check.return_value = GateResult(
            gate=Gate.SPEC, decision=GateDecision.SKIPPED, item_id="GATE-002"
        )
        mock_gates.wait_for_decision.return_value = GateResult(
            gate=Gate.SPEC, decision=GateDecision.APPROVED, item_id="GATE-002"
        )

        ctx = _make_ctx(skip_spec=False, gates={"spec"}, one_liner="test")
        pipeline = OrchestratePipeline(ctx, mock_gates)

        rc = pipeline.run()
        assert rc == 0  # continued past spec gate
