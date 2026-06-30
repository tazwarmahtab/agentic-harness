"""Tests for TAZ OS multi-venture support."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from tazos.registry import load_registry, Registry
from tazos.loader import load_venture
from tazos.schemas.venture import Venture


# ---------------------------------------------------------------------------
# Venture loading
# ---------------------------------------------------------------------------


class TestVentureLoading:
    def test_load_netso_venture(self) -> None:
        path = Path("tazos/ventures/netso/venture.yml")
        if not path.exists():
            pytest.skip("Netso venture not found")
        venture = load_venture(path)
        assert venture.id == "VEN-NETSO-001"
        assert venture.name == "Netso Energy"
        assert venture.status == "active"

    def test_venture_has_artifacts(self) -> None:
        path = Path("tazos/ventures/netso/venture.yml")
        if not path.exists():
            pytest.skip("Netso venture not found")
        venture = load_venture(path)
        assert len(venture.artifacts) > 0

    def test_venture_has_financial_constants(self) -> None:
        path = Path("tazos/ventures/netso/venture.yml")
        if not path.exists():
            pytest.skip("Netso venture not found")
        venture = load_venture(path)
        assert venture.financial_constants is not None
        assert venture.financial_constants.true_variable_rate == 12.98


# ---------------------------------------------------------------------------
# Multi-venture discovery
# ---------------------------------------------------------------------------


class TestVentureDiscovery:
    def test_discover_ventures(self) -> None:
        """Discover all venture.yml files in ventures/ directory."""
        ventures_dir = Path("tazos/ventures")
        if not ventures_dir.exists():
            pytest.skip("Ventures directory not found")

        ventures = list(ventures_dir.glob("*/venture.yml"))
        assert len(ventures) >= 1  # At least Netso

    def test_load_multiple_ventures(self) -> None:
        """Load all discovered ventures."""
        ventures_dir = Path("tazos/ventures")
        if not ventures_dir.exists():
            pytest.skip("Ventures directory not found")

        for venture_path in ventures_dir.glob("*/venture.yml"):
            venture = load_venture(venture_path)
            assert venture.id.startswith("VEN-")
            assert venture.name
            assert venture.status in ("active", "inactive", "planning")


# ---------------------------------------------------------------------------
# Registry with venture selection
# ---------------------------------------------------------------------------


class TestRegistryVentureSelection:
    def test_load_with_specific_venture(self) -> None:
        """Load registry with a specific venture."""
        harness_dir = Path("tazos/harnesses/executive")
        venture_path = Path("tazos/ventures/netso/venture.yml")
        if not harness_dir.exists() or not venture_path.exists():
            pytest.skip("Required paths not found")

        registry = load_registry(harness_dir, venture_path)
        assert registry.venture is not None
        assert registry.venture.id == "VEN-NETSO-001"

    def test_load_without_venture(self) -> None:
        """Load registry without any venture."""
        harness_dir = Path("tazos/harnesses/executive")
        if not harness_dir.exists():
            pytest.skip("Harness directory not found")

        registry = load_registry(harness_dir, None)
        assert registry.venture is None
        assert len(registry.harnesses) > 0


# ---------------------------------------------------------------------------
# CLI multi-venture commands
# ---------------------------------------------------------------------------


class TestCLIMultiVenture:
    def test_cli_has_ventures_command(self) -> None:
        """CLI should have a 'ventures' subcommand."""
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "tazos", "ventures"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        # Should not crash (exit 0 or 1, but not exception)
        assert result.returncode in (0, 1)

    def test_cli_run_with_venture_flag(self) -> None:
        """CLI should accept --venture flag."""
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "tazos", "run", "--venture", "netso", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert "Netso" in result.stdout or result.returncode == 0

    def test_cli_run_with_unknown_venture_fails(self) -> None:
        """CLI should fail gracefully with unknown venture."""
        import subprocess
        result = subprocess.run(
            ["python3", "-m", "tazos", "run", "--venture", "nonexistent", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent),
        )
        assert result.returncode != 0 or "not found" in result.stderr.lower() or "error" in result.stderr.lower()
