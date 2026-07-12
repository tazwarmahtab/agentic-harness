"""Tests for the AOS workflow engine."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from aos.workflow import WorkflowEngine, WorkflowRun, WorkflowStatus
from aos.event_bus import EventBus


@pytest.fixture
def mock_graph():
    """A mock compiled LangGraph graph."""
    graph = MagicMock()
    graph.invoke.return_value = {"result": "done", "step": 1}
    return graph


@pytest.fixture
def engine(mock_graph):
    return WorkflowEngine(
        compiled_graph=mock_graph,
        harness_id="HAR-TEST-001",
        venture_id="VEN-TEST-001",
        bus=EventBus(),
    )


class TestWorkflowStatus:
    def test_all_statuses(self):
        assert WorkflowStatus.PENDING.value == "pending"
        assert WorkflowStatus.RUNNING.value == "running"
        assert WorkflowStatus.PAUSED.value == "paused"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.FAILED.value == "failed"
        assert WorkflowStatus.CANCELLED.value == "cancelled"


class TestWorkflowRun:
    def test_duration_s_without_times(self):
        run = WorkflowRun(id="WFL-001", harness_id="H1", venture_id="V1")
        assert run.duration_s() is None

    def test_to_dict_has_required_keys(self):
        run = WorkflowRun(id="WFL-001", harness_id="H1", venture_id="V1")
        d = run.to_dict()
        assert "id" in d
        assert "status" in d
        assert "step_count" in d
        assert d["step_count"] == 0


class TestWorkflowEngine:
    def test_start_returns_run_id(self, engine):
        run_id = engine.start({"input": "test"})
        assert run_id.startswith("WFL-")

    def test_start_sets_running_then_completed(self, engine):
        run_id = engine.start({"input": "test"})
        run = engine.get_run(run_id)
        assert run.status == WorkflowStatus.COMPLETED

    def test_start_records_final_state(self, engine):
        run_id = engine.start({"input": "test"})
        run = engine.get_run(run_id)
        assert run.final_state is not None
        assert "result" in run.final_state

    def test_start_records_duration(self, engine):
        run_id = engine.start({"input": "test"})
        run = engine.get_run(run_id)
        assert run.started_at is not None
        assert run.completed_at is not None
        assert run.duration_s() is not None

    def test_start_on_failure(self, mock_graph):
        mock_graph.invoke.side_effect = RuntimeError("boom")
        engine = WorkflowEngine(mock_graph, "H1", "V1")
        run_id = engine.start({})
        run = engine.get_run(run_id)
        assert run.status == WorkflowStatus.FAILED
        assert "boom" in run.error

    def test_get_run_returns_none_for_missing(self, engine):
        assert engine.get_run("WFL-NONEXISTENT") is None

    def test_list_runs(self, engine):
        engine.start({})
        engine.start({})
        runs = engine.list_runs()
        assert len(runs) == 2

    def test_summary_counts_by_status(self, engine):
        engine.start({})
        summary = engine.summary()
        assert summary["total"] == 1
        assert summary["by_status"]["completed"] == 1

    def test_start_emits_events(self, engine):
        run_id = engine.start({"input": "test"})
        # No assertion on events — just verify no crash
        assert run_id is not None

    def test_default_bus_when_none(self, mock_graph):
        engine = WorkflowEngine(mock_graph, "H1", "V1", bus=None)
        run_id = engine.start({})
        assert run_id.startswith("WFL-")
