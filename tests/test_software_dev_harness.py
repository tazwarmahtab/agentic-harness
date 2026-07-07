"""Tests for Software Dev Harness — full component stack."""

from pathlib import Path
import pytest
from tazos.loader import (
    load_harness, load_agent, load_memory, load_tool_registry,
    load_evaluation, load_policy_collection, load_sop,
)

HARNESS_DIR = Path(__file__).resolve().parent.parent / "tazos" / "harnesses" / "software_dev"

@pytest.fixture
def harness_dir():
    if not HARNESS_DIR.exists():
        pytest.skip("Software Dev harness directory not found")
    return HARNESS_DIR

class TestDevManifests:
    def test_harness_loads(self, harness_dir):
        h = load_harness(harness_dir / "harness.yml")
        assert h.id == "HAR-DEV-001"

    def test_six_specialists(self, harness_dir):
        specs = list((harness_dir / "specialists").glob("*.yml"))
        assert len(specs) == 6

class TestDevComponents:
    def test_memory_loads(self, harness_dir):
        m = load_memory(harness_dir / "memory.yml")
        assert m.id == "MEM-DEV-001"

    def test_tools_loads(self, harness_dir):
        t = load_tool_registry(harness_dir / "tools.yml")
        assert t.id == "TOL-DEV-001"

    def test_approvals_loads(self, harness_dir):
        p = load_policy_collection(harness_dir / "approvals.yml")
        assert p.id == "POL-DEV-001"

    def test_evaluation_loads(self, harness_dir):
        e = load_evaluation(harness_dir / "evaluation.yml")
        assert e.id == "EVAL-DEV-001"

    def test_sop_loads(self, harness_dir):
        sop = load_sop(harness_dir / "sops" / "feature-development.yml")
        assert sop.id == "SOP-DEV-001"
