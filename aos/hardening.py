"""Platform hardening — rate limiting, health checks, input validation, structured errors.

Provides:
  - RateLimiter: token-bucket rate limiting for API endpoints
  - HealthChecker: LLM + memory store health verification
  - Input validation: harness name, path sanitization
  - ConnectionLimiter: WebSocket connection cap
  - Structured error hierarchy with codes
"""

from __future__ import annotations

import logging
import os
import posixpath
import re
import time
import threading
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Structured errors
# ---------------------------------------------------------------------------

class AOSError(Exception):
    """Base error with code for structured responses."""

    code: str = "AOS_ERROR"

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": str(self)}


class HarnessNotFoundError(AOSError):
    """Raised when a harness name is not found."""

    code = "HARNESS_NOT_FOUND"

    def __init__(self, name: str) -> None:
        super().__init__(f"Harness '{name}' not found")
        self.name = name


class RateLimitError(AOSError):
    """Raised when rate limit is exceeded."""

    code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, key: str) -> None:
        super().__init__(f"Rate limit exceeded for '{key}'")
        self.key = key


class ValidationError(AOSError):
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
    """Reject path traversal attempts. Returns normalized path or None if suspicious.

    Checks for:
      1. Literal ".." segments
      2. URL-encoded traversal: %2e%2e, %252e%252e, %c0%ae (overlong UTF-8)
      3. Null bytes: \\x00
      4. Backslashes (Windows-style traversal)
      5. Absolute paths (leading /)
      6. Tilde expansion (~)
      7. Path normalization bypasses: /foo/./bar, /foo//bar
    """
    if not path:
        return None

    # --- Normalize first: collapse double slashes, resolve . segments ---
    # posixpath handles /foo//bar and /foo/./bar without touching the filesystem
    normalized = posixpath.normpath(path)

    # --- Decode percent-encoding for inspection, then re-check ---
    # Unescape once to catch %2e%2e and double-encoded %252e%252e
    decoded = urllib.parse.unquote(path)
    decoded_double = urllib.parse.unquote(decoded)

    # Build a combined string to inspect for all encoded variants
    combined = f"{path} {normalized} {decoded} {decoded_double}"

    # 1. Literal ".." in any form (normalized already collapses these, but check raw)
    if ".." in normalized:
        logger.warning("Blocked path traversal (literal '..'): %s", path)
        return None

    # 2. URL-encoded traversal: %2e%2e, %252e%252e (double-encoded), %c0%ae (overlong UTF-8)
    encoded_patterns = [
        r"(?i)%2e",
        r"(?i)%c0%ae",
        r"(?i)%c0%af",
        r"(?i)%e0%80%af",
    ]
    for pattern in encoded_patterns:
        if re.search(pattern, combined):
            logger.warning("Blocked URL-encoded traversal (pattern %s): %s", pattern, path)
            return None

    # 3. Null bytes — dangerous in C-backed path operations
    if "\x00" in path or "\x00" in normalized:
        logger.warning("Blocked null byte in path: %s", path)
        return None

    # 4. Backslashes — Windows-style traversal on any OS
    if "\\" in path:
        logger.warning("Blocked backslash in path: %s", path)
        return None

    # 5. Absolute paths (harness paths must be relative)
    if normalized.startswith("/"):
        logger.warning("Blocked absolute path: %s", path)
        return None

    # 6. Tilde expansion
    if "~" in path:
        logger.warning("Blocked tilde in path: %s", path)
        return None

    # 7. Path normalization bypasses — if normpath changed it, the original
    #    contained ./ or // that could be used to confuse logic
    if normalized != path and (
        "/." in path or "//" in path
    ):
        logger.warning("Blocked normalization bypass in path: %s", path)
        return None

    return normalized


def validate_path_contents(path: str) -> tuple[bool, str]:
    """Check that a path exists and resolves to a file (not a symlink escape).

    Args:
        path: The (already sanitized) filesystem path to validate.

    Returns:
        (is_valid, reason_string) — is_valid is True only when the path
        exists as a regular file and its resolved real path does not escape
        the current working directory.
    """
    p = Path(path)

    if not p.exists():
        return False, "path does not exist"

    # Resolve to real path (follows symlinks)
    real = p.resolve()

    # Ensure the resolved path stays under the current working directory
    cwd = Path.cwd().resolve()
    try:
        real.relative_to(cwd)
    except ValueError:
        return False, f"resolved path {real} escapes working directory {cwd}"

    if not real.is_file():
        return False, f"resolved path {real} is not a regular file"

    return True, "ok"


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
