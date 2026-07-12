"""Tests for _run_parallel — M3 async parallel execution.

_run_parallel wraps synchronous callables in asyncio.to_thread for
I/O-bound workloads (HTTP, LLM calls). Falls back to ThreadPoolExecutor
when an event loop is already running (LangGraph, Jupyter).
"""

from __future__ import annotations

import time
import pytest
from aos.graph import _run_parallel, _fallback_threadpool


class TestRunParallel:
    """Tests for _run_parallel function."""

    def test_empty_list(self) -> None:
        result = _run_parallel([], lambda x: x * 2)
        assert result == []

    def test_single_item(self) -> None:
        result = _run_parallel([5], lambda x: x * 2)
        assert result == [10]

    def test_multiple_items_preserve_order(self) -> None:
        """Results must be in same order as input items."""
        items = [1, 2, 3, 4, 5]
        result = _run_parallel(items, lambda x: x * 10)
        assert result == [10, 20, 30, 40, 50]

    def test_concurrent_execution_is_faster(self) -> None:
        """Parallel execution should be faster than sequential for slow tasks."""
        items = list(range(8))

        def slow_double(x: int) -> int:
            time.sleep(0.1)
            return x * 2

        start = time.monotonic()
        result = _run_parallel(items, slow_double)
        elapsed = time.monotonic() - start

        assert result == [x * 2 for x in items]
        # Sequential would take ~0.8s; parallel should be under 0.3s
        assert elapsed < 0.5

    def test_exception_in_one_item_doesnt_crash(self) -> None:
        """Exception in one callable is caught by the caller."""

        def maybe_fail(x: int) -> int:
            if x == 3:
                raise ValueError("boom")
            return x

        # _run_parallel propagates exceptions from asyncio.gather
        with pytest.raises(Exception):
            _run_parallel([1, 2, 3, 4], maybe_fail)

    def test_none_fn_result(self) -> None:
        """Callable returning None is fine."""
        result = _run_parallel([1, 2, 3], lambda x: None)
        assert result == [None, None, None]

    def test_string_items(self) -> None:
        """Works with non-numeric items."""
        result = _run_parallel(["hello", "world"], str.upper)
        assert result == ["HELLO", "WORLD"]


class TestFallbackThreadpool:
    """Tests for _fallback_threadpool (sync fallback path)."""

    def test_basic_execution(self) -> None:
        result = _fallback_threadpool([1, 2, 3], lambda x: x + 10)
        # Thread pool doesn't guarantee order, so sort
        assert sorted(result) == [11, 12, 13]

    def test_respects_max_workers(self) -> None:
        """Should not fail with max_workers=1."""
        result = _fallback_threadpool([1, 2, 3], lambda x: x, max_workers=1)
        assert sorted(result) == [1, 2, 3]

    def test_empty_list(self) -> None:
        result = _fallback_threadpool([], lambda x: x)
        assert result == []
