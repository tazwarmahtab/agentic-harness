from __future__ import annotations

from pathlib import Path

import yaml

from aos.constants import NETSO_FINANCIAL
from aos.validator import validate_all, validate_manifest


def test_validate_manifest_path_traversal() -> None:
    path = Path("aos/harnesses/executive/../../etc/passwd")

    errors = validate_manifest(path)

    assert len(errors) == 1
    assert errors[0].field == "(path)"
    assert "Path traversal detected" in errors[0].error


def test_validate_all_path_traversal() -> None:
    harness_dir = Path("aos/harnesses/executive/../../etc/passwd")
    venture_path = Path("aos/ventures/netso/../../etc/passwd")

    result1 = validate_all(harness_dir)
    result2 = validate_all(Path("aos/harnesses/executive"), venture_path)

    assert not result1.ok
    assert len(result1.errors) == 1
    assert result1.errors[0].field == "(path)"
    assert "Path traversal detected" in result1.errors[0].error

    assert not result2.ok
    assert len(result2.errors) == 1
    assert result2.errors[0].field == "(path)"
    assert "Path traversal detected" in result2.errors[0].error


def test_validate_manifest_malformed_yaml(tmp_path: Path) -> None:
    temp_file = tmp_path / "malformed.yml"
    temp_file.write_text("invalid: [\n")

    errors = validate_manifest(temp_file)

    assert len(errors) == 1
    assert errors[0].field == "(load)"
    assert "Failed to load" in errors[0].error


def test_validate_manifest_invalid_root(tmp_path: Path) -> None:
    temp_file = tmp_path / "invalid_root.yml"
    temp_file.write_text("- item1\n- item2")

    errors = validate_manifest(temp_file)

    assert len(errors) == 1
    assert errors[0].field == "(root)"
    assert "YAML root is not a mapping" in errors[0].error


def test_validate_manifest_schema_validation(tmp_path: Path) -> None:
    temp_file = tmp_path / "agent.yml"
    data = {
        "id": "AGT-TEST-001",
        "harness": "HAR-TEST-001",
        "role": "Test Role",
    }
    temp_file.write_text(yaml.safe_dump(data))

    errors = validate_manifest(temp_file)

    assert len(errors) > 0
    assert any("name" in err.error or "name" in err.field for err in errors)


def test_validate_manifest_financial_constants_valid(tmp_path: Path) -> None:
    temp_file = tmp_path / "venture.yml"
    data = {
        "id": "VEN-NETSO-001",
        "name": "Netso Energy Test",
        "type": "venture",
        "status": "active",
        "version": "1.0.0",
        "identities": {"humans": []},
        "artifacts": {},
        "financial_constants": NETSO_FINANCIAL,
    }
    temp_file.write_text(yaml.safe_dump(data))

    errors = validate_manifest(temp_file)
    errors = [err for err in errors if err.severity == "error"]

    assert len(errors) == 0


def test_validate_manifest_financial_constants_mismatch(tmp_path: Path) -> None:
    temp_file = tmp_path / "venture.yml"
    mismatched_financial = dict(NETSO_FINANCIAL)
    mismatched_financial["true_variable_rate"] = 15.0

    data = {
        "id": "VEN-NETSO-001",
        "name": "Netso Energy Test",
        "type": "venture",
        "status": "active",
        "version": "1.0.0",
        "identities": {"humans": []},
        "artifacts": {},
        "financial_constants": mismatched_financial,
    }
    temp_file.write_text(yaml.safe_dump(data))

    errors = validate_manifest(temp_file)
    errors = [err for err in errors if err.severity == "error"]

    assert len(errors) == 1
    assert "true_variable_rate" in errors[0].field
    assert "does not match ground truth" in errors[0].error


def test_validate_manifest_policy_rules_invalid(tmp_path: Path) -> None:
    temp_file = tmp_path / "policy.yml"
    data = {
        "id": "POL-TEST-001",
        "name": "Test Policy Collection",
        "rules": [{"id": "rule-1"}],
    }
    temp_file.write_text(yaml.safe_dump(data))

    errors = validate_manifest(temp_file)
    errors = [err for err in errors if err.severity == "error"]

    assert len(errors) > 0
    fields = [err.field for err in errors]
    assert any("name" in field for field in fields)
    assert any("category" in field for field in fields)
    assert any("rule" in field for field in fields)
    assert any("action" in field for field in fields)


def test_validate_manifest_cross_references_warning(tmp_path: Path) -> None:
    temp_file = tmp_path / "harness.yml"
    data = {
        "id": "HAR-TEST-001",
        "name": "Test Harness",
        "venture": "VEN-UNKNOWN-999",
        "version": "1.0.0",
        "status": "draft",
        "mission": "Test mission.",
        "scope": {"in_scope": ["foo"], "out_of_scope": ["bar"]},
        "kpis": [{"name": "score", "target": ">80%"}],
        "inputs": [],
        "outputs": [],
    }
    temp_file.write_text(yaml.safe_dump(data))

    errors = validate_manifest(temp_file, known_ids={"HAR-TEST-001"})

    assert len(errors) == 1
    assert errors[0].severity == "warning"
    assert errors[0].field == "venture"
    assert "References unknown venture" in errors[0].error


def test_validate_all_executes_successfully(tmp_path: Path) -> None:
    harness_dir = tmp_path / "harnesses" / "test_harness"
    harness_dir.mkdir(parents=True, exist_ok=True)

    harness_data = {
        "id": "HAR-TEST-001",
        "name": "Test Harness",
        "venture": "VEN-NETSO-001",
        "version": "1.0.0",
        "status": "draft",
        "mission": "Test mission.",
        "scope": {"in_scope": ["foo"], "out_of_scope": ["bar"]},
        "kpis": [{"name": "score", "target": ">80%"}],
        "inputs": [],
        "outputs": [],
    }
    harness_file = harness_dir / "harness.yml"
    harness_file.write_text(yaml.safe_dump(harness_data))

    venture_dir = tmp_path / "ventures" / "netso"
    venture_dir.mkdir(parents=True, exist_ok=True)
    venture_data = {
        "id": "VEN-NETSO-001",
        "name": "Netso Energy",
        "type": "venture",
        "status": "active",
        "version": "1.0.0",
        "identities": {"humans": []},
        "artifacts": {},
        "financial_constants": NETSO_FINANCIAL,
    }
    venture_file = venture_dir / "venture.yml"
    venture_file.write_text(yaml.safe_dump(venture_data))

    result = validate_all(
        harness_dir=harness_dir, venture_path=venture_file, verbose=False
    )

    assert result.ok
    assert result.manifests_validated == 2
    assert result.manifests_failed == 0
    assert len(result.errors) == 0
    assert len(result.warnings) == 0
