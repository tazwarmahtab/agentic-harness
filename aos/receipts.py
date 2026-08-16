"""Quality Gate Receipts — hash-chained receipts proving QG was run on specific changes.

Modeled after TheAgency's QGR (Quality Gate Receipt) chain.
Prevents "I reviewed it" without evidence by linking each receipt
cryptographically to the previous one.

ReceiptChain uses threading.Lock for safe concurrent access
(follows RateLimiter/ConnectionLimiter pattern in hardening.py).
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Receipt model
# ---------------------------------------------------------------------------


class GateType(str, Enum):
    ITERATION = "iteration"
    PHASE = "phase"
    PRE_PR = "pre-pr"


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    CONDITIONAL = "conditional"


@dataclass(frozen=True)
class QualityGateReceipt:
    """Immutable receipt proving a quality gate was run on specific changes."""

    id: str
    stage_hash: str  # hash of the staged changes
    gate_type: GateType
    agent_id: str  # who ran the gate
    timestamp: str
    findings_count: int
    findings_fixed: int
    tests_passed: int
    tests_total: int
    receipt_hash: str  # hash of this receipt (chain link)
    previous_receipt_hash: str | None  # chain to previous receipt
    artifacts: list[str] = field(default_factory=list)
    verdict: Verdict = Verdict.PASS

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for hashing and storage."""
        return {
            "id": self.id,
            "stage_hash": self.stage_hash,
            "gate_type": self.gate_type.value,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "findings_count": self.findings_count,
            "findings_fixed": self.findings_fixed,
            "tests_passed": self.tests_passed,
            "tests_total": self.tests_total,
            "previous_receipt_hash": self.previous_receipt_hash,
            "artifacts": self.artifacts,
            "verdict": self.verdict.value,
        }


def compute_receipt_hash(receipt: QualityGateReceipt) -> str:
    """Compute SHA-256 hash of receipt content (excludes receipt_hash itself)."""
    content = json.dumps(receipt.to_dict(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def create_receipt(
    *,
    id: str,
    stage_hash: str,
    gate_type: GateType,
    agent_id: str,
    timestamp: str,
    findings_count: int,
    findings_fixed: int,
    tests_passed: int,
    tests_total: int,
    previous_receipt_hash: str | None = None,
    artifacts: list[str] | None = None,
    verdict: Verdict = Verdict.PASS,
) -> QualityGateReceipt:
    """Create a receipt with auto-computed receipt_hash."""
    receipt = QualityGateReceipt(
        id=id,
        stage_hash=stage_hash,
        gate_type=gate_type,
        agent_id=agent_id,
        timestamp=timestamp,
        findings_count=findings_count,
        findings_fixed=findings_fixed,
        tests_passed=tests_passed,
        tests_total=tests_total,
        receipt_hash="",  # placeholder
        previous_receipt_hash=previous_receipt_hash,
        artifacts=artifacts or [],
        verdict=verdict,
    )
    computed_hash = compute_receipt_hash(receipt)
    return QualityGateReceipt(
        id=receipt.id,
        stage_hash=receipt.stage_hash,
        gate_type=receipt.gate_type,
        agent_id=receipt.agent_id,
        timestamp=receipt.timestamp,
        findings_count=receipt.findings_count,
        findings_fixed=receipt.findings_fixed,
        tests_passed=receipt.tests_passed,
        tests_total=receipt.tests_total,
        receipt_hash=computed_hash,
        previous_receipt_hash=receipt.previous_receipt_hash,
        artifacts=receipt.artifacts,
        verdict=receipt.verdict,
    )


# ---------------------------------------------------------------------------
# Receipt chain
# ---------------------------------------------------------------------------


class ReceiptChain:
    """Thread-safe hash-chain verifier for QGR receipts.

    Follows threading.Lock pattern from hardening.py RateLimiter/ConnectionLimiter.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._receipts: list[QualityGateReceipt] = []

    @property
    def receipts(self) -> list[QualityGateReceipt]:
        """Return a copy of the receipts list."""
        with self._lock:
            return list(self._receipts)

    @property
    def length(self) -> int:
        with self._lock:
            return len(self._receipts)

    def append(self, receipt: QualityGateReceipt) -> None:
        """Append a receipt to the chain. Thread-safe."""
        with self._lock:
            self._receipts.append(receipt)
            logger.info(
                "Receipt appended: %s (chain length: %d)",
                receipt.id,
                len(self._receipts),
            )

    def verify(self) -> bool:
        """Verify the chain is unbroken from first to last. Thread-safe.

        Checks:
        1. Each receipt's previous_receipt_hash matches the prior receipt's receipt_hash
        2. Each receipt's own receipt_hash is correctly computed
        3. The first receipt has previous_receipt_hash=None
        """
        with self._lock:
            return len(self._verify_unsafe()) == 0

    def _verify_unsafe(self) -> list[str]:
        """Internal verification — returns list of error strings (empty = valid).

        Must be called while holding self._lock.
        """
        errors: list[str] = []
        receipts = self._receipts

        if not receipts:
            return errors

        for i, receipt in enumerate(receipts):
            # Check hash chain linkage
            if i == 0:
                if receipt.previous_receipt_hash is not None:
                    errors.append(
                        f"Receipt {receipt.id}: first receipt should have "
                        f"previous_receipt_hash=None, got {receipt.previous_receipt_hash}"
                    )
            else:
                prev = receipts[i - 1]
                if receipt.previous_receipt_hash != prev.receipt_hash:
                    errors.append(
                        f"Receipt {receipt.id}: previous_receipt_hash "
                        f"({receipt.previous_receipt_hash}) != "
                        f"prior receipt hash ({prev.receipt_hash})"
                    )

            # Check own hash is correct
            expected_hash = compute_receipt_hash(receipt)
            if receipt.receipt_hash != expected_hash:
                errors.append(
                    f"Receipt {receipt.id}: receipt_hash "
                    f"({receipt.receipt_hash}) != computed ({expected_hash})"
                )

        return errors

    def verify_strict(self) -> tuple[bool, list[str]]:
        """Verify chain and return (is_valid, errors). Thread-safe."""
        with self._lock:
            errors = self._verify_unsafe()
            return len(errors) == 0, errors

    def clear(self) -> None:
        """Clear the chain. Thread-safe."""
        with self._lock:
            self._receipts.clear()
