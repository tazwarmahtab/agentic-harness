"""Unit tests for LLM routing manifest validation."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from aos.llm import (
    VentureRoutingManifest,
    validate_manifest,
    load_manifest,
)


def test_validate_manifest_valid():
    """Test validation of a valid manifest."""
    manifest = VentureRoutingManifest(
        version="1.0",
        venture="test",
        dag=[("default", "fast"), ("fast", "free")],
        criticality_map={
            "critical": "default",
            "high": "default",
            "medium": "fast",
            "low": "free",
        },
        fallback_path=["default", "fast", "free"],
    )
    # Should not raise an exception
    validate_manifest(manifest)


def test_validate_manifest_cyclic_dag():
    """Test validation fails for cyclic DAG."""
    manifest = VentureRoutingManifest(
        version="1.0",
        venture="test",
        dag=[("default", "fast"), ("fast", "default")],  # Cycle
        criticality_map={
            "critical": "default",
            "high": "default",
            "medium": "fast",
            "low": "free",
        },
        fallback_path=["default", "fast"],
    )
    with pytest.raises(ValueError, match="contains cycles"):
        validate_manifest(manifest)


def test_validate_manifest_invalid_fallback_path():
    """Test validation fails for invalid fallback path."""
    manifest = VentureRoutingManifest(
        version="1.0",
        venture="test",
        dag=[("default", "fast"), ("fast", "free")],
        criticality_map={
            "critical": "default",
            "high": "default",
            "medium": "fast",
            "low": "free",
        },
        fallback_path=["default", "free"],  # Missing 'fast'
    )
    with pytest.raises(ValueError, match="not a valid path"):
        validate_manifest(manifest)


def test_validate_manifest_missing_criticality():
    """Test validation fails for missing criticality mapping."""
    manifest = VentureRoutingManifest(
        version="1.0",
        venture="test",
        dag=[("default", "fast"), ("fast", "free")],
        criticality_map={
            "critical": "default",
            "high": "default",
            # Missing medium and low
        },
        fallback_path=["default", "fast", "free"],
    )
    with pytest.raises(ValueError, match="Missing criticality mapping"):
        validate_manifest(manifest)


def test_validate_manifest_model_not_in_dag():
    """Test validation fails for model in criticality_map not in DAG."""
    manifest = VentureRoutingManifest(
        version="1.0",
        venture="test",
        dag=[("default", "fast")],
        criticality_map={
            "critical": "default",
            "high": "default",
            "medium": "fast",
            "low": "free",  # Not in DAG
        },
        fallback_path=["default", "fast"],
    )
    with pytest.raises(ValueError, match="not found in DAG"):
        validate_manifest(manifest)


def test_load_manifest_netso():
    """Test loading the Netso routing manifest."""
    # This tests the actual Netso manifest in the codebase
    manifest = load_manifest("netso")
    assert manifest.venture == "netso"
    assert "critical" in manifest.criticality_map
    assert "default" in manifest.fallback_path


def test_load_manifest_transitbd():
    """Test loading the TransitBD routing manifest."""
    # This tests the actual TransitBD manifest in the codebase
    manifest = load_manifest("transitbd")
    assert manifest.venture == "transitbd"
    assert "critical" in manifest.criticality_map
    assert "default" in manifest.fallback_path


def test_load_manifest_missing_file():
    """Test loading a missing manifest file."""
    with pytest.raises(FileNotFoundError, match="No routing manifest found"):
        load_manifest("nonexistent_venture")


def test_resolve_model_with_manifest():
    """Test resolve_model uses venture manifest."""
    from aos.llm import resolve_model

    # Criticality "high" for Netso should use "default" tier
    model = resolve_model("high", "netso")
    assert model == "meta/llama-3.1-8b-instruct"

    # Criticality "critical" for Netso uses "reasoning" tier
    model = resolve_model("critical", "netso")
    assert model == "meta/llama-3.1-8b-instruct"


def test_resolve_model_fallback_without_manifest():
    """Test resolve_model falls back to global mapping when no manifest."""
    from aos.llm import resolve_model

    # Should use global CRITICALITY_TO_MODEL when no manifest
    model = resolve_model("high", "nonexistent_venture")
    assert model == "meta/llama-3.1-8b-instruct"