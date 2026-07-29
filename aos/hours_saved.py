"""Hours saved tracker — measures AI vs estimated manual work time."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta


@dataclass(frozen=True)
class TaskEstimate:
    task: str
    ai_minutes: float
    manual_minutes_est: float
    venture: str = "unknown"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HoursTracker:
    def __init__(self) -> None:
        self._records: list[TaskEstimate] = []

    def record(self, estimate: TaskEstimate) -> None:
        self._records.append(estimate)

    def total_saved_minutes(self) -> float:
        return sum(r.manual_minutes_est - r.ai_minutes for r in self._records)

    def weekly_summary(self) -> dict:
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        week_records = [
            r for r in self._records
            if datetime.fromisoformat(r.timestamp) >= week_ago
        ]
        saved = sum(r.manual_minutes_est - r.ai_minutes for r in week_records)
        return {
            "total_tasks": len(week_records),
            "hours_saved": round(saved / 60, 1),
            "ai_hours_spent": round(sum(r.ai_minutes for r in week_records) / 60, 1),
            "manual_hours_equivalent": round(sum(r.manual_minutes_est for r in week_records) / 60, 1),
        }
