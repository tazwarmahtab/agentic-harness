# Skill incident and regression ledger — append-only review template
Status: **TEMPLATE / EMPTY**. No incidents are marked resolved by this file.

A past error is never erased. Store public-safe metadata here, and sensitive evidence only in its authorized private workstream. A new revision creates a new row or linked correction rather than silently rewriting an old assessment.

## Minimum fields (required for every real incident)
- Incident ID / first-detected timestamp (UTC), owner and workstream
- Source locator + hash + access classification; affected skill and pinned revision
- Observed failure vs expected behavior and explicit blast radius
- **Reproduction:** exact inputs and commands or why a reproduction is blocked
- Root-cause hypothesis (not a claim without evidence)
- Containment / rollback; approval and side-effect status
- **Prevention test:** regression fixture, RED evidence, GREEN evidence
- **Independent review:** checker, exact SHA, evaluation rubric version, result
- **Recurrence:** follow-up trigger and latest observation, with UNKNOWN on sensor loss

## Register
| ID | Incident | State | Reproduction | Prevention test | Independent review | Recurrence |
|---|---|---|---|---|---|---|
| TEMPLATE-ONLY | Example / do not count as a real incident | NOT_RUN | Not attempted | Not attempted | Not attempted | UNKNOWN |

## Mistake-closure invariants
- A failing test that was later deleted or skipped is not a correction.
- Matching internal logs do not establish an external effect; require independent source readback.
- Incidents cannot close while telemetry is missing, evidence is tampered with or CI has no jobs.
- A skill under improvement cannot edit its evaluator, promotion policy or its own accepted baseline.
- A policy change requires distinct human approval. If authorization is unavailable, BLOCKED.
