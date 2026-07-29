from aos.cost_tracker import CostTracker, CostRecord

def test_cost_tracker_records_usage():
    tracker = CostTracker()
    tracker.record(CostRecord(harness="executive", agent="AGT-EXEC-CFO", model="claude-3.5-sonnet", input_tokens=1000, output_tokens=500))
    assert tracker.total_cost() > 0

def test_cost_tracker_per_harness():
    tracker = CostTracker()
    tracker.record(CostRecord(harness="executive", agent="AGT-EXEC-CFO", model="claude-3.5-sonnet", input_tokens=1000, output_tokens=500))
    tracker.record(CostRecord(harness="finance", agent="AGT-FIN-UNIT", model="claude-3.5-sonnet", input_tokens=2000, output_tokens=1000))
    by_harness = tracker.cost_by_harness()
    assert "executive" in by_harness
    assert "finance" in by_harness
    assert by_harness["finance"] > by_harness["executive"]

def test_cost_tracker_free_model():
    tracker = CostTracker()
    tracker.record(CostRecord(harness="personal", agent="AGT-PER-TASK", model="free", input_tokens=5000, output_tokens=2000))
    assert tracker.total_cost() == 0.0
