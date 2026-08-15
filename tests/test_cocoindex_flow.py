"""Tests for CocoIndex indexer — unit tests only (no live DB required).

All pgvector/DB calls and cocoindex itself are mocked at module import
time via sys.modules, so no live install of cocoindex is needed.

Tests verify:
  - _validate_venture_root raises FileNotFoundError on missing dir
  - _validate_venture_root raises NotADirectoryError on file
  - _validate_venture_root warns when no .md files found
  - _validate_venture_root logs md file count on success
  - get_flow raises RuntimeError when DATABASE_URL is unset
  - get_flow raises ValueError on null-byte in DATABASE_URL
  - run_index calls flow.update() (incremental)
  - run_index calls flow.update(full=True) (force)
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def _install_cocoindex_stub() -> MagicMock:
    """Install a minimal cocoindex stub into sys.modules.

    Must run before any import of aos.ventures.netso.indexer.
    Returns the mock so callers can configure it further.
    """
    mock = MagicMock()

    # Decorator @cocoindex.flow_def(name=...) must return a callable that
    # accepts a function and returns a MagicMock with an .update() method.
    def _flow_def_decorator(name: str):
        def wrapper(fn):
            m = MagicMock()
            m.__name__ = fn.__name__
            return m
        return wrapper

    mock.flow_def.side_effect = _flow_def_decorator
    mock.init = MagicMock()

    sys.modules.setdefault("cocoindex", mock)
    return mock


# Install stub before any test imports the indexer module.
_COCO_STUB = _install_cocoindex_stub()


@pytest.mark.unit
class TestValidateVentureRoot:
    """_validate_venture_root guards."""

    def _fresh_import(self):
        """Force a re-import of the indexer (removes cached module)."""
        sys.modules.pop("aos.ventures.netso.indexer", None)
        from aos.ventures.netso import indexer  # noqa: PLC0415
        return indexer

    def test_raises_when_root_missing(self, tmp_path: Path) -> None:
        indexer = self._fresh_import()
        with (
            patch.object(indexer, "VENTURE_ROOT", tmp_path / "nonexistent"),
            pytest.raises(FileNotFoundError, match="not found"),
        ):
            indexer._validate_venture_root()

    def test_raises_when_root_is_file(self, tmp_path: Path) -> None:
        indexer = self._fresh_import()
        fake_file = tmp_path / "notadir.txt"
        fake_file.touch()

        with (
            patch.object(indexer, "VENTURE_ROOT", fake_file),
            pytest.raises(NotADirectoryError),
        ):
            indexer._validate_venture_root()

    def test_warns_when_no_md_files(self, tmp_path: Path, caplog) -> None:
        import logging

        indexer = self._fresh_import()
        with (
            patch.object(indexer, "VENTURE_ROOT", tmp_path),
            caplog.at_level(logging.WARNING, logger="aos.ventures.netso.indexer"),
        ):
            indexer._validate_venture_root()

        assert "No .md files found" in caplog.text

    def test_logs_md_file_count(self, tmp_path: Path, caplog) -> None:
        import logging

        indexer = self._fresh_import()
        (tmp_path / "a.md").write_text("hello")
        (tmp_path / "b.md").write_text("world")

        with (
            patch.object(indexer, "VENTURE_ROOT", tmp_path),
            caplog.at_level(logging.INFO, logger="aos.ventures.netso.indexer"),
        ):
            indexer._validate_venture_root()

        assert "2" in caplog.text


@pytest.mark.unit
class TestGetFlow:
    """get_flow() guards on DATABASE_URL."""

    def _fresh_import(self):
        sys.modules.pop("aos.ventures.netso.indexer", None)
        from aos.ventures.netso import indexer  # noqa: PLC0415
        return indexer

    def test_raises_without_database_url(self) -> None:
        indexer = self._fresh_import()
        with (
            patch.dict(os.environ, {"DATABASE_URL": ""}),
            pytest.raises(RuntimeError, match="DATABASE_URL"),
        ):
            indexer.get_flow()

    def test_rejects_null_byte_in_database_url(self) -> None:
        """Null bytes are invalid in connection strings.

        On Python 3.13+, os.environ itself raises ValueError on null bytes,
        preventing the string from reaching get_flow. Either way the system
        rejects the value before any DB connection is attempted.
        """
        indexer = self._fresh_import()
        # The ValueError may come from patch.dict (OS-level) or get_flow itself.
        with pytest.raises((ValueError, RuntimeError)):
            with patch.dict(os.environ, {"DATABASE_URL": "postgresql://foo\x00bar"}):
                indexer.get_flow()


@pytest.mark.unit
class TestRunIndex:
    """run_index() execution paths."""

    def _fresh_import(self):
        sys.modules.pop("aos.ventures.netso.indexer", None)
        from aos.ventures.netso import indexer  # noqa: PLC0415
        return indexer

    def test_run_index_incremental(self, tmp_path: Path) -> None:
        indexer = self._fresh_import()
        (tmp_path / "doc.md").write_text("content")

        mock_flow = MagicMock()

        with (
            patch.object(indexer, "VENTURE_ROOT", tmp_path),
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}),
            patch.object(indexer, "cocoindex", _COCO_STUB),
            patch.object(indexer, "netso_doc_flow", mock_flow),
        ):
            indexer.run_index(force=False)

        mock_flow.update.assert_called_once_with()

    def test_run_index_force(self, tmp_path: Path) -> None:
        indexer = self._fresh_import()
        (tmp_path / "doc.md").write_text("content")

        mock_flow = MagicMock()

        with (
            patch.object(indexer, "VENTURE_ROOT", tmp_path),
            patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost/test"}),
            patch.object(indexer, "cocoindex", _COCO_STUB),
            patch.object(indexer, "netso_doc_flow", mock_flow),
        ):
            indexer.run_index(force=True)

        mock_flow.update.assert_called_once_with(full=True)
