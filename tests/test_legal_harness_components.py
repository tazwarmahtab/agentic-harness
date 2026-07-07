"""Tests for Legal Harness — full component stack."""

from pathlib import Path

import pytest

from tazos.loader import (
    load_harness, load_agent, load_memory, load_tool_registry,
    load_evaluation, load_policy_collection, load_sop,
)

HARNESS_DIR = Path(__file__).resolve().parent.parent / "tazos" / "harnesses" / "legal"

@pytest.fixture
def harness_dir():
    if not HARNESS_DIR.exists():
        pytest.skip("Legal harness directory not found")
    return HARNESS_DIR

class TestLegalManifests:
    def test_harness_loads(self, harness_dir):
        h = load_harness(harness_dir / "harness.yml")
        assert h.id == "HAR-LEG-001"

    def test_five_specialists(self, harness_dir):
        specs = list((harness_dir / "specialists").glob("*.yml"))
        assert len(specs) == 5

    def test_compliance_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "compliance.yml")
        assert "COMP" in a.id

    def test_contract_reviewer_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "contract-reviewer.yml")
        assert "REV" in a.id

    def test_ppa_specialist_loads(self, harness_dir):
        a = load_agent(harness_dir / "specialists" / "ppa-specialist.yml")
        assert "PPA" in a.id

class TestLegalComponents:
    def test_memory_loads(self, harness_dir):
        m = load_memory(harness_dir / "memory.yml")
        assert m.id == "MEM-LEG-001"

    def test_tools_loads(self, harness_dir):
        t = load_tool_registry(harness_dir / "tools.yml")
        assert t.id == "TOL-LEG-001"

    def test_approvals_loads(self, harness_dir):
        p = load_policy_collection(harness_dir / "approvals.yml")
        assert p.id == "POL-LEG-001"

    def test_evaluation_loads(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.id == "EVAL-LEG-001"

    def test_sop_loads(self, harness_dir):
        sop = load_sop(harness_dir / "sops" / "contract-lifecycle.yml")
        assert sop.id == "SOP-LEG-001"
