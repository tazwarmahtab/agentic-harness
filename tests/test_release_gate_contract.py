"""Regression tests for the evidence-backed, fail-closed release register."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from scripts.check_release_gates import (
    EXPECTED_IDS,
    GateRegisterError,
    validate_register,
)

REGISTER = (
    Path(__file__).resolve().parents[1]
    / "docs/architecture/agent-harness-gap-register-2026-11-01.json"
)


@pytest.fixture
def register() -> dict:
    return json.loads(REGISTER.read_text(encoding="utf-8"))


def test_committed_baseline_has_32_open_gaps(register: dict) -> None:
    result = validate_register(register)
    assert result == {
        "registered_gaps": 32,
        "verified_gaps": 0,
        "total_gates": 7,
        "all_gates_green": False,
    }


def test_duplicate_gap_id_fails_closed(register: dict) -> None:
    register["gaps"][1]["id"] = register["gaps"][0]["id"]
    with pytest.raises(GateRegisterError, match="duplicate"):
        validate_register(register)


def test_missing_gap_fails_closed(register: dict) -> None:
    register["gaps"].pop()
    with pytest.raises(GateRegisterError, match="coverage"):
        validate_register(register)


def test_wrong_gate_mapping_fails_closed(register: dict) -> None:
    register["gaps"][0]["gate"] = "G0"
    with pytest.raises(GateRegisterError, match="mapping"):
        validate_register(register)


def test_unverified_claim_cannot_turn_all_green(register: dict) -> None:
    register["all_gates_green"] = True
    with pytest.raises(GateRegisterError, match="all_gates_green"):
        validate_register(register)


def test_verified_without_evidence_is_rejected(register: dict) -> None:
    register["gaps"][0]["status"] = "verified"
    with pytest.raises(GateRegisterError, match="verified without verification"):
        validate_register(register)


def test_self_attestation_cannot_verify(register: dict) -> None:
    gap = register["gaps"][0]
    gap["status"] = "verified"
    gap["evidence"] = [{"ref": "https://example.test/run", "fingerprint": "abc", "result": "pass"}]
    gap["verification"] = {
        "commit_sha": "0123456789",
        "implemented_by": "agent-1",
        "verified_by": "agent-1",
        "verified_at": "2026-11-03T00:00:00+00:00",
        "test_summary": "synthetic fixture",
        "test_status": "passed",
    }
    with pytest.raises(GateRegisterError, match="not independent"):
        validate_register(register)


def test_verified_with_independent_receipt_does_not_turn_gate_green(register: dict) -> None:
    gap = register["gaps"][0]
    gap["status"] = "verified"
    gap["evidence"] = [{"ref": "https://example.test/run", "fingerprint": "abc", "result": "pass"}]
    gap["verification"] = {
        "commit_sha": "0123456789",
        "implemented_by": "agent-1",
        "verified_by": "agent-2",
        "verified_at": "2026-11-03T00:00:00+00:00",
        "test_summary": "synthetic fixture",
        "test_status": "passed",
    }
    result = validate_register(register)
    assert result["verified_gaps"] == 1
    assert result["all_gates_green"] is False
    assert {gap["id"] for gap in register["gaps"]} == EXPECTED_IDS


def test_invalid_status_fails_closed(register: dict) -> None:
    register["gaps"][0]["status"] = "done"
    with pytest.raises(GateRegisterError, match="unsupported status"):
        validate_register(register)


def test_input_document_is_not_mutated(register: dict) -> None:
    before = copy.deepcopy(register)
    validate_register(register)
    assert before == register


def test_failed_evidence_is_not_verification(register: dict) -> None:
    gap = register["gaps"][0]
    gap["status"] = "verified"
    gap["evidence"] = [{"ref": "https://example.test/run", "fingerprint": "abc123", "result": "fail"}]
    gap["verification"] = {
        "commit_sha": "0123456789",
        "implemented_by": "agent-1",
        "verified_by": "agent-2",
        "verified_at": "2026-11-03T00:00:00+00:00",
        "test_summary": "failed",
        "test_status": "failed",
    }
    with pytest.raises(GateRegisterError, match="failed or unverified evidence"):
        validate_register(register)


def test_nonpassing_test_receipt_is_rejected(register: dict) -> None:
    gap = register["gaps"][0]
    gap["status"] = "verified"
    gap["evidence"] = [{"ref": "https://example.test/run", "fingerprint": "abc123", "result": "pass"}]
    gap["verification"] = {
        "commit_sha": "0123456789",
        "implemented_by": "agent-1",
        "verified_by": "agent-2",
        "verified_at": "2026-11-03T00:00:00+00:00",
        "test_summary": "incomplete",
        "test_status": "failed",
    }
    with pytest.raises(GateRegisterError, match="test receipt"):
        validate_register(register)
