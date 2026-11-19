#!/usr/bin/env python3
"""Deterministic candidate-skill schema and policy-presence checks.

This is a cheap static gate, NOT a behavioral eval, prompt-injection sandbox,
external verification, or permission/authorization system.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    base = root / "skills" / "skill-vetting-observer"
    skill = base / "SKILL.md"
    manifest_path = base / "manifest.json"
    eval_path = base / "references" / "eval-cases.json"
    ledger_path = root / "docs" / "skill-governance" / "INCIDENT-LEDGER.md"

    for p in (skill, manifest_path, eval_path, ledger_path):
        if not p.is_file():
            errors.append(f"missing required file: {p.relative_to(root)}")
    if errors:
        return errors

    text = skill.read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        errors.append("SKILL.md needs YAML frontmatter")
    else:
        frontmatter = text.split("\n---\n", 1)[0].removeprefix("---\n")
        fields = dict(
            (key.strip(), value.strip())
            for key, value in re.findall(r"(?m)^([a-z_]+):\s*(.*)$", frontmatter)
        )
        if fields.get("name") != "skill-vetting-observer":
            errors.append("frontmatter name differs from directory")
        if len(fields.get("description", "")) < 75:
            errors.append("trigger description too short")

    if len(text.splitlines()) > 500:
        errors.append("SKILL.md exceeds progressive-disclosure length")
    required_sections = ["## LOOK", "## SPEC", "## VET", "## OBSERVE", "## CHECK", "**Not for:**"]
    for section in required_sections:
        if section not in text:
            errors.append(f"missing lifecycle section: {section}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        return errors + [f"manifest invalid JSON: {exc}"]
    if not isinstance(manifest, dict):
        return errors + ["manifest must be a JSON object"]
    if manifest.get("name") != "skill-vetting-observer":
        errors.append("manifest skill name mismatch")
    if manifest.get("status") != "candidate_not_installed":
        errors.append("candidate must not self-report promoted/installed")
    if manifest.get("workstream") != "agent-infrastructure":
        errors.append("manifest workstream must be agent-infrastructure")
    approvals = manifest.get("requires_human_approval", [])
    if not isinstance(approvals, list) or not any("promotion" in x for x in approvals if isinstance(x, str)):
        errors.append("promotion needs explicit human approval")
    if manifest.get("external_verification") != "required for claims about external outcomes":
        errors.append("external outcome verification policy missing")
    for field, message in (
        ("not_for", "negative usage scope missing or malformed"),
        ("side_effects", "side effect disclosure missing or malformed"),
    ):
        values = manifest.get(field)
        if not isinstance(values, list) or not values or not all(
            isinstance(value, str) and value.strip() for value in values
        ):
            errors.append(message)

    try:
        suite = json.loads(eval_path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        return errors + [f"evaluation fixture JSON invalid: {exc}"]
    if not isinstance(suite, dict):
        return errors + ["evaluation fixture must be a JSON object"]
    cases = suite.get("cases", [])
    if suite.get("schema_version") != 1 or not isinstance(cases, list) or len(cases) < 8:
        errors.append("eval suite must have v1 schema and >=8 cases")
        return errors
    ids: set[str] = set()
    nontriggers = 0
    critical = 0
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"case {index} is not an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not re.fullmatch(r"C\d{2,}", case_id):
            errors.append(f"case {index} invalid ID")
        elif case_id in ids:
            errors.append(f"duplicate case ID {case_id}")
        else:
            ids.add(case_id)
        if not isinstance(case.get("should_trigger"), bool):
            errors.append(f"case {index} missing boolean trigger expectation")
        prompt = case.get("input")
        expected = case.get("expected")
        if (
            not isinstance(prompt, str)
            or not prompt.strip()
            or not isinstance(expected, list)
            or not expected
            or not all(isinstance(item, str) and item.strip() for item in expected)
        ):
            errors.append(f"case {index} missing prompt/expected assertions")
        nontriggers += case.get("should_trigger") is False
        critical += case.get("risk") == "critical"
    if nontriggers < 2:
        errors.append("need >=2 non-trigger cases")
    if critical < 2:
        errors.append("need >=2 critical-risk cases")
    incident = ledger_path.read_text(encoding="utf-8")
    for field in ("Reproduction", "Prevention test", "Independent review", "Recurrence"):
        if field not in incident:
            errors.append(f"incident ledger missing field {field!r}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    issues = validate(args.root)
    if issues:
        for item in issues:
            print(f"FAIL: {item}")
        return 2
    print("PASS: candidate skill static contract (NOT behavioral verification or promotion)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
