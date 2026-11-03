"""Fail-closed, read-only validation of the Agent Harness release-gate register.

A report may only say "all green" after every registered gap has independent,
linked verification evidence. This validator deliberately grants no authority.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REGISTER = (
    Path(__file__).resolve().parents[1]
    / "docs/architecture/agent-harness-gap-register-2026-11-01.json"
)

GATE_MAP = {
    "G0": {"G09", "G10", "G13", "G26"},
    "G1": {"G01", "G02", "G03", "G04", "G05", "G07", "G16", "G25"},
    "G2": {"G11", "G12", "G19"},
    "G3": {"G06", "G14", "G15", "G18", "G22", "G23"},
    "G4": {"G20", "G31"},
    "G5": {"G17", "G24", "G27", "G28", "G29", "G30", "G32"},
    "G6": {"G08", "G21"},
}
ALLOWED_STATUSES = {"open", "in_progress", "blocked", "verified"}
EXPECTED_IDS = {f"G{i:02d}" for i in range(1, 33)}


class GateRegisterError(ValueError):
    """A register contradicts the published verification contract."""


def validate_register(data: Any) -> dict[str, Any]:
    """Return a derived progress summary or reject inconsistent claims."""
    if not isinstance(data, dict) or data.get("schema_version") != "1.0":
        raise GateRegisterError("unsupported release register schema")
    gaps = data.get("gaps")
    if not isinstance(gaps, list):
        raise GateRegisterError("gaps must be a list")
    ids: set[str] = set()
    per_gate: dict[str, set[str]] = {gate: set() for gate in GATE_MAP}
    verified = 0
    for item in gaps:
        if not isinstance(item, dict):
            raise GateRegisterError("gap must be an object")
        gap_id, gate, status = item.get("id"), item.get("gate"), item.get("status")
        if not isinstance(gap_id, str) or gap_id in ids:
            raise GateRegisterError(f"invalid or duplicate gap id: {gap_id}")
        ids.add(gap_id)
        if gate not in GATE_MAP:
            raise GateRegisterError(f"{gap_id}: unknown gate: {gate}")
        per_gate[gate].add(gap_id)
        if status not in ALLOWED_STATUSES:
            raise GateRegisterError(f"{gap_id}: unsupported status: {status}")
        if item.get("priority") not in {"P0", "P1", "P2"}:
            raise GateRegisterError(f"{gap_id}: missing priority")
        if not all(isinstance(item.get(key), str) and item[key].strip()
                   for key in ("title", "required_proof")):
            raise GateRegisterError(f"{gap_id}: missing title or required proof")
        evidence = item.get("evidence")
        if not isinstance(evidence, list):
            raise GateRegisterError(f"{gap_id}: evidence must be a list")
        if status == "verified":
            verification = item.get("verification")
            if not isinstance(verification, dict):
                raise GateRegisterError(f"{gap_id}: verified without verification")
            if not evidence or any(
                not isinstance(ref, dict)
                or not all(isinstance(ref.get(k), str) and ref[k].strip()
                           for k in ("ref", "fingerprint", "result"))
                for ref in evidence
            ):
                raise GateRegisterError(f"{gap_id}: verified without linked evidence")
            fields = ("commit_sha", "implemented_by", "verified_by", "verified_at", "test_summary")
            if not all(isinstance(verification.get(k), str) and verification[k].strip()
                       for k in fields):
                raise GateRegisterError(f"{gap_id}: incomplete verification receipt")
            if verification["implemented_by"] == verification["verified_by"]:
                raise GateRegisterError(f"{gap_id}: verification is not independent")
            verified += 1
    if ids != EXPECTED_IDS:
        raise GateRegisterError(f"gap coverage mismatch: missing={sorted(EXPECTED_IDS - ids)}")
    if per_gate != GATE_MAP:
        raise GateRegisterError("gate-to-gap mapping drifted from approved baseline")
    green = verified == len(EXPECTED_IDS)
    if type(data.get("all_gates_green")) is not bool or data["all_gates_green"] != green:
        raise GateRegisterError("all_gates_green must equal independently verified coverage")
    return {
        "registered_gaps": len(ids),
        "verified_gaps": verified,
        "total_gates": len(GATE_MAP),
        "all_gates_green": green,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=REGISTER)
    args = parser.parse_args()
    try:
        summary = validate_register(json.loads(args.path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, GateRegisterError) as exc:
        print(f"RELEASE GATE CONTRACT FAILED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
