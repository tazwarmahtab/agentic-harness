"""Tests for Quality Gate Receipts — ReceiptChain, hash linking, thread safety."""

from __future__ import annotations

import threading

import pytest

from aos.receipts import (
    GateType,
    QualityGateReceipt,
    ReceiptChain,
    Verdict,
    compute_receipt_hash,
    create_receipt,
)


# ---------------------------------------------------------------------------
# QualityGateReceipt model tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestQualityGateReceipt:

    def test_frozen(self):
        r = _make_receipt(id_="R-001")
        with pytest.raises(AttributeError):
            r.id = "changed"  # type: ignore[misc]

    def test_to_dict(self):
        r = _make_receipt(id_="R-002", verdict=Verdict.FAIL)
        d = r.to_dict()
        assert d["id"] == "R-002"
        assert d["verdict"] == "fail"
        assert d["gate_type"] == "iteration"
        assert "receipt_hash" not in d  # excluded from to_dict

    def test_defaults(self):
        r = _make_receipt(id_="R-003")
        assert r.verdict == Verdict.PASS
        assert r.artifacts == []
        assert r.previous_receipt_hash is None


# ---------------------------------------------------------------------------
# compute_receipt_hash tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestComputeReceiptHash:

    def test_deterministic(self):
        r = _make_receipt(id_="R-HASH-001")
        h1 = compute_receipt_hash(r)
        h2 = compute_receipt_hash(r)
        assert h1 == h2

    def test_different_content_different_hash(self):
        r1 = _make_receipt(id_="R-HASH-002", findings_count=0)
        r2 = _make_receipt(id_="R-HASH-002", findings_count=5)
        assert compute_receipt_hash(r1) != compute_receipt_hash(r2)

    def test_excludes_receipt_hash_field(self):
        """Changing receipt_hash field alone should not change computed hash."""
        r1 = _make_receipt(id_="R-HASH-003")
        r2 = QualityGateReceipt(
            id=r1.id, stage_hash=r1.stage_hash, gate_type=r1.gate_type,
            agent_id=r1.agent_id, timestamp=r1.timestamp,
            findings_count=r1.findings_count, findings_fixed=r1.findings_fixed,
            tests_passed=r1.tests_passed, tests_total=r1.tests_total,
            receipt_hash="totally-different-hash",
            previous_receipt_hash=r1.previous_receipt_hash,
            artifacts=r1.artifacts, verdict=r1.verdict,
        )
        assert compute_receipt_hash(r1) == compute_receipt_hash(r2)


# ---------------------------------------------------------------------------
# create_receipt tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCreateReceipt:

    def test_auto_computes_hash(self):
        r = create_receipt(
            id="R-CREATE-001", stage_hash="abc123", gate_type=GateType.PHASE,
            agent_id="AGT-EXEC-COO", timestamp="2025-01-01T00:00:00Z",
            findings_count=3, findings_fixed=2, tests_passed=10, tests_total=12,
        )
        expected = compute_receipt_hash(r)
        assert r.receipt_hash == expected

    def test_chain_link(self):
        r1 = create_receipt(
            id="R-CREATE-002", stage_hash="abc", gate_type=GateType.ITERATION,
            agent_id="AGT-001", timestamp="t1", findings_count=0, findings_fixed=0,
            tests_passed=5, tests_total=5,
        )
        r2 = create_receipt(
            id="R-CREATE-003", stage_hash="def", gate_type=GateType.PRE_PR,
            agent_id="AGT-001", timestamp="t2", findings_count=1, findings_fixed=1,
            tests_passed=6, tests_total=6, previous_receipt_hash=r1.receipt_hash,
        )
        assert r2.previous_receipt_hash == r1.receipt_hash


# ---------------------------------------------------------------------------
# ReceiptChain tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestReceiptChain:

    def test_empty_chain_valid(self):
        chain = ReceiptChain()
        assert chain.verify()
        assert chain.length == 0

    def test_single_receipt_valid(self):
        chain = ReceiptChain()
        r = create_receipt(
            id="R-CHAIN-001", stage_hash="a", gate_type=GateType.ITERATION,
            agent_id="AGT-001", timestamp="t", findings_count=0, findings_fixed=0,
            tests_passed=1, tests_total=1,
        )
        chain.append(r)
        assert chain.verify()
        assert chain.length == 1

    def test_two_linked_receipts_valid(self):
        chain = ReceiptChain()
        r1 = create_receipt(
            id="R-CHAIN-002", stage_hash="a", gate_type=GateType.ITERATION,
            agent_id="AGT-001", timestamp="t1", findings_count=0, findings_fixed=0,
            tests_passed=1, tests_total=1,
        )
        r2 = create_receipt(
            id="R-CHAIN-003", stage_hash="b", gate_type=GateType.PHASE,
            agent_id="AGT-001", timestamp="t2", findings_count=0, findings_fixed=0,
            tests_passed=1, tests_total=1, previous_receipt_hash=r1.receipt_hash,
        )
        chain.append(r1)
        chain.append(r2)
        assert chain.verify()
        assert chain.length == 2

    def test_broken_chain_detected(self):
        chain = ReceiptChain()
        r1 = create_receipt(
            id="R-CHAIN-004", stage_hash="a", gate_type=GateType.ITERATION,
            agent_id="AGT-001", timestamp="t1", findings_count=0, findings_fixed=0,
            tests_passed=1, tests_total=1,
        )
        # r2 links to wrong hash
        r2 = create_receipt(
            id="R-CHAIN-005", stage_hash="b", gate_type=GateType.PHASE,
            agent_id="AGT-001", timestamp="t2", findings_count=0, findings_fixed=0,
            tests_passed=1, tests_total=1, previous_receipt_hash="WRONG-HASH",
        )
        chain.append(r1)
        chain.append(r2)
        assert not chain.verify()
        is_valid, errors = chain.verify_strict()
        assert not is_valid
        assert len(errors) == 1
        assert "WRONG-HASH" in errors[0]

    def test_first_receipt_with_wrong_previous_hash(self):
        chain = ReceiptChain()
        r = create_receipt(
            id="R-CHAIN-006", stage_hash="a", gate_type=GateType.ITERATION,
            agent_id="AGT-001", timestamp="t", findings_count=0, findings_fixed=0,
            tests_passed=1, tests_total=1, previous_receipt_hash="some-hash",
        )
        chain.append(r)
        assert not chain.verify()

    def test_clear(self):
        chain = ReceiptChain()
        r = create_receipt(
            id="R-CHAIN-007", stage_hash="a", gate_type=GateType.ITERATION,
            agent_id="AGT-001", timestamp="t", findings_count=0, findings_fixed=0,
            tests_passed=1, tests_total=1,
        )
        chain.append(r)
        assert chain.length == 1
        chain.clear()
        assert chain.length == 0

    def test_receipts_returns_copy(self):
        chain = ReceiptChain()
        r = create_receipt(
            id="R-CHAIN-008", stage_hash="a", gate_type=GateType.ITERATION,
            agent_id="AGT-001", timestamp="t", findings_count=0, findings_fixed=0,
            tests_passed=1, tests_total=1,
        )
        chain.append(r)
        receipts = chain.receipts
        receipts.clear()  # mutate the copy
        assert chain.length == 1  # original unaffected


# ---------------------------------------------------------------------------
# Thread safety test
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestReceiptChainThreadSafety:

    def test_concurrent_appends(self):
        """Concurrent appends don't crash or lose receipts."""
        chain = ReceiptChain()
        errors: list[Exception] = []

        def worker(idx: int) -> None:
            try:
                r = create_receipt(
                    id=f"R-THREAD-{idx:03d}", stage_hash=f"h{idx}",
                    gate_type=GateType.ITERATION, agent_id="AGT-THREAD",
                    timestamp="t", findings_count=0, findings_fixed=0,
                    tests_passed=1, tests_total=1,
                )
                chain.append(r)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert chain.length == 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_receipt(
    *,
    id_: str = "R-TEST-001",
    findings_count: int = 0,
    verdict: Verdict = Verdict.PASS,
    previous_receipt_hash: str | None = None,
) -> QualityGateReceipt:
    """Create a test receipt with sensible defaults."""
    return create_receipt(
        id=id_,
        stage_hash="stage-abc",
        gate_type=GateType.ITERATION,
        agent_id="AGT-EXEC-COO",
        timestamp="2025-01-01T00:00:00Z",
        findings_count=findings_count,
        findings_fixed=0,
        tests_passed=5,
        tests_total=5,
        previous_receipt_hash=previous_receipt_hash,
        verdict=verdict,
    )
