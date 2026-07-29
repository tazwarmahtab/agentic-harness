"""Bounded, evidence-driven quality cycles for agentic work.

This module is deliberately runtime-agnostic: an orchestrator supplies the
work, evaluation, and correction functions while AOS owns the loop contract,
budgets, stop reasons, and change history.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable


class QualityStatus(str, Enum):
    PASSED = "passed"
    RETRYING = "retrying"
    EXHAUSTED = "exhausted"
    BLOCKED = "blocked"


class FindingSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class QualityContract:
    task_id: str
    success_criteria: list[str]
    max_passes: int = 3
    stop_on_blocked: bool = True

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError("task_id must not be empty")
        if not self.success_criteria:
            raise ValueError("at least one success criterion is required")
        if self.max_passes < 1:
            raise ValueError("max_passes must be at least 1")


@dataclass(frozen=True)
class QualityFinding:
    code: str
    message: str
    severity: FindingSeverity = FindingSeverity.MEDIUM
    evidence: str = ""
    blocking: bool = True
    recommendation: str = ""

    @property
    def impact(self) -> int:
        return {FindingSeverity.CRITICAL: 4, FindingSeverity.HIGH: 3,
                FindingSeverity.MEDIUM: 2, FindingSeverity.LOW: 1}[self.severity]


@dataclass
class QualityEvaluation:
    passed: bool
    findings: list[QualityFinding] = field(default_factory=list)
    score: float | None = None


@dataclass
class QualityPass:
    pass_number: int
    status: QualityStatus
    output: Any = None
    findings: list[QualityFinding] = field(default_factory=list)
    change_summary: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["findings"] = [
            {**asdict(f), "severity": f.severity.value} for f in self.findings
        ]
        return data


@dataclass
class QualityCycleResult:
    task_id: str
    status: QualityStatus
    final_output: Any
    passes: list[QualityPass]
    stop_reason: str

    @property
    def change_log(self) -> list[str]:
        return [p.change_summary for p in self.passes if p.change_summary]

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "final_output": self.final_output,
            "passes": [p.to_dict() for p in self.passes],
            "stop_reason": self.stop_reason,
            "change_log": self.change_log,
        }


class QualityCycle:
    """Run work, evaluate it, and apply bounded corrections until done."""

    def __init__(
        self,
        contract: QualityContract,
        work: Callable[[Any, int], Any],
        evaluate: Callable[[Any, int], QualityEvaluation],
        correct: Callable[[Any, QualityFinding, int], tuple[Any, str]] | None = None,
    ) -> None:
        self.contract = contract
        self.work = work
        self.evaluate = evaluate
        self.correct = correct

    def run(self, initial_input: Any = None) -> QualityCycleResult:
        passes: list[QualityPass] = []
        current = initial_input

        for number in range(1, self.contract.max_passes + 1):
            started = datetime.now(timezone.utc).isoformat()
            try:
                output = self.work(current, number)
                evaluation = self.evaluate(output, number)
            except Exception as exc:
                record = QualityPass(number, QualityStatus.BLOCKED, current,
                                     change_summary=f"blocked: {exc}",
                                     started_at=started,
                                     finished_at=datetime.now(timezone.utc).isoformat())
                passes.append(record)
                return QualityCycleResult(self.contract.task_id, QualityStatus.BLOCKED,
                                          current, passes, f"execution_error: {exc}")

            findings = sorted(evaluation.findings, key=lambda f: f.impact, reverse=True)
            if evaluation.passed:
                passes.append(QualityPass(number, QualityStatus.PASSED, output, findings,
                                          "passed quality contract", started,
                                          datetime.now(timezone.utc).isoformat()))
                return QualityCycleResult(self.contract.task_id, QualityStatus.PASSED,
                                          output, passes, "success_criteria_met")

            if number >= self.contract.max_passes:
                passes.append(QualityPass(number, QualityStatus.EXHAUSTED, output, findings,
                                          "retry budget exhausted", started,
                                          datetime.now(timezone.utc).isoformat()))
                return QualityCycleResult(self.contract.task_id, QualityStatus.EXHAUSTED,
                                          output, passes, "max_passes_reached")

            if self.correct is None or not findings:
                passes.append(QualityPass(number, QualityStatus.BLOCKED, output, findings,
                                          "no correction strategy available", started,
                                          datetime.now(timezone.utc).isoformat()))
                return QualityCycleResult(self.contract.task_id, QualityStatus.BLOCKED,
                                          output, passes, "missing_correction_strategy")

            finding = findings[0]
            if self.contract.stop_on_blocked and finding.blocking and not finding.recommendation:
                # A blocking finding without a safe recommendation must surface.
                passes.append(QualityPass(number, QualityStatus.BLOCKED, output, findings,
                                          "blocking finding has no safe fix", started,
                                          datetime.now(timezone.utc).isoformat()))
                return QualityCycleResult(self.contract.task_id, QualityStatus.BLOCKED,
                                          output, passes, f"blocked_by:{finding.code}")
            try:
                current, change = self.correct(output, finding, number)
            except Exception as exc:
                passes.append(QualityPass(number, QualityStatus.BLOCKED, output, findings,
                                          f"correction failed: {exc}", started,
                                          datetime.now(timezone.utc).isoformat()))
                return QualityCycleResult(self.contract.task_id, QualityStatus.BLOCKED,
                                          output, passes, f"correction_error: {exc}")
            passes.append(QualityPass(number, QualityStatus.RETRYING, output, findings,
                                      change, started, datetime.now(timezone.utc).isoformat()))

        raise AssertionError("quality cycle exited without a terminal result")
