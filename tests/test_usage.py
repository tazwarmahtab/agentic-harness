"""Tests for TAZ OS usage tracker — cost visibility."""

from __future__ import annotations

from aos.usage import UsageTracker


class TestUsageTracker:
    def test_record_usage(self) -> None:
        tracker = UsageTracker()
        tracker.record("AGT-EXEC-CFO", "sonnet", {"prompt_tokens": 1000, "completion_tokens": 500})
        report = tracker.report()
        assert report.total_prompt_tokens == 1000
        assert report.total_completion_tokens == 500
        assert report.total_calls == 1

    def test_accumulates_multiple_calls(self) -> None:
        tracker = UsageTracker()
        tracker.record("AGT-EXEC-CFO", "sonnet", {"prompt_tokens": 1000, "completion_tokens": 500})
        tracker.record("AGT-EXEC-COO", "sonnet", {"prompt_tokens": 800, "completion_tokens": 300})
        report = tracker.report()
        assert report.total_prompt_tokens == 1800
        assert report.total_completion_tokens == 800
        assert report.total_calls == 2

    def test_per_agent_breakdown(self) -> None:
        tracker = UsageTracker()
        tracker.record("AGT-EXEC-CFO", "sonnet", {"prompt_tokens": 1000, "completion_tokens": 500})
        tracker.record("AGT-EXEC-COO", "haiku", {"prompt_tokens": 800, "completion_tokens": 300})
        report = tracker.report()
        assert "AGT-EXEC-CFO" in report.by_agent
        assert "AGT-EXEC-COO" in report.by_agent
        assert report.by_agent["AGT-EXEC-CFO"]["prompt_tokens"] == 1000

    def test_per_model_breakdown(self) -> None:
        tracker = UsageTracker()
        tracker.record("A", "sonnet", {"prompt_tokens": 100, "completion_tokens": 50})
        tracker.record("B", "haiku", {"prompt_tokens": 200, "completion_tokens": 100})
        report = tracker.report()
        assert "sonnet" in report.by_model
        assert "haiku" in report.by_model

    def test_empty_tracker(self) -> None:
        tracker = UsageTracker()
        report = tracker.report()
        assert report.total_calls == 0
        assert report.total_prompt_tokens == 0

    def test_handles_missing_usage_fields(self) -> None:
        tracker = UsageTracker()
        tracker.record("A", "sonnet", {})
        report = tracker.report()
        assert report.total_calls == 1
        assert report.total_prompt_tokens == 0

    def test_total_tokens_property(self) -> None:
        tracker = UsageTracker()
        tracker.record("A", "sonnet", {"prompt_tokens": 100, "completion_tokens": 50})
        report = tracker.report()
        assert report.total_tokens == 150

    def test_summary_string(self) -> None:
        tracker = UsageTracker()
        tracker.record("AGT-EXEC-CFO", "sonnet", {"prompt_tokens": 1000, "completion_tokens": 500})
        report = tracker.report()
        summary = report.summary()
        assert "1 calls" in summary
        assert "1500 tokens" in summary
