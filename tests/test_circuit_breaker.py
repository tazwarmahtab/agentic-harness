"""Unit tests for circuit breaker functionality."""

import time

import pytest

from aos.llm import CircuitBreaker


def test_circuit_breaker_initial_state():
    cb = CircuitBreaker(failure_threshold=3, recovery_window_sec=1)
    assert not cb.is_open()


def test_circuit_breaker_trips_after_threshold():
    cb = CircuitBreaker(failure_threshold=3, recovery_window_sec=1)
    cb.record_failure()
    assert not cb.is_open()
    cb.record_failure()
    assert not cb.is_open()
    cb.record_failure()
    assert cb.is_open()


def test_circuit_breaker_resets_after_recovery():
    cb = CircuitBreaker(failure_threshold=2, recovery_window_sec=1)
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open()
    time.sleep(1.1)
    assert not cb.is_open()


def test_circuit_breaker_resets_on_success():
    cb = CircuitBreaker(failure_threshold=2, recovery_window_sec=10)
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open()
    cb.record_success()
    assert not cb.is_open()


def test_circuit_breaker_multiple_models_independent():
    """Circuit breakers for different models operate independently."""
    cb1 = CircuitBreaker(failure_threshold=2, recovery_window_sec=10)
    cb2 = CircuitBreaker(failure_threshold=2, recovery_window_sec=10)

    cb1.record_failure()
    cb1.record_failure()
    assert cb1.is_open()
    assert not cb2.is_open()  # cb2 should still be closed


def test_circuit_breaker_thread_safety():
    """Circuit breaker should be thread-safe."""
    import threading
    cb = CircuitBreaker(failure_threshold=100, recovery_window_sec=10)

    def record_failures():
        for _ in range(10):
            cb.record_failure()

    threads = [threading.Thread(target=record_failures) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert cb.failure_count == 50
    assert not cb.is_open()  # 50 < 100 threshold