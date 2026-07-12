"""Tests for platform hardening — rate limiting, health checks, input validation, audit cap."""

from __future__ import annotations



from aos.memory import MemoryStore


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_allows_within_limit(self) -> None:
        from aos.hardening import RateLimiter
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        for _ in range(10):
            assert limiter.allow("test-key") is True

    def test_blocks_over_limit(self) -> None:
        from aos.hardening import RateLimiter
        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            assert limiter.allow("test-key") is True
        assert limiter.allow("test-key") is False

    def test_separate_keys_independent(self) -> None:
        from aos.hardening import RateLimiter
        limiter = RateLimiter(max_requests=2, window_seconds=60)
        assert limiter.allow("a") is True
        assert limiter.allow("a") is True
        assert limiter.allow("a") is False
        assert limiter.allow("b") is True

    def test_window_expiry_resets(self) -> None:
        from aos.hardening import RateLimiter
        limiter = RateLimiter(max_requests=2, window_seconds=0)
        # Window of 0 means always expired
        for _ in range(10):
            assert limiter.allow("test-key") is True


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealthCheck:
    def test_health_llm_ok(self) -> None:
        from aos.hardening import health_check
        from aos.llm import DryRunLLMClient

        store = MemoryStore()
        store.seed_from_dict("long_term", "test", [{"key": "a", "value": "b"}])
        result = health_check(llm=DryRunLLMClient(), memory_store=store)
        assert result["status"] == "ok"
        assert result["llm"]["status"] == "ok"
        assert result["memory"]["status"] == "ok"

    def test_health_memory_store(self) -> None:
        from aos.hardening import health_check
        from aos.llm import DryRunLLMClient

        store = MemoryStore()
        store.seed_from_dict("long_term", "test", [{"key": "a", "value": "b"}])
        result = health_check(llm=DryRunLLMClient(), memory_store=store)
        assert result["memory"]["status"] == "ok"
        assert result["memory"]["total_entries"] >= 1

    def test_health_degraded_no_memory(self) -> None:
        from aos.hardening import health_check
        from aos.llm import DryRunLLMClient

        result = health_check(llm=DryRunLLMClient(), memory_store=None)
        assert result["memory"]["status"] == "not_configured"

    def test_health_llm_degraded(self) -> None:
        from aos.hardening import health_check

        class BrokenLLM:
            def complete(self, **kwargs):
                raise ConnectionError("LLM unreachable")

        result = health_check(llm=BrokenLLM())
        assert result["llm"]["status"] == "degraded"


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_validate_harness_name_valid(self) -> None:
        from aos.hardening import validate_harness_name
        assert validate_harness_name("executive") is True
        assert validate_harness_name("evaluator") is True
        assert validate_harness_name("my-harness-123") is True

    def test_validate_harness_name_invalid(self) -> None:
        from aos.hardening import validate_harness_name
        assert validate_harness_name("") is False
        assert validate_harness_name("../../etc/passwd") is False
        assert validate_harness_name("exec; rm -rf /") is False
        assert validate_harness_name("a" * 100) is False

    def test_sanitize_path(self) -> None:
        from aos.hardening import sanitize_path
        result = sanitize_path("project/aos/harnesses/executive")
        assert result is not None
        assert ".." not in result
        assert result == "project/aos/harnesses/executive"

    def test_sanitize_path_rejects_traversal(self) -> None:
        from aos.hardening import sanitize_path
        result = sanitize_path("/project/../../etc/passwd")
        assert result is None


# ---------------------------------------------------------------------------
# Audit trail cap
# ---------------------------------------------------------------------------

class TestAuditTrailCap:
    def test_audit_trail_capped(self) -> None:

        store = MemoryStore()
        # Submit many candidates to build up audit trail
        for i in range(250):
            store.submit_candidate(
                agent_id="AGT-CEO",
                layer="long_term",
                domain="facts",
                key=f"key-{i}",
                value=f"value-{i}",
            )
            # Auto-review to generate audit records
            if store.candidates:
                store.candidates[-1].id
                store.review_pending(auto_store=True)

        # Audit trail should be capped at 200
        assert len(store.audit_trail) <= 200

    def test_audit_trail_preserves_recent(self) -> None:
        store = MemoryStore(max_audit_records=5)
        for i in range(10):
            store.submit_candidate(
                agent_id="AGT-CEO",
                layer="long_term",
                domain="facts",
                key=f"key-{i}",
                value=f"value-{i}",
            )
            store.review_pending(auto_store=True)

        # Most recent should be kept
        assert len(store.audit_trail) <= 5


# ---------------------------------------------------------------------------
# WebSocket connection limiter
# ---------------------------------------------------------------------------

class TestConnectionLimiter:
    def test_allows_within_limit(self) -> None:
        from aos.hardening import ConnectionLimiter
        limiter = ConnectionLimiter(max_connections=5)
        assert limiter.try_acquire("conn-1") is True
        assert limiter.try_acquire("conn-2") is True

    def test_blocks_over_limit(self) -> None:
        from aos.hardening import ConnectionLimiter
        limiter = ConnectionLimiter(max_connections=2)
        assert limiter.try_acquire("a") is True
        assert limiter.try_acquire("b") is True
        assert limiter.try_acquire("c") is False

    def test_release_allows_new(self) -> None:
        from aos.hardening import ConnectionLimiter
        limiter = ConnectionLimiter(max_connections=1)
        assert limiter.try_acquire("a") is True
        assert limiter.try_acquire("b") is False
        limiter.release("a")
        assert limiter.try_acquire("b") is True

    def test_release_unknown_is_safe(self) -> None:
        from aos.hardening import ConnectionLimiter
        limiter = ConnectionLimiter(max_connections=5)
        limiter.release("nonexistent")  # should not raise


# ---------------------------------------------------------------------------
# Structured errors
# ---------------------------------------------------------------------------

class TestStructuredErrors:
    def test_error_hierarchy(self) -> None:
        from aos.hardening import AOSError, HarnessNotFoundError, RateLimitError, ValidationError

        assert issubclass(HarnessNotFoundError, AOSError)
        assert issubclass(RateLimitError, AOSError)
        assert issubclass(ValidationError, AOSError)

    def test_error_has_code_and_message(self) -> None:
        from aos.hardening import HarnessNotFoundError

        err = HarnessNotFoundError("executive")
        assert err.code == "HARNESS_NOT_FOUND"
        assert "executive" in str(err)
        assert err.to_dict()["code"] == "HARNESS_NOT_FOUND"
