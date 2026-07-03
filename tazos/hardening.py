"""Platform hardening — rate limiting, health checks, input validation, structured errors.

Provides:
  - RateLimiter: token-bucket rate limiting for API endpoints
  - HealthChecker: LLM + memory store health verification
  - Input validation: harness name, path sanitization
  - ConnectionLimiter: WebSocket connection cap
  - Structured error hierarchy with codes
"""

from __future__ import annotations

import re
import time
import threading
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Structured errors
# ---------------------------------------------------------------------------

class TazosError(Exception):
    """Base error with code for structured responses."""

    code: str = "TAZOS_ERROR"

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


class HarnessNotFoundError(TazosError):
    """Raised when a harness name is not found."""

    code = "HARNESS_NOT_FOUND"

    def __init__(self, name: str) -> None:
        super().__init__(f"Harness '{name}' not found")
        self.name = name


class RateLimitError(TazosError):
    """Raised when rate limit is exceeded."""

    code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, key: str) -> None:
        super().__init__(f"Rate limit exceeded for '{key}'")
        self.key = key


class ValidationError(TazosError):
    """Raised when input validation fails."""

    code = "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# Rate limiter (sliding window)
# ---------------------------------------------------------------------------

class RateLimiter:
    """Thread-safe sliding window rate limiter.

    Tracks request timestamps per key and evicts entries older than
    the window.  O(n) on eviction but n is bounded by max_requests.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Return True if the request is allowed, False if rate-limited."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._requests.get(key, [])
            # Evict expired entries
            timestamps = [t for t in timestamps if t > cutoff]
            if len(timestamps) >= self.max_requests:
                self._requests[key] = timestamps
                return False
            timestamps.append(now)
            self._requests[key] = timestamps
            return True


# ---------------------------------------------------------------------------
# Connection limiter (WebSocket)
# ---------------------------------------------------------------------------

class ConnectionLimiter:
    """Track and cap concurrent WebSocket connections."""

    def __init__(self, max_connections: int = 10) -> None:
        self.max_connections = max_connections
        self._active: set[str] = set()
        self._lock = threading.Lock()

    def try_acquire(self, conn_id: str) -> bool:
        """Try to acquire a connection slot. Returns False if at capacity."""
        with self._lock:
            if len(self._active) >= self.max_connections:
                return False
            self._active.add(conn_id)
            return True

    def release(self, conn_id: str) -> None:
        """Release a connection slot. Safe to call with unknown ID."""
        with self._lock:
            self._active.discard(conn_id)

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._active)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

_HARNESS_NAME_RE = re.compile(r"^[a-z][a-z0-9\-]{0,63}$")


def validate_harness_name(name: str) -> bool:
    """Validate a harness name: lowercase alphanumeric + hyphens, max 64 chars."""
    return bool(_HARNESS_NAME_RE.match(name))


def sanitize_path(path: str) -> str | None:
    """Reject path traversal attempts. Returns None if suspicious."""
    if ".." in path:
        return None
    return path


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

def health_check(
    llm: Any | None = None,
    memory_store: Any | None = None,
) -> dict[str, Any]:
    """Run a health check across system components.

    Returns a dict with status for each component.
    """
    result: dict[str, Any] = {
        "status": "ok",
        "llm": _check_llm(llm),
        "memory": _check_memory(memory_store),
    }

    # Overall status: ok if all ok, degraded if any degraded, down if any down
    statuses = [result["llm"]["status"], result["memory"]["status"]]
    if any(s == "down" for s in statuses):
        result["status"] = "degraded"
    elif all(s == "ok" for s in statuses):
        result["status"] = "ok"
    elif all(s in ("ok", "not_configured") for s in statuses):
        result["status"] = "ok"
    else:
        result["status"] = "degraded"

    return result


def _check_llm(llm: Any | None) -> dict[str, Any]:
    """Probe the LLM backend with a lightweight call."""
    if llm is None:
        return {"status": "not_configured"}
    try:
        llm.complete(
            model="test",
            system="ping",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=1,
            temperature=0.0,
        )
        return {"status": "ok"}
    except ConnectionError:
        return {"status": "degraded"}
    except Exception:
        return {"status": "degraded"}


def _check_memory(memory_store: Any | None) -> dict[str, Any]:
    """Check memory store stats."""
    if memory_store is None:
        return {"status": "not_configured"}
    try:
        total = 0
        for layer in memory_store.layers.values():
            for entries in layer.values():
                total += len(entries)
        return {"status": "ok", "total_entries": total}
    except Exception:
        return {"status": "degraded"}
