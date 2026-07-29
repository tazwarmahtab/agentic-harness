from aos.hours_saved import HoursTracker, TaskEstimate


def test_hours_tracker_records():
    tracker = HoursTracker()
    tracker.record(TaskEstimate(task="financial_analysis", ai_minutes=2.5, manual_minutes_est=45.0, venture="netso"))
    assert tracker.total_saved_minutes() > 0


def test_hours_tracker_weekly():
    tracker = HoursTracker()
    tracker.record(TaskEstimate(task="t1", ai_minutes=5, manual_minutes_est=60, venture="netso"))
    tracker.record(TaskEstimate(task="t2", ai_minutes=3, manual_minutes_est=30, venture="netso"))
    weekly = tracker.weekly_summary()
    assert weekly["total_tasks"] == 2
    assert weekly["hours_saved"] > 0


def test_hours_tracker_free_model():
    tracker = HoursTracker()
    tracker.record(TaskEstimate(task="t", ai_minutes=10, manual_minutes_est=10, venture="netso"))
    assert tracker.total_saved_minutes() == 0.0
