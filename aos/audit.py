"""Structured audits for code, manifests, documents, plans, and artifacts."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable


class AuditSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass(frozen=True)
class AuditFinding:
    finding_id: str
    category: str
    severity: AuditSeverity
    confidence: float
    evidence: str
    recommendation: str
    blocks_ship: bool = False
    location: str = ""

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")


@dataclass
class AuditReport:
    target: str
    target_type: str
    findings: list[AuditFinding] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str = ""
    status: str = "pending"

    def finalize(self) -> "AuditReport":
        self.findings.sort(key=lambda f: (
            {AuditSeverity.CRITICAL: 0, AuditSeverity.HIGH: 1, AuditSeverity.MEDIUM: 2,
             AuditSeverity.LOW: 3, AuditSeverity.INFO: 4}[f.severity],
            -f.confidence,
        ))
        self.status = "blocked" if any(f.blocks_ship for f in self.findings) else "pass"
        self.completed_at = datetime.now(timezone.utc).isoformat()
        return self

    @property
    def blocking_findings(self) -> list[AuditFinding]:
        return [f for f in self.findings if f.blocks_ship]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["findings"] = [
            {**asdict(f), "severity": f.severity.value} for f in self.findings
        ]
        return data


AuditChecker = Callable[[str, str], Iterable[AuditFinding]]


class AuditEngine:
    """Run composable checkers and return a ranked, machine-readable report."""

    def __init__(self, checkers: Iterable[AuditChecker] = ()) -> None:
        self.checkers = list(checkers)

    def run(self, target: str, target_type: str, content: str) -> AuditReport:
        report = AuditReport(target=target, target_type=target_type)
        for checker in self.checkers:
            report.findings.extend(checker(target, content))
        return report.finalize()

    @classmethod
    def default(cls) -> "AuditEngine":
        return cls([_check_todos, _check_placeholders, _check_secrets])

    def audit_path(self, path: str | Path, target_type: str = "artifact") -> AuditReport:
        resolved = Path(path)
        if not resolved.exists():
            report = AuditReport(str(resolved), target_type)
            report.findings.append(AuditFinding(
                "AUDIT-MISSING-001", "integrity", AuditSeverity.CRITICAL, 1.0,
                f"Target does not exist: {resolved}", "Create or correct the target path.", True,
            ))
            return report.finalize()
        if not resolved.is_file():
            raise ValueError(f"audit target must be a file: {resolved}")
        return self.run(str(resolved), target_type, resolved.read_text(encoding="utf-8"))


def _check_todos(target: str, content: str) -> Iterable[AuditFinding]:
    for index, line in enumerate(content.splitlines(), 1):
        if re.search(r"\b(TODO|FIXME|XXX)\b", line, re.IGNORECASE):
            yield AuditFinding(
                f"AUDIT-TODO-{index}", "unfinished_work", AuditSeverity.MEDIUM, 0.98,
                line.strip(), "Resolve or explicitly track this unfinished item.", False,
                f"{target}:{index}",
            )


def _check_placeholders(target: str, content: str) -> Iterable[AuditFinding]:
    for index, line in enumerate(content.splitlines(), 1):
        if re.search(r"\[(?:FEATURE|TASK|TODO|OUTPUT|INPUT|TBD)\]", line, re.IGNORECASE):
            yield AuditFinding(
                f"AUDIT-PLACEHOLDER-{index}", "placeholder", AuditSeverity.HIGH, 0.99,
                line.strip(), "Replace the placeholder before shipment.", True,
                f"{target}:{index}",
            )


def _check_secrets(target: str, content: str) -> Iterable[AuditFinding]:
    pattern = re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[^\s'\"]{12,}")
    for index, line in enumerate(content.splitlines(), 1):
        if pattern.search(line) and not re.search(r"(example|placeholder|your[_-])", line, re.IGNORECASE):
            yield AuditFinding(
                f"AUDIT-SECRET-{index}", "security", AuditSeverity.CRITICAL, 0.85,
                "Potential credential-like value detected.", "Move the value to a secret store and rotate it.", True,
                f"{target}:{index}",
            )
