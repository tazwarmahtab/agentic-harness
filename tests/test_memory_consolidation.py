from aos.memory_consolidation import consolidate_daily, get_consolidation_stats


def test_consolidate_daily_returns_list():
    entries = consolidate_daily(venture="netso")
    assert isinstance(entries, list)


def test_consolidate_daily_no_traces():
    entries = consolidate_daily(venture="nonexistent_venture_xyz")
    assert entries == []


def test_consolidation_stats():
    stats = get_consolidation_stats(venture="netso")
    assert "venture" in stats
    assert "trace_files" in stats
