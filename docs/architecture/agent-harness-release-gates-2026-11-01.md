# Agent Harness — Verified Release Gate Register

**Date:** 2026-11-01 (Asia/Dhaka). **Truthfulness:** These are tracked gates, NOT evidence of completion. **Current green count: 0/7.**

**Program:** [Issue #11](https://github.com/tazwarmahtab/agentic-harness/issues/11). **Existing consolidation:** [draft PR #9](https://github.com/tazwarmahtab/agentic-harness/pull/9), open/unmerged at review.

## Current blockers

- Current global entity index and event bus are in memory, not durable operational state.
- Local Git Brain could not be inventoried: connected Mac offline; prior local/remote histories diverge.
- GitHub commit status only showed CodeRabbit success; not a current full-repository CI pass.
- Supermemory connector returned zero accessible spaces; live memory/model/Convex integrations not established.
- Do not infer production release, external data disclosure, or Brain merge permission.

## Gates and assigned gap IDs

| Gate / GitHub ticket | Primary gap IDs | Depends on | Exit proof | State |
|---|---|---|---|---|
| [G0 #12](https://github.com/tazwarmahtab/agentic-harness/issues/12) | G09, G10, G13, G26 | none | Authority/source map; reconcile Brain read-only; hash and ACL all inventoried files; mark unknowns. | NOT GREEN |
| [G1 #13](https://github.com/tazwarmahtab/agentic-harness/issues/13) | G01, G02, G03, G04, G05, G07, G16, G25 | G0 | Transactional event and checkpoint recovery; version-bound approvals; wrong recipient and replay denied. | NOT GREEN |
| [G2 #14](https://github.com/tazwarmahtab/agentic-harness/issues/14) | G11, G12, G19 | G0,G1 | One source-linked temporal Netso decision; exact-revision founder review; test coverage visible. | NOT GREEN |
| [G3 #15](https://github.com/tazwarmahtab/agentic-harness/issues/15) | G06, G14, G15, G18, G22, G23 | G1,G2 | Blind agent A→B handoff after crash; no duplicates; revocation/injection/scope tests. | NOT GREEN |
| [G4 #16](https://github.com/tazwarmahtab/agentic-harness/issues/16) | G20, G31 | G1 | Canonical audit plus traces/outcomes; missing telemetry displays degraded, not green. | NOT GREEN |
| [G5 #17](https://github.com/tazwarmahtab/agentic-harness/issues/17) | G17, G24, G27, G28, G29, G30, G32 | G0,G2 | Hindsight/Supermemory/Jev/Laya/Convex/UX pilots against baseline on held-out data. | NOT GREEN |
| [G6 #18](https://github.com/tazwarmahtab/agentic-harness/issues/18) | G08, G21 | G1,G2,G3,G4,G5 | Restore, kill switch, security/supply-chain review, explicit founder pilot gate. | NOT GREEN |

## Bounded release loop

1. Select next unblocked issue in dependency order and capture fresh evidence/fingerprints.
2. Write a failing behavioral test first. Confirm that it fails for the expected reason.
3. Implement the smallest isolated change; pass focused tests; rerun relevant full CI and independent checker.
4. Record source/commit/test/evaluator links on the ticket. Do not close from model self-rating.
5. Reconcile replay/idempotency and authority; mark green only when ALL acceptance criteria are independently evidenced.
6. Stop and escalate at an irreversible action, credential change, broad external disclosure, migration or production promotion.

## Non-negotiable authority rules

- GitHub code and PRs, human source docs, and canonical operational state have distinct declared owners.
- Jev/Laya, Hindsight/Supermemory, Convex projections and generated UI must NEVER grant tool authority.
- Source citations and timestamps track provenance, not truth; contradictory/historical records remain explicit.
- A complete audit is not possible while sources are inaccessible; report missing coverage rather than manufacturing green.
- Approval binds actor, scope, decision revision, evidence version, exact proposed payload and recipient, and expiry.
- Critical audit events are durable and never replaced by sampled telemetry.

## Review references

- [Earlier implementation design](https://github.com/tazwarmahtab/agentic-harness/blob/feat/founder-os-prospect-workflow-20261030/docs/architecture/founder-os-next-design.md)
- [Main entity index](https://github.com/tazwarmahtab/agentic-harness/blob/main/aos/entity_index.py)
- [Main in-process event bus](https://github.com/tazwarmahtab/agentic-harness/blob/main/aos/event_bus.py)
- Gap register v0.1: G01–G32 mapped exactly once above. Each issue specifies its detailed tests.
