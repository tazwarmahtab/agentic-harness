# Wayfinding: Agent Harness Gated First Pilot
**Status:** PROPOSED / UNCLAIMED · **Date:** 2026-11-01
**Tracker:** local Git Markdown · **Authority:** [Controlled Build Program](../../../docs/plans/2026-11-01-agent-harness-controlled-build-loop.md); map is coordination only.
**Destination:** human-approved target architecture and one complete evidence-backed *non-production* end-to-end controlled pilot.
**Frame:** existing Python AOS has running design and approval machinery, adjacent projects overlap, and baseline is not independently verified.
**Exit check:** G0–G8 signed off for pilot; specified tests pass; observed end-to-end run and rollback drill captured; no inferred production permission.

## Frontier (all currently unclaimed)
| Ticket | Type | One precise question / deliverable | Blocked by | Owner / next move | State |
|---|---|---|---|---|---|
| WF-001 | evidence | Which branch/PR is authoritative, and what fails on fresh baseline tests/CI? | none | GitHub + gstack Health | OPEN |
| WF-002 | evidence | Can an approval for one phase authorize a different phase/run? Demonstrate with failing test. | none | security/TDD review | OPEN |
| WF-003 | evidence | Which unique capabilities in Paperclip and TAZ_OS should be integrated rather than duplicated? | none | architecture comparison | OPEN |
| WF-004 | evidence | Are tracked state, docs, artifacts, paths, or repository metadata leaking secrets or stale domain assumptions? | none | security audit (redacted) | OPEN |
| WF-005 | decision | Accept first pilot, canonical repo/branch, scope and owner? | WF-001, WF-002 | human G0 | BLOCKED |
| WF-006 | decision | Which control-plane/worker/data boundary is accepted? | WF-003, WF-004, WF-005 | shaping + architecture ADR / human G3 | BLOCKED |
| WF-007 | prerequisite | How must scoped approvals, state resume, side effects and retries work contractually? | WF-002, WF-006 | statechart + interface contracts | BLOCKED |
| WF-008 | prototype | Can one synthetic end-to-end run meet G4–G8 with independent evidence? | WF-007 | executable breadboard + TDD implementation | BLOCKED |
| WF-009 | decision | Does evidence justify expanding to Netso/other domains or production? | WF-008 | human pilot acceptance | BLOCKED |

## Not yet specified (fog)
- Hosting choices and cost ceilings; real-user acceptance thresholds and comparative model benchmarks.
- Sensitive-data migration boundaries; connectors that may require separate permissions.
- Exact UI direction; do not scaffold or deploy a design not selected by a human.

## Out of scope
Production sends/deploys, capital or legal transactions, repository merges, bulk migration, live Netso financial calculations, privilege grants, and autonomous changes to connected accounts.

## Rules
- Investigate independent evidence tickets concurrently only when safe; acceptance and execution advance in dependency order.
- One ticket resolves one uncertainty, with source link and date; closed ticket != human promotion.
- Every material decision must be stored in the owning spec/ADR; this map is only the index.
- On denial, CI failure, missing evidence or approval mismatch: BLOCK, do not auto-advance.
- Reassess frontier after each accepted result; never assume unexecuted work is completed.

## Progress (2026-11-01)
- Repository inventory: partial, source-linked in main plan.
- WF-001 through WF-004: discovered evidence, **not closed** pending verification.
- Human gate G0: **PENDING**.
