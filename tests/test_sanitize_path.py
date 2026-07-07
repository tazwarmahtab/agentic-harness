"""Tests for the hardened sanitize_path function in tazos.hardening.

Covers: path traversal (literal, URL-encoded, double-encoded),
null bytes, backslashes, absolute paths, tilde, normalization bypasses,
empty input, and logging behavior.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestSanitizePath:
    """Thorough tests for sanitize_path input validation."""

    def test_clean_relative_path(self) -> None:
        """A clean relative path is returned as-is (normalized)."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "project/tazos/harnesses/executive"

        # Act
        result = sanitize_path(path)

        # Assert
        assert result is not None
        assert result == "project/tazos/harnesses/executive"

    def test_rejects_literal_dotdot(self) -> None:
        """Path with literal '..' segments is rejected."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "/project/../../etc/passwd"

        # Act
        result = sanitize_path(path)

        # Assert
        assert result is None

    def test_rejects_url_encoded_dotdot(self) -> None:
        """URL-encoded '%2e%2e' traversal is rejected."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "/project/%2e%2e/etc/passwd"

        # Act
        result = sanitize_path(path)

        # Assert
        assert result is None

    def test_rejects_double_encoded_dotdot(self) -> None:
        """Double URL-encoded '%252e%252e' traversal is rejected."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "/project/%252e%252e/etc/passwd"

        # Act
        result = sanitize_path(path)

        # Assert
        assert result is None

    def test_rejects_null_bytes(self) -> None:
        """Path containing null bytes is rejected."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "/project/\x00/etc/passwd"

        # Act
        result = sanitize_path(path)

        # Assert
        assert result is None

    def test_rejects_backslash(self) -> None:
        """Windows-style backslash path is rejected."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "/project/..\\etc\\passwd"

        # Act
        result = sanitize_path(path)

        # Assert
        assert result is None

    def test_rejects_absolute_path(self) -> None:
        """Absolute path (leading slash) is rejected."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "/etc/passwd"

        # Act
        result = sanitize_path(path)

        # Assert
        assert result is None

    def test_rejects_tilde(self) -> None:
        """Tilde expansion path is rejected."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "~/etc/passwd"

        # Act
        result = sanitize_path(path)

        # Assert
        assert result is None

    def test_rejects_double_slash_bypass(self) -> None:
        """Path with double slashes that normpath changes is rejected."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "/project//etc/passwd"

        # Act
        result = sanitize_path(path)

        # Assert — blocked by both absolute-path check and normalization-bypass check
        assert result is None

    def test_rejects_dot_segments(self) -> None:
        """Path with dot segments that normpath changes is rejected."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "/project/./foo"

        # Act
        result = sanitize_path(path)

        # Assert — blocked by both absolute-path check and normalization-bypass check
        assert result is None

    def test_allows_clean_simple(self) -> None:
        """Simple relative path is allowed."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "harnesses/executive"

        # Act
        result = sanitize_path(path)

        # Assert
        assert result == "harnesses/executive"

    def test_rejects_relative_with_dots(self) -> None:
        """Relative path with '..' that contains '/.' is rejected by normalization-bypass check.

        posixpath.normpath resolves 'harnesses/../harnesses/executive' to
        'harnesses/executive', so normalized != path. The original contains
        '/..' which contains '/.', triggering check #7 (normalization bypass).
        """
        from tazos.hardening import sanitize_path

        # Arrange
        path = "harnesses/../harnesses/executive"

        # Act
        result = sanitize_path(path)

        # Assert — blocked because '/.' is present in the original path
        assert result is None

    def test_empty_string(self) -> None:
        """Empty string is rejected."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = ""

        # Act
        result = sanitize_path(path)

        # Assert
        assert result is None

    def test_logging_on_block(self) -> None:
        """logger.warning is called when a path is blocked."""
        from tazos.hardening import sanitize_path

        # Arrange — use a path that hits the literal '..' traversal check
        # (normalized form keeps '..' only if it can't be resolved,
        # e.g. ".." alone normpath returns "..")
        malicious_path = "/project/../../etc/passwd"

        # Act
        with patch("tazos.hardening.logger") as mock_logger:
            result = sanitize_path(malicious_path)

            # Assert — blocked (absolute path check fires first for this input)
            assert result is None
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert isinstance(warning_msg, str)
            assert "blocked" in warning_msg.lower()

    def test_rejects_overlong_utf8_encoded_dotdot(self) -> None:
        """Overlong UTF-8 encoded dot-dot (%c0%ae) is rejected."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "/project/%c0%ae%c0%ae/etc/passwd"

        # Act
        result = sanitize_path(path)

        # Assert
        assert result is None

    def test_clean_multi_segment_relative_path(self) -> None:
        """Deep clean relative path is allowed and returned unchanged."""
        from tazos.hardening import sanitize_path

        # Arrange
        path = "tazos/harnesses/evaluator/config.json"

        # Act
        result = sanitize_path(path)

        # Assert
        assert result == "tazos/harnesses/evaluator/config.json"

    def test_rejects_trailing_dotdot(self) -> None:
        """Path ending with '..' segment is rejected by normalization-bypass check.

        posixpath.normpath('project/..') returns '.', so normalized != path.
        The original contains '/.' (from '/..'), triggering check #7.
        """
        from tazos.hardening import sanitize_path

        # Arrange
        path = "project/.."

        # Act
        result = sanitize_path(path)

        # Assert — blocked because '/.' is present in the original path
        assert result is None


class TestConnectionLimiterExtended:
    """Additional ConnectionLimiter tests beyond the base suite."""

    def test_active_count_tracks_acquires(self) -> None:
        """active_count reflects the number of acquired connections."""
        from tazos.hardening import ConnectionLimiter

        # Arrange
        limiter = ConnectionLimiter(max_connections=5)

        # Act
        limiter.try_acquire("c1")
        limiter.try_acquire("c2")

        # Assert
        assert limiter.active_count == 2

    def test_active_count_after_release(self) -> None:
        """active_count decreases after release."""
        from tazos.hardening import ConnectionLimiter

        # Arrange
        limiter = ConnectionLimiter(max_connections=3)
        limiter.try_acquire("c1")
        limiter.try_acquire("c2")

        # Act
        limiter.release("c1")

        # Assert
        assert limiter.active_count == 1

    def test_acquire_same_id_twice(self) -> None:
        """Acquiring the same conn_id twice counts as one active connection."""
        from tazos.hardening import ConnectionLimiter

        # Arrange
        limiter = ConnectionLimiter(max_connections=2)

        # Act
        limiter.try_acquire("c1")
        limiter.try_acquire("c1")  # duplicate

        # Assert — set deduplicates, so active_count is 1
        assert limiter.active_count == 1
        assert limiter.try_acquire("c2") is True

    def test_release_and_reacquire_fills_slot(self) -> None:
        """After releasing, the slot can be reused to reach capacity again."""
        from tazos.hardening import ConnectionLimiter

        # Arrange
        limiter = ConnectionLimiter(max_connections=1)

        # Act
        limiter.try_acquire("c1")
        limiter.release("c1")
        limiter.try_acquire("c2")

        # Assert
        assert limiter.active_count == 1
        assert limiter.try_acquire("c3") is False
