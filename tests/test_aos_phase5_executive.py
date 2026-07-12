"""Phase 5: Executive Harness live dry-run validation.

Validates that all new AOS platform components wire together correctly
against the Executive Harness manifests — without making real LLM calls.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aos.registry import load_registry, Registry
from aos.event_bus import EventBus, AOSEvent, EventType
from aos.entity_index import EntityIndex, EntityType, Entity
from aos.health import check_system_health
from aos.workflow import WorkflowEngine, WorkflowStatus


EXEC_DIR = Path("aos/harnesses/executive")
NETSO_PATH = Path("aos/ventures/netso/venture.yml")


@pytest.fixture
def exec_registry() -> Registry:
    vp = NETSO_PATH if NETSO_PATH.exists() else None
    return load_registry(EXEC_DIR, vp)


class TestEventBus:
    def test_emit_and_log(self):
        bus = EventBus()
        ev = AOSEvent(
            type=EventType.TASK_CREATED,
            source_harness="HAR-EXEC-001",
            source_agent="AGT-EXEC-DISPATCH",
            payload={"task": "investor_deck"},
        )
        bus.emit(ev)
        assert len(bus.log()) == 1
        assert bus.log()[0].type == EventType.TASK_CREATED

    def test_handler_called(self):
        bus = EventBus()
        received = []
        bus.on(EventType.TASK_CREATED, received.append)
        bus.emit(AOSEvent(
            type=EventType.TASK_CREATED,
            source_harness="HAR-EXEC-001",
            source_agent="AGT-EXEC-PLAN",
        ))
        assert len(received) == 1

    def test_handler_error_does_not_crash_bus(self):
        bus = EventBus()
        def bad_handler(_): raise RuntimeError("boom")
        bus.on(EventType.ALERT_TRIGGERED, bad_handler)
        bus.emit(AOSEvent(
            type=EventType.ALERT_TRIGGERED,
            source_harness="HAR-EXEC-001",
            source_agent="AGT-EXEC-RSK",
        ))
        assert len(bus.log()) == 1  # event still logged

    def test_summary_counts(self):
        bus = EventBus()
        for _ in range(3):
            bus.emit(AOSEvent(type=EventType.TASK_CREATED,
                              source_harness="H", source_agent="A"))
        bus.emit(AOSEvent(type=EventType.APPROVAL_REQUESTED,
                          source_harness="H", source_agent="A"))
        s = bus.summary()
        assert s[EventType.TASK_CREATED] == 3
        assert s[EventType.APPROVAL_REQUESTED] == 1

    def test_log_for_harness_filters(self):
        bus = EventBus()
        bus.emit(AOSEvent(type=EventType.TASK_CREATED,
                          source_harness="HAR-EXEC-001", source_agent="A"))
        bus.emit(AOSEvent(type=EventType.TASK_CREATED,
                          source_harness="HAR-FIN-001", source_agent="B"))
        assert len(bus.log_for_harness("HAR-EXEC-001")) == 1


class TestEntityIndex:
    def test_register_and_get(self):
        idx = EntityIndex()
        e = Entity.create(EntityType.PROJECT, "Lhoist 450kW", "VEN-NETSO-001",
                          created_by="AGT-EXEC-COO")
        idx.register(e)
        assert idx.get(e.id) is not None
        assert idx.get(e.id).name == "Lhoist 450kW"

    def test_list_by_type(self):
        idx = EntityIndex()
        for name in ("Alpha", "Beta", "Gamma"):
            idx.register(Entity.create(EntityType.CUSTOMER, name, "VEN-NETSO-001"))
        idx.register(Entity.create(EntityType.PROJECT, "P1", "VEN-NETSO-001"))
        customers = idx.list_by_type(EntityType.CUSTOMER)
        assert len(customers) == 3

    def test_find_by_name(self):
        idx = EntityIndex()
        idx.register(Entity.create(EntityType.CUSTOMER, "Lhoist BD", "VEN-NETSO-001"))
        idx.register(Entity.create(EntityType.CUSTOMER, "Square Food", "VEN-NETSO-001"))
        results = idx.find("lhoist")
        assert len(results) == 1
        assert results[0].name == "Lhoist BD"

    def test_summary(self):
        idx = EntityIndex()
        idx.register(Entity.create(EntityType.HARNESS, "Executive", "VEN-NETSO-001"))
        idx.register(Entity.create(EntityType.AGENT, "CFO", "VEN-NETSO-001"))
        idx.register(Entity.create(EntityType.AGENT, "COO", "VEN-NETSO-001"))
        s = idx.summary()
        assert s.get("harness") == 1
        assert s.get("agent") == 2


class TestSystemHealth:
    def test_health_with_no_providers(self, monkeypatch):
        for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
                    "AOS_LLM_BASE_URL", "TAZOS_LLM_BASE_URL", "NVIDIA_NIM_API_KEY"):
            monkeypatch.delenv(var, raising=False)
        h = check_system_health()
        assert h.status in ("ok", "degraded", "down")  # graceful even with no providers

    def test_health_with_anthropic(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        h = check_system_health()
        llm = next(c for c in h.components if c.name == "llm_provider")
        assert llm.status == "ok"
        assert "anthropic" in llm.details

    def test_health_to_dict(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        h = check_system_health()
        d = h.to_dict()
        assert "status" in d
        assert "components" in d
        assert isinstance(d["components"], list)


class TestWorkflowEngine:
    def test_dry_run_completes(self):
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"summary": "dry run done", "handoffs": []}

        engine = WorkflowEngine(mock_graph, "HAR-EXEC-001")
        run_id = engine.start({"reviewed_inputs": {}})

        run = engine.get_run(run_id)
        assert run is not None
        assert run.status == WorkflowStatus.COMPLETED
        assert run.duration_s() is not None

    def test_failed_run_captured(self):
        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = RuntimeError("LLM timeout")

        engine = WorkflowEngine(mock_graph, "HAR-EXEC-001")
        run_id = engine.start({})

        run = engine.get_run(run_id)
        assert run.status == WorkflowStatus.FAILED
        assert "LLM timeout" in run.error

    def test_events_emitted_on_run(self):
        bus = EventBus()
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {}

        engine = WorkflowEngine(mock_graph, "HAR-EXEC-001", bus=bus)
        engine.start({})

        types = [e.type for e in bus.log()]
        assert EventType.HARNESS_STARTED in types
        assert EventType.CYCLE_COMPLETED in types

    def test_summary(self):
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {}

        engine = WorkflowEngine(mock_graph, "HAR-EXEC-001")
        engine.start({})
        engine.start({})

        s = engine.summary()
        assert s["total"] == 2
        assert s["by_status"]["completed"] == 2


class TestRegistryLiveStatus:
    def test_live_status_returns_all_harnesses(self, exec_registry):
        status = exec_registry.live_status()
        assert len(status) >= 1
        for hid, info in status.items():
            assert "name" in info
            assert "agents" in info
            assert info["agents"] > 0

    def test_live_status_executive_fields(self, exec_registry):
        status = exec_registry.live_status()
        exec_status = status.get("HAR-EXEC-001")
        if exec_status:
            assert exec_status["has_memory"] is not None
            assert exec_status["has_tools"] is not None
