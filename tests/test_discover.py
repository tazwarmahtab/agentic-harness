"""Tests for venture discovery module."""

from __future__ import annotations

from pathlib import Path

from aos.discover import discover_ventures, find_venture


VENTURES_DIR = Path(__file__).resolve().parent.parent / "aos" / "ventures"


class TestDiscoverVentures:
    def test_discovers_all_ventures(self):
        results = discover_ventures(VENTURES_DIR)
        names = [v.name for _, v in results]
        assert "Netso Energy" in names

    def test_returns_path_and_venture(self):
        results = discover_ventures(VENTURES_DIR)
        for path, venture in results:
            assert isinstance(path, Path)
            assert path.name == "venture.yml"
            assert hasattr(venture, "id")
            assert hasattr(venture, "name")

    def test_sorted_by_name(self):
        results = discover_ventures(VENTURES_DIR)
        names = [v.name for _, v in results]
        assert names == sorted(names)

    def test_nonexistent_dir_returns_empty(self):
        results = discover_ventures(Path("/nonexistent/path"))
        assert results == []

    def test_none_uses_default_dir(self):
        results = discover_ventures(None)
        assert len(results) >= 1


class TestFindVenture:
    def test_find_by_id(self):
        result = find_venture("VEN-NETSO-001", VENTURES_DIR)
        assert result is not None
        path, venture = result
        assert venture.id == "VEN-NETSO-001"

    def test_find_by_name_lowercase(self):
        result = find_venture("netso", VENTURES_DIR)
        assert result is not None
        _, venture = result
        assert "netso" in venture.name.lower()

    def test_find_by_full_name(self):
        result = find_venture("Netso Energy", VENTURES_DIR)
        assert result is not None

    def test_find_by_partial_name(self):
        result = find_venture("netso", VENTURES_DIR)
        assert result is not None

    def test_not_found_returns_none(self):
        result = find_venture("nonexistent-venture", VENTURES_DIR)
        assert result is None

    def test_case_insensitive(self):
        result = find_venture("NETSO", VENTURES_DIR)
        assert result is not None
