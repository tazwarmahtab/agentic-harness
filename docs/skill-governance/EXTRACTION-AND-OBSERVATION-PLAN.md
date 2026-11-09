# Agent Harness → Little Space: observed-workflow and reusable-skill extraction plan
As of 2026-11-09. **Proposal in review**; this document is not a new task-state authority.

## Trust boundaries and sources
- This public repository's original seven-gate program [#11](https://github.com/tazwarmahtab/agentic-harness/issues/11) remains the release gate of record. [#12](https://github.com/tazwarmahtab/agentic-harness/issues/12) source provenance → [#13](https://github.com/tazwarmahtab/agentic-harness/issues/13) durable contracts → [#15](https://github.com/tazwarmahtab/agentic-harness/issues/15) handoff → [#16](https://github.com/tazwarmahtab/agentic-harness/issues/16) Observatory → [#18](https://github.com/tazwarmahtab/agentic-harness/issues/18) pilot security. G2/G5 remain separate scoped evaluations.
- The Little Space 92-gap list is a distinct design register from the older Agent Harness 32-gap/G0–G6 issues; maintain cross-references, never silently merge or declare coverage.
- User-requested cross-conversation extraction is only **partially sourced**. Historical chat summaries and known audit files surfaced candidates; inaccessible original chats, private local skills, local Brain, full 92-gap register, and every attached artifact are still UNKNOWN until inventoried by G0. Do not assert complete historical extraction.
- Existing skill creator guidance was consulted from [Anthropic's public Skill Creator](https://github.com/anthropics/skills/blob/main/skills/skill-creator/SKILL.md). It is reference material, not proof that the skill is installed or its evaluation runner has been executed.
- Never copy private business, client, health, credentials, memories, or secret data into this public repository. No broad cross-workstream memory grants.

## Priority inventory (candidate extraction — not promoted)
| Rank | Workflow / recurring mistake class | Decision | Existing / dependency | Minimum proof |
|---|---|---|---|---|
| P0 | Verified task execution and return-to-check | REUSE / VERIFY | Existing Verified Workflow Loop is reported in prior context; source and current hash need inspection | Pinned baseline, exact test receipt, output vs external source |
| P0 | Reusable skill creation, vetting and promotion | CANDIDATE | `skills/skill-vetting-observer` in this branch | Static checks, triggered/non-triggered behavioral tests, independent reviewer, library install receipt |
| P0 | Cross-workspace scope and exact-action approval | ADAPT / TEST | G1 #13 and Little Space GAP-020/018/025 | Wrong-target and stale/replay tests, no escalation |
| P0 | Independent external-state read-back | ADAPT / TEST | G4 #16, GAP-091 | Source-system read after action, forged receipt rejection |
| P0 | One logical control plane for journal/queue/approvals | BUILD CONTRACT | G1 #13, GAP-092 | Crash/concurrency/replay, single authoritative revision |
| P0 | Observatory and observation self-health | BUILD | G4 #16, candidate observational contract | Collector-loss faults, discrepancy escalation, UNKNOWN not green |
| P1 | Systematic debugging and non-recurrence ledger | REUSE + ADAPT | Existing TDD / debugging standards | RED→GREEN regression, independent review, recurrence observation |
| P1 | Multi-agent delegation and independent critic | ADAPT | G3 #15 | Authenticated checkpoint handoff, reviewer separation |
| P1 | Source inventory and skill retrieval provenance | ADAPT | G0 #12 | Hash/ACL/freshness inventory and source conflict detection |
| P1 | UI fidelity and real-device runtime QA | REUSE | Existing code review/browser skills | Screenshot comparison and mobile accessibility checks |
| P2 | Voice/avatar provider benchmarking | DEFER | Realtime call requirements | Live p95 latency, media permission, rejoin, thermal/cost data |
| P2 | Vendor/model routing and context evaluation | DEFER | G5 #17 | Held-out queries, costs, scope, deletion and abstention |

## One observation and improvement loop
```
Source inventory + accepted constraints
   ↓
Small exact-revision task contract
   ↓
RED regression or negative permission test
   ↓
Implement minimal candidate in isolated branch
   ↓
Deterministic checks → representative eval → held-out eval
   ↓
Independent reviewer checks source, runtime, evidence and effects
   ↓
Human gate for external effects or promotion
   ↓
One authoritative journal records execution and source-system read-back
   ↓
Observatory checks signals, trace gaps, failures, budgets, drift, blind spots
   ↓
Incident? → containment + immutable record + RED prevention test
   ↳ next bounded iteration, never edit accepted policy/rubric in same run
```

## Observatory's blind-spot detectors
- **Truth:** internal-completed but external-unchanged; stale receipts; missing source read-back; replay and duplicate effects.
- **Authority:** wrong actor, wrong workstream, expired/replayed grants, uncommitted offline writes falsely displayed as committed.
- **Health:** dead collector, event gap, missed heartbeat, CI startup failures, missing job logs, unobservable execution and audit integrity checks.
- **Quality:** regression fixture failures, benchmark drift, unsourced claims, error recurrence, independent reviewer disagreement.
- **Operations:** error budgets, run cost and tool quotas, lock/queue congestion, stale skills, unbounded recursion and privacy/redaction errors.
- **UX:** call/approval/handoff continuity, mobile parity, keyboard/focus and invalid status semantics.

## Rules for a green gate
- exact SHA and source provenance with valid ACL
- executable command/output, positive and adversarial negative tests
- independent reviewer not assuming author conclusions
- externally verifiable source observation for any external effect
- observatory signals healthy and tested under failure injection
- no suppressed/removed checks to obtain a green verdict
- rollback/recovery proof and human approval where the action changes permissions, policies, skills shared with others, external records or production

## Current operational blockers / next order
1. Resolve [GitHub Actions startup issue #20](https://github.com/tazwarmahtab/agentic-harness/issues/20) with first real job-step logs. Local reconstruction or builds alone cannot close it.
2. Reconcile available prior skill source against saved baseline **read-only**. Verify hash/version/ownership; if missing, mark BLOCKED and leave candidate unpromoted.
3. Run this skill's static validator and unit tests at exact branch SHA, then behavioral evaluations on held-out scenarios with a separate reviewer. This branch deliberately changes no operational control plane.
4. Choose a secure persistent runtime with authenticated identity, workspace authorization and durable task state before any live agent action. Do not bypass hostname guards.
5. Only after G0/G1 proof, implement one bounded source → proposal → exact-action approval → authorized change → external read-back → incident/receipt → preserved task resume.

## Non-goals of this PR
No replacing existing operating agent framework, no actual self-updating skills, no production deployment, no data migration or public marketplace listing. A committed `SKILL.md` is a versioned **candidate**, not a user's installed ChatGPT skill.
