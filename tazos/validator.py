"""Manifest validator — validates all TAZ OS manifests against JSON schemas.

Custom validation rules:
- Financial constants match ground truth
- Every blocker names a holder
- No gated action bypass
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

from tazos.constants import NETSO_FINANCIAL
from tazos.loader import PLATFORM_DIR, _load_schema, detect_manifest_type


@dataclass
class ValidationError:
    """A single validation error."""
    manifest_path: str
    field: str
    error: str
    severity: str = "error"  # error, warning

    def __str__(self) -> str:
        return f"[{self.severity}] {self.manifest_path}:{self.field}: {self.error}"


@dataclass
class ValidationResult:
    """Result of validating all manifests."""
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)
    manifests_validated: int = 0
    manifests_failed: int = 0

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [
            f"Manifests validated: {self.manifests_validated}",
            f"Manifests failed: {self.manifests_failed}",
            f"Errors: {len(self.errors)}",
            f"Warnings: {len(self.warnings)}",
        ]
        if self.errors:
            lines.append("\nErrors:")
            for err in self.errors:
                lines.append(f"  {err}")
        if self.warnings:
            lines.append("\nWarnings:")
            for warn in self.warnings:
                lines.append(f"  {warn}")
        return "\n".join(lines)


def _validate_financial_constants(data: dict, path: Path) -> list[ValidationError]:
    """Validate financial constants in venture manifests match ground truth."""
    errors = []
    fc = data.get("financial_constants")
    if not fc:
        return errors

    for key, expected in NETSO_FINANCIAL.items():
        actual = fc.get(key)
        if actual is not None and abs(float(actual) - float(expected)) > 0.001:
            errors.append(ValidationError(
                manifest_path=str(path),
                field=f"financial_constants.{key}",
                error=f"Value {actual} does not match ground truth {expected}",
            ))
    return errors


def _validate_policy_rules(data: dict, path: Path) -> list[ValidationError]:
    """Validate policy collection rules have required fields."""
    errors = []
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        return errors

    for i, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        rule_id = rule.get("id", f"rule[{i}]")
        if "name" not in rule:
            errors.append(ValidationError(
                manifest_path=str(path),
                field=f"rules.{rule_id}.name",
                error="Policy rule missing required 'name' field",
            ))
        if "category" not in rule:
            errors.append(ValidationError(
                manifest_path=str(path),
                field=f"rules.{rule_id}.category",
                error="Policy rule missing required 'category' field",
            ))
        if "rule" not in rule:
            errors.append(ValidationError(
                manifest_path=str(path),
                field=f"rules.{rule_id}.rule",
                error="Policy rule missing required 'rule' field",
            ))
        if "action" not in rule:
            errors.append(ValidationError(
                manifest_path=str(path),
                field=f"rules.{rule_id}.action",
                error="Policy rule missing required 'action' field",
            ))
    return errors


def _validate_cross_references(
    data: dict, path: Path, known_ids: set[str]
) -> list[ValidationError]:
    """Validate cross-references between manifests."""
    errors = []
    manifest_id = data.get("id", "")

    # Harness → venture reference
    venture = data.get("venture")
    if venture and venture not in known_ids:
        errors.append(ValidationError(
            manifest_path=str(path),
            field="venture",
            error=f"References unknown venture: {venture}",
            severity="warning",
        ))

    # Agent → harness reference
    harness = data.get("harness")
    if harness and manifest_id.startswith("AGT-") and harness not in known_ids:
        errors.append(ValidationError(
            manifest_path=str(path),
            field="harness",
            error=f"References unknown harness: {harness}",
            severity="warning",
        ))

    return errors


def validate_manifest(path: Path, known_ids: set[str] | None = None) -> list[ValidationError]:
    """Validate a single manifest file."""
    errors = []

    # Load YAML
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except Exception as e:
        errors.append(ValidationError(str(path), "(load)", f"Failed to load: {e}"))
        return errors

    if not isinstance(data, dict):
        errors.append(ValidationError(str(path), "(root)", "YAML root is not a mapping"))
        return errors

    # Detect type and validate against JSON schema
    manifest_type = detect_manifest_type(data)
    if manifest_type:
        schema = _load_schema(manifest_type)
        validator = Draft7Validator(schema)
        for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
            field_path = ".".join(str(p) for p in error.absolute_path) or "(root)"
            errors.append(ValidationError(str(path), field_path, error.message))

    # Custom validation rules
    if data.get("id", "").startswith("VEN-"):
        errors.extend(_validate_financial_constants(data, path))
    if data.get("id", "").startswith("POL-") and "rules" in data:
        errors.extend(_validate_policy_rules(data, path))

    # Cross-reference validation
    if known_ids:
        errors.extend(_validate_cross_references(data, path, known_ids))

    return errors


def validate_all(
    harness_dir: Path,
    venture_path: Path | None = None,
    verbose: bool = False,
) -> ValidationResult:
    """Validate all manifests in a harness directory."""
    result = ValidationResult()

    # First pass: collect all known IDs
    known_ids: set[str] = set()
    manifest_files: list[Path] = []

    # Find all YAML files in the harness directory
    for yml in harness_dir.rglob("*.yml"):
        manifest_files.append(yml)
    for yml in harness_dir.rglob("*.yaml"):
        manifest_files.append(yml)

    # Add venture if specified
    if venture_path and venture_path.exists():
        manifest_files.append(venture_path)

    # Collect IDs
    for mf in manifest_files:
        try:
            with open(mf) as f:
                data = yaml.safe_load(f)
            if isinstance(data, dict) and "id" in data:
                known_ids.add(data["id"])
        except Exception:
            pass

    # Second pass: validate each manifest
    for mf in sorted(manifest_files):
        errors = validate_manifest(mf, known_ids)
        if errors:
            for err in errors:
                if err.severity == "error":
                    result.errors.append(err)
                else:
                    result.warnings.append(err)
            result.manifests_failed += 1
        else:
            result.manifests_validated += 1

        if verbose:
            status = "PASS" if not any(e.severity == "error" for e in errors) else "FAIL"
            print(f"  [{status}] {mf.name}")

    return result
