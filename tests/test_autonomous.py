"""Tests for the autonomous pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from aos.orchestrate.autonomous import (
    AutonomousPipeline,
    AutonomousState,
    PhaseRecord,
    PhaseStatus,
)
from aos.orchestrate.gates import GateDecision, GateManager
from aos.approval_queue import ApprovalQueue


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPhaseStatus:
    """PhaseStatus enum values."""

    def test_all_statuses_exist(self) -> None:
        expected = {"pending", "running", "passed", "failed", "skipped", "blocked"}
        assert {s.value for s in PhaseStatus} == expected

    def test_string_enum(self) -> None:
        assert PhaseStatus.PENDING == "pending"


@pytest.mark.unit
class TestPhaseRecord:
    """PhaseRecord frozen dataclass."""

    def test_defaults(self) -> None:
        rec = PhaseRecord(phase_id="p-1", title="Test", status=PhaseStatus.PENDING)
        assert rec.phase_id == "p-1"
        assert rec.duration_s == 0.0
        assert rec.outputs == {}
        assert rec.error is None

    def test_frozen(self) -> None:
        rec = PhaseRecord(phase_id="p-1", title="T", status=PhaseStatus.PASSED)
        with pytest.raises(AttributeError):
            rec.phase_id = "p-2"  # type: ignore[misc]


@pytest.mark.unit
class TestAutonomousPipelineInstantiation:
    """Pipeline can be created with defaults."""

    def test_default_init(self) -> None:
        p = AutonomousPipeline()
        assert p.roadmap_file == "ROADMAP.md"
        assert p.dry_run is False
        assert p.auto is False
        assert p.gate_timeout_s == 300.0
        assert p.max_retries == 3

    def test_custom_init(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(
            roadmap_file="custom.md",
            dry_run=True,
            auto=True,
            project_root=tmp_path,
            gate_timeout_s=60.0,
            max_retries=5,
        )
        assert p.roadmap_file == "custom.md"
        assert p.dry_run is True
        assert p.auto is True
        assert p.project_root == tmp_path
        assert p.gate_timeout_s == 60.0
        assert p.max_retries == 5

    def test_graph_has_expected_nodes(self) -> None:
        p = AutonomousPipeline()
        node_names = set(p.graph.nodes) - {"__start__", "__end__"}
        expected = {
            "discover_phases",
            "gate_phase",
            "run_phase",
            "check_phase_result",
            "rollback_gate",
            "update_state",
            "gate_milestone",
            "audit_complete",
        }
        assert expected == node_names

    def test_custom_gate_manager(self, tmp_path: Path) -> None:
        queue = ApprovalQueue()
        gm = GateManager(queue=queue)
        p = AutonomousPipeline(project_root=tmp_path, gate_manager=gm)
        assert p.gate_manager is gm


@pytest.mark.unit
class TestAutonomousPipelineRun:
    """Pipeline executes without crashing in dry-run mode."""

    def test_dry_run_completes(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(dry_run=True, project_root=tmp_path)
        rc = p.run()
        assert rc == 0

    def test_auto_mode_completes(self, tmp_path: Path) -> None:
        # auto=True only auto-approves gates; LLM execution still requires
        # a valid registry. Use dry_run=True to skip LLM calls in tests.
        p = AutonomousPipeline(dry_run=True, auto=True, project_root=tmp_path)
        rc = p.run()
        assert rc == 0

    def test_dry_run_with_roadmap(self, tmp_path: Path) -> None:
        roadmap = tmp_path / "ROADMAP.md"
        roadmap.write_text(
            "# Roadmap\n\n## Phase 1: Setup\nSome work\n\n## Phase 2: Deploy\nMore work\n"
        )
        p = AutonomousPipeline(
            roadmap_file="ROADMAP.md",
            dry_run=True,
            project_root=tmp_path,
        )
        rc = p.run()
        assert rc == 0

    def test_missing_roadmap_still_completes(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(
            roadmap_file="NONEXISTENT.md",
            dry_run=True,
            project_root=tmp_path,
        )
        rc = p.run()
        assert rc == 0


@pytest.mark.unit
class TestAutonomousState:
    """TypedDict state shape."""

    def test_partial_state_allowed(self) -> None:
        state: AutonomousState = {"dry_run": True}
        assert state["dry_run"] is True
        assert state.get("phases") is None

    def test_auto_field(self) -> None:
        state: AutonomousState = {"auto": True}
        assert state["auto"] is True

    def test_pending_gate_item_id_field(self) -> None:
        state: AutonomousState = {"pending_gate_item_id": "APR-0001"}
        assert state["pending_gate_item_id"] == "APR-0001"

    def test_retries_field(self) -> None:
        state: AutonomousState = {"retries": 2}
        assert state["retries"] == 2

    def test_max_retries_field(self) -> None:
        state: AutonomousState = {"max_retries": 5}
        assert state["max_retries"] == 5


# ---------------------------------------------------------------------------
# Gate node tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGatePhase:
    """_gate_phase node behavior."""

    def test_auto_approved_in_dry_run(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(dry_run=True, project_root=tmp_path)
        state: AutonomousState = {
            "dry_run": True,
            "auto": False,
            "phases": [{"id": "p-1", "title": "Test", "status": "pending"}],
            "current_phase_index": 0,
        }
        result = p._gate_phase(state)
        assert result.get("pending_gate_item_id") is None
        assert "error" not in result

    def test_auto_approved_in_auto_mode(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(dry_run=False, auto=True, project_root=tmp_path)
        state: AutonomousState = {
            "dry_run": False,
            "auto": True,
            "phases": [{"id": "p-1", "title": "Test", "status": "pending"}],
            "current_phase_index": 0,
        }
        result = p._gate_phase(state)
        assert result.get("pending_gate_item_id") is None
        assert "error" not in result

    def test_gate_rejected_returns_error(self, tmp_path: Path) -> None:
        queue = ApprovalQueue()
        gm = GateManager(queue=queue)
        p = AutonomousPipeline(
            dry_run=False, auto=False, project_root=tmp_path, gate_manager=gm,
        )
        # Pre-submit a rejected item
        from aos.orchestrate.gates import Gate
        item = queue.add(
            agent_id="test",
            action="[spec gate] Approve phase: Test",
            rationale="test",
            risk_assessment="low",
        )
        queue.decide(item.id, __import__("aos.approval_queue", fromlist=["ApprovalDecision"]).ApprovalDecision.REJECT)

        state: AutonomousState = {
            "dry_run": False,
            "auto": False,
            "phases": [{"id": "p-1", "title": "Test", "status": "pending"}],
            "current_phase_index": 0,
        }
        result = p._gate_phase(state)
        assert "error" in result

    def test_gate_no_phases_returns_empty(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(dry_run=True, project_root=tmp_path)
        state: AutonomousState = {
            "dry_run": True,
            "phases": [],
            "current_phase_index": 0,
        }
        result = p._gate_phase(state)
        assert result == {}


@pytest.mark.unit
class TestGateMilestone:
    """_gate_milestone node behavior."""

    def test_auto_approved_in_dry_run(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(dry_run=True, project_root=tmp_path)
        state: AutonomousState = {
            "dry_run": True,
            "auto": False,
            "phase_results": [
                {"phase_id": "p-1", "status": "passed"},
            ],
        }
        result = p._gate_milestone(state)
        assert "error" not in result

    def test_skipped_when_phases_failed(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(dry_run=False, project_root=tmp_path)
        state: AutonomousState = {
            "dry_run": False,
            "auto": False,
            "phase_results": [
                {"phase_id": "p-1", "status": "passed"},
                {"phase_id": "p-2", "status": "failed"},
            ],
        }
        result = p._gate_milestone(state)
        # No error, just skipped — no sign-off needed for failed milestones
        assert "error" not in result


# ---------------------------------------------------------------------------
# Phase result + rollback tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCheckPhaseResult:
    """_check_phase_result node behavior."""

    def test_passed_routes_to_update(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(dry_run=True, project_root=tmp_path)
        state: AutonomousState = {
            "phase_results": [{"phase_id": "p-1", "status": "passed"}],
        }
        result = p._check_phase_result(state)
        assert result["_next_action"] == "passed"

    def test_failed_routes_to_rollback(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(dry_run=True, project_root=tmp_path)
        state: AutonomousState = {
            "phase_results": [{"phase_id": "p-1", "status": "failed"}],
            "retries": 0,
            "max_retries": 3,
        }
        result = p._check_phase_result(state)
        assert result["_next_action"] == "failed"

    def test_no_results_routes_to_error(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(dry_run=True, project_root=tmp_path)
        state: AutonomousState = {"phase_results": []}
        result = p._check_phase_result(state)
        assert result["_next_action"] == "error"


@pytest.mark.unit
class TestRollbackGate:
    """_rollback_gate node behavior."""

    def test_auto_approved_in_dry_run(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(dry_run=True, project_root=tmp_path)
        state: AutonomousState = {
            "dry_run": True,
            "auto": False,
            "retries": 0,
            "max_retries": 3,
            "phases": [{"id": "p-1", "title": "Test", "status": "failed"}],
            "current_phase_index": 0,
        }
        result = p._rollback_gate(state)
        assert result["retries"] == 1
        assert "error" not in result

    def test_auto_approved_in_auto_mode(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(dry_run=False, auto=True, project_root=tmp_path)
        state: AutonomousState = {
            "dry_run": False,
            "auto": True,
            "retries": 1,
            "max_retries": 3,
            "phases": [{"id": "p-1", "title": "Test", "status": "failed"}],
            "current_phase_index": 0,
        }
        result = p._rollback_gate(state)
        assert result["retries"] == 2
        assert "error" not in result

    def test_max_retries_exhausted(self, tmp_path: Path) -> None:
        p = AutonomousPipeline(dry_run=True, project_root=tmp_path)
        state: AutonomousState = {
            "dry_run": True,
            "retries": 3,
            "max_retries": 3,
            "phases": [{"id": "p-1", "title": "Test", "status": "failed"}],
            "current_phase_index": 0,
        }
        result = p._rollback_gate(state)
        assert "error" in result
        assert "retries" in result["error"].lower()

    def test_rollback_rejected_returns_error(self, tmp_path: Path) -> None:
        queue = ApprovalQueue()
        gm = GateManager(queue=queue)
        p = AutonomousPipeline(
            dry_run=False, auto=False, project_root=tmp_path, gate_manager=gm,
        )
        # Pre-submit a rejected rollback item
        item = queue.add(
            agent_id="test",
            action="[doubt gate] Approve rollback: Test",
            rationale="test",
            risk_assessment="medium",
        )
        queue.decide(item.id, __import__("aos.approval_queue", fromlist=["ApprovalDecision"]).ApprovalDecision.REJECT)

        state: AutonomousState = {
            "dry_run": False,
            "auto": False,
            "retries": 0,
            "max_retries": 3,
            "phases": [{"id": "p-1", "title": "Test", "status": "failed"}],
            "current_phase_index": 0,
        }
        result = p._rollback_gate(state)
        assert "error" in result


# ---------------------------------------------------------------------------
# Edge function tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEdgeFunctions:
    """Conditional edge routing logic."""

    def test_should_continue_phases_with_more(self) -> None:
        state: AutonomousState = {
            "phases": [{"id": "p-0"}, {"id": "p-1"}],
            "current_phase_index": 0,
            "is_complete": False,
        }
        assert AutonomousPipeline._should_continue_phases(state) == "continue"

    def test_should_continue_phases_at_end(self) -> None:
        state: AutonomousState = {
            "phases": [{"id": "p-0"}],
            "current_phase_index": 1,
            "is_complete": False,
        }
        assert AutonomousPipeline._should_continue_phases(state) == "end"

    def test_should_continue_phases_complete(self) -> None:
        state: AutonomousState = {
            "phases": [{"id": "p-0"}],
            "current_phase_index": 0,
            "is_complete": True,
        }
        assert AutonomousPipeline._should_continue_phases(state) == "end"

    def test_should_continue_phases_on_error(self) -> None:
        state: AutonomousState = {
            "phases": [{"id": "p-0"}],
            "current_phase_index": 0,
            "is_complete": False,
            "error": "gate rejected",
        }
        assert AutonomousPipeline._should_continue_phases(state) == "end"

    def test_after_gate_phase_approved(self) -> None:
        state: AutonomousState = {}
        assert AutonomousPipeline._after_gate_phase(state) == "approved"

    def test_after_gate_phase_rejected(self) -> None:
        state: AutonomousState = {"error": "rejected"}
        assert AutonomousPipeline._after_gate_phase(state) == "rejected"

    def test_after_check_phase_passed(self) -> None:
        state: AutonomousState = {"_next_action": "passed"}
        assert AutonomousPipeline._after_check_phase(state) == "passed"

    def test_after_check_phase_failed(self) -> None:
        state: AutonomousState = {"_next_action": "failed"}
        assert AutonomousPipeline._after_check_phase(state) == "failed"

    def test_after_check_phase_default_error(self) -> None:
        state: AutonomousState = {}
        assert AutonomousPipeline._after_check_phase(state) == "error"

    def test_after_rollback_gate_retry(self) -> None:
        state: AutonomousState = {}
        assert AutonomousPipeline._after_rollback_gate(state) == "retry"

    def test_after_rollback_gate_stop(self) -> None:
        state: AutonomousState = {"error": "rejected"}
        assert AutonomousPipeline._after_rollback_gate(state) == "stop"

    def test_after_gate_milestone(self) -> None:
        state: AutonomousState = {}
        assert AutonomousPipeline._after_gate_milestone(state) == "approved"
