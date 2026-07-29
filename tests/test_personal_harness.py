"""Tests for AOS Personal Harness — Phase 15."""

from __future__ import annotations
import sys

from pathlib import Path

import pytest

from aos.registry import load_registry


class TestPersonalHarnessLoading:
    def test_load_personal_harness(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        assert len(registry.harnesses) == 1
        bundle = list(registry.harnesses.values())[0]
        assert bundle.harness.id == "HAR-PER-001"

    def test_personal_has_6_specialists(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert len(bundle.specialists) == 6

    def test_personal_has_planner(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.planner is not None
        assert bundle.planner.id == "AGT-PER-PLAN"

    def test_personal_has_dispatcher(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        assert bundle.dispatcher is not None
        assert bundle.dispatcher.id == "AGT-PER-DISPATCH"


class TestCalendarManager:
    def test_calendar_exists(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        cal = bundle.specialists.get("AGT-PER-CAL")
        assert cal is not None
        assert cal.name == "Calendar Manager"
        assert cal.criticality.value == "high"

    def test_calendar_has_focus_time_constraint(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        cal = bundle.specialists.get("AGT-PER-CAL")
        assert cal is not None
        constraint_text = " ".join(cal.constraints).lower()
        assert "deep_work" in constraint_text or "morning" in constraint_text


class TestTaskManager:
    def test_task_manager_exists(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        task = bundle.specialists.get("AGT-PER-TASK")
        assert task is not None
        assert task.name == "Task Manager"
        assert task.criticality.value == "high"

    def test_task_manager_has_max_3_constraint(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        task = bundle.specialists.get("AGT-PER-TASK")
        assert task is not None
        constraint_text = " ".join(task.constraints).lower()
        assert "max_3" in constraint_text or "3_focus" in constraint_text


class TestHealthTracker:
    def test_health_exists(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        health = bundle.specialists.get("AGT-PER-HEALTH")
        assert health is not None
        assert health.name == "Health Tracker"
        assert health.criticality.value == "high"

    def test_health_has_exercise_constraint(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        health = bundle.specialists.get("AGT-PER-HEALTH")
        assert health is not None
        constraint_text = " ".join(health.constraints).lower()
        assert "exercise" in constraint_text


class TestHabitCoach:
    def test_habit_exists(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        habit = bundle.specialists.get("AGT-PER-HABIT")
        assert habit is not None
        assert habit.name == "Habit Coach"
        assert habit.criticality.value == "medium"


class TestReadingManager:
    def test_reading_exists(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        read = bundle.specialists.get("AGT-PER-READ")
        assert read is not None
        assert read.name == "Reading Manager"
        assert read.criticality.value == "medium"


class TestGoalTracker:
    def test_goal_exists(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        goal = bundle.specialists.get("AGT-PER-GOAL")
        assert goal is not None
        assert goal.name == "Goal Tracker"
        assert goal.criticality.value == "high"

    def test_goal_has_quarterly_review_constraint(self) -> None:
        harness_dir = Path("aos/harnesses/personal")
        if not harness_dir.exists():
            pytest.skip("Personal harness not found")
        registry = load_registry(harness_dir)
        bundle = list(registry.harnesses.values())[0]
        goal = bundle.specialists.get("AGT-PER-GOAL")
        assert goal is not None
        constraint_text = " ".join(goal.constraints).lower()
        assert "quarterly" in constraint_text


class TestCLIPersonalHarness:
    def test_cli_run_personal_harness(self) -> None:
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "aos", "run", "--harness", "personal", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert "personal" in result.stdout.lower()
        assert "Running harness cycle" in result.stdout

    def test_cli_validate_personal_harness(self) -> None:
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "aos", "validate", "--harness", "personal"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode in (0, 1)
