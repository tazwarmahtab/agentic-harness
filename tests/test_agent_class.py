"""Tests for AgentClass schema, loader, and registry integration."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from aos.schemas.agent_class import (
    AgentClass,
    AgentClassStatus,
    EscalationTarget,
    ReviewRequirement,
    ToolPermission,
    _AGENT_CLASS_ID_PATTERN,
)
from aos.loader import load_agent_class, detect_manifest_type
from aos.registry import HarnessBundle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_agent_class_data() -> dict:
    return {
        "id": "ACL-EXEC-001",
        "name": "Executive Planner",
        "harness": "HAR-EXECUTIVE-001",
        "role": "planner",
    }


@pytest.fixture
def full_agent_class_data() -> dict:
    return {
        "id": "ACL-EXEC-001",
        "name": "Executive Planner",
        "harness": "HAR-EXECUTIVE-001",
        "version": "1.2.0",
        "status": "deployed",
        "role": "planner",
        "description": "Plans execution cycles for the executive harness",
        "allowed_tools": [
            {"capability": "read_file", "permission": "read"},
            {"capability": "write_file", "permission": "write"},
        ],
        "allowed_memory_read": ["execution_history", "task_status"],
        "allowed_memory_write": ["plan_output"],
        "denied_actions": ["execute_shell"],
        "enforcement_rules": ["ENF-NO-SHELL-001"],
        "escalation_targets": [
            {"failure_mode": "tool_failure", "target": "AGT-EXEC-CHIEFOFSTAFF"},
        ],
        "review_requirements": [
            {"artifact_type": "plan", "reviewer": "AGT-EXEC-CFO"},
        ],
        "constraints": ["Never deploy without founder approval"],
    }


@pytest.fixture
def agent_class_yaml_file(tmp_path: Path, full_agent_class_data: dict) -> Path:
    path = tmp_path / "planner.yml"
    path.write_text(yaml.dump(full_agent_class_data))
    return path


# ---------------------------------------------------------------------------
# AgentClass schema tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAgentClassSchema:
    """AgentClass Pydantic model validation."""

    def test_minimal_creation(self, minimal_agent_class_data):
        ac = AgentClass(**minimal_agent_class_data)
        assert ac.id == "ACL-EXEC-001"
        assert ac.role == "planner"
        assert ac.status == AgentClassStatus.DRAFT
        assert ac.version == "1.0.0"
        assert ac.allowed_tools == []
        assert ac.enforcement_rules == []

    def test_full_creation(self, full_agent_class_data):
        ac = AgentClass(**full_agent_class_data)
        assert ac.status == AgentClassStatus.DEPLOYED
        assert len(ac.allowed_tools) == 2
        assert ac.allowed_tools[0].capability == "read_file"
        assert ac.denied_actions == ["execute_shell"]
        assert len(ac.escalation_targets) == 1
        assert len(ac.review_requirements) == 1

    def test_invalid_id_format(self):
        with pytest.raises(ValidationError, match="ACL-XXX-NNN"):
            AgentClass(id="BAD-ID", name="test", harness="HAR-EXEC-001", role="planner")

    def test_invalid_id_prefix(self):
        with pytest.raises(ValidationError, match="ACL-XXX-NNN"):
            AgentClass(id="AGT-EXEC-001", name="test", harness="HAR-EXEC-001", role="planner")

    def test_invalid_harness_ref(self):
        with pytest.raises(ValidationError, match="must start with HAR-"):
            AgentClass(
                id="ACL-EXEC-001",
                name="test",
                harness="NOT-HAR",
                role="planner",
            )

    def test_valid_harness_ref(self):
        ac = AgentClass(
            id="ACL-EXEC-001",
            name="test",
            harness="HAR-EXECUTIVE-001",
            role="planner",
        )
        assert ac.harness == "HAR-EXECUTIVE-001"

    def test_defaults(self):
        ac = AgentClass(id="ACL-EXEC-001", name="test", harness="HAR-X-001", role="r")
        assert ac.version == "1.0.0"
        assert ac.status == AgentClassStatus.DRAFT
        assert ac.description == ""
        assert ac.allowed_tools == []
        assert ac.allowed_memory_read == []
        assert ac.allowed_memory_write == []
        assert ac.denied_actions == []
        assert ac.enforcement_rules == []
        assert ac.escalation_targets == []
        assert ac.review_requirements == []
        assert ac.constraints == []


@pytest.mark.unit
class TestAgentClassIDPattern:
    """Regex pattern validation for ACL- prefix IDs."""

    def test_valid_patterns(self):
        assert _AGENT_CLASS_ID_PATTERN.match("ACL-EXEC-001")
        assert _AGENT_CLASS_ID_PATTERN.match("ACL-FIN-042")
        assert _AGENT_CLASS_ID_PATTERN.match("ACL-OPS-999")

    def test_invalid_patterns(self):
        assert not _AGENT_CLASS_ID_PATTERN.match("ACL-exec-001")  # lowercase
        assert not _AGENT_CLASS_ID_PATTERN.match("ACL-EXEC-1")    # <3 digits
        assert not _AGENT_CLASS_ID_PATTERN.match("ACL-EXEC-1234") # >3 digits
        assert not _AGENT_CLASS_ID_PATTERN.match("AGT-EXEC-001")  # wrong prefix
        assert not _AGENT_CLASS_ID_PATTERN.match("ACL-EXEC")      # no digits


# ---------------------------------------------------------------------------
# ToolPermission, EscalationTarget, ReviewRequirement tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSubModels:

    def test_tool_permission(self):
        tp = ToolPermission(capability="read_file", permission="read")
        assert tp.capability == "read_file"
        assert tp.permission == "read"

    def test_escalation_target(self):
        et = EscalationTarget(failure_mode="tool_failure", target="AGT-CHIEF")
        assert et.failure_mode == "tool_failure"
        assert et.target == "AGT-CHIEF"

    def test_review_requirement(self):
        rr = ReviewRequirement(artifact_type="plan", reviewer="AGT-CFO")
        assert rr.artifact_type == "plan"
        assert rr.reviewer == "AGT-CFO"


# ---------------------------------------------------------------------------
# Loader tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAgentClassLoader:

    def test_load_from_yaml(self, agent_class_yaml_file):
        ac = load_agent_class(agent_class_yaml_file)
        assert ac.id == "ACL-EXEC-001"
        assert ac.name == "Executive Planner"
        assert ac.role == "planner"
        assert len(ac.allowed_tools) == 2

    def test_load_minimal_yaml(self, tmp_path, minimal_agent_class_data):
        path = tmp_path / "min.yml"
        path.write_text(yaml.dump(minimal_agent_class_data))
        ac = load_agent_class(path)
        assert ac.id == "ACL-EXEC-001"
        assert ac.status == AgentClassStatus.DRAFT


# ---------------------------------------------------------------------------
# detect_manifest_type tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestDetectManifestType:

    def test_detects_agent_class(self):
        data = {"id": "ACL-EXEC-001", "name": "test"}
        assert detect_manifest_type(data) == "agent-class"

    def test_detects_agent_class_various_prefixes(self):
        for prefix in ["ACL-EXEC-001", "ACL-FIN-042", "ACL-OPS-999"]:
            assert detect_manifest_type({"id": prefix}) == "agent-class"

    def test_does_not_confuse_with_agent(self):
        assert detect_manifest_type({"id": "AGT-EXEC-001"}) == "agent"


# ---------------------------------------------------------------------------
# HarnessBundle integration tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestHarnessBundleIntegration:

    def test_bundle_has_agent_classes_field(self):
        bundle = HarnessBundle(harness=None)  # type: ignore[arg-type]
        assert bundle.agent_classes == {}

    def test_bundle_agent_classes_dict(self, full_agent_class_data):
        ac = AgentClass(**full_agent_class_data)
        bundle = HarnessBundle(harness=None)  # type: ignore[arg-type]
        bundle.agent_classes[ac.id] = ac
        assert "ACL-EXEC-001" in bundle.agent_classes
        assert bundle.agent_classes["ACL-EXEC-001"].role == "planner"
