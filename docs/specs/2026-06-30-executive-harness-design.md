# TAZ OS — Executive Harness Design

- **Date:** 2026-06-30
- **Status:** Approved (design); manifests in progress
- **Venture instance:** Netso Energy
- **Author:** Taz + TAZ OS architecture work
- **Supersedes (gradually):** `Netso_HQ/ai_system/` v0 (Nexus + PLAN/DO/CHECK/ACT)

---

## 1. Purpose

The Executive Harness is the **reference implementation** of TAZ OS. It is the first harness built on the canonical template; every later harness (Sales, Finance, Engineering, Legal, Operations, Customer Success, Marketing, Research, Knowledge, Investor Relations, Personal) inherits this structure unchanged.

It operates Netso Energy as an autonomous executive team: continuously monitors the company, identifies priorities, coordinates specialist harnesses, and surfaces only high-leverage decisions requiring founder approval.

## 2. Key Decisions (locked)

| # | Decision | Choice |
|---|----------|--------|
| D1 | Deliverable | Declarative YAML manifests + JSON Schema validation |
| D2 | Relationship to existing org | **Re-home & unify** — not greenfield, not parallel |
| D3 | Repo home | Standalone git repo at `Agentic Harness/`; Netso mounted as venture |
| D4 | Format | YAML manifests (machine-readable), no runtime code yet |
| D5 | Scope | Executive Harness only. No other harnesses yet. Netso only. |

### D2 in detail — Re-home & unify

The existing `Netso_HQ/ai_system/` workforce is **not** thrown away. It is re-homed as the Executive Harness's specialists:

| Existing persona | Re-homed as | Notes |
|---|---|---|
| LILTAZ | Planner + Dispatcher core | Orchestrator stays the brain |
| ATLAS | COO specialist | Operations, execution, deadlines |
| MINERVA | CFO specialist | Cash, forecasts, investor reporting |
| SHIELD | **Splits** → Legal Officer + Risk Officer | Legal and risk are distinct seats |
| LENS | Performance Analyst specialist | KPIs, forecasts, execution velocity |
| COUNCIL | Deliberation escalation tier | Invoked on high-risk / strategic decisions — not a specialist seat |
| *(new)* | Chief of Staff specialist | Meeting prep, follow-ups, decision log — currently a gap |

Tier-2 specialists (SPARK, AURUM, SIGNAL, FORGE, NEXUS, BEACON, SCRY, CRAFT, CANVAS, VOICE, PRISM, PIPE, SCRIBE) **stay where they are.** They belong to other harnesses (Finance, Sales, Ops, Legal, Marketing, Research) and are routed to *by* the Executive Harness's dispatcher — not owned by it.

The existing PLAN/DO/CHECK/ACT files become the harness's **live shared memory + outputs**, not duplicated.

## 3. Architecture

```
Founder (HUM-000001)
        │
        ▼
┌─────────────────────────────────────────┐
│            EXECUTIVE HARNESS             │
│                                          │
│   Planner ◄──── Dispatcher ◄──── Memory  │
│      │             │            ▲        │
│      ▼             │            │        │
│   Priorities    Routes to       │        │
│                 specialists     │        │
│      │             │            │        │
│      ▼             ▼            │        │
│   Decision ◄── Approval ◄───────┤        │
│     Queue       Gates           │        │
│      │                          │        │
│      ▼                          │        │
│   Outputs ──────────────────────┘        │
│   (brief, weekly, board, decisions)      │
└──────────────────────────────────────────┘
        │ dispatch (cross-harness)
        ▼
  Sales │ Finance │ Engineering │ Legal │ Ops │ ...
```

## 4. Canonical Template Coverage (14 manifests)

| # | Manifest | Template part |
|---|----------|---------------|
| 1 | `harness.yml` | Mission, Scope, KPIs, Inputs, Outputs |
| 2 | `planner.yml` | Planner |
| 3 | `dispatcher.yml` | Dispatcher |
| 4 | `specialists/ceo.yml` | CEO Agent |
| 5 | `specialists/coo.yml` | COO Agent (← ATLAS) |
| 6 | `specialists/cfo.yml` | CFO Agent (← MINERVA) |
| 7 | `specialists/chief-of-staff.yml` | Chief of Staff (new) |
| 8 | `specialists/legal-officer.yml` | Legal Officer (← SHIELD) |
| 9 | `specialists/risk-officer.yml` | Risk Officer (← SHIELD split) |
| 10 | `specialists/performance-analyst.yml` | Performance Analyst (← LENS) |
| 11 | `memory.yml` | Shared Memory (perms + Netso refs) |
| 12 | `tools.yml` | Tools (capabilities + perms) |
| 13 | `approvals.yml` | Approval Gates |
| 14 | `evaluation.yml` | Evaluation Metrics + Continuous Improvement |

Supporting: 4 SOP files in `sops/`.

## 5. Grounding in Real Artifacts

Manifests **reference**, never duplicate:

| Source (Netso_HQ) | Used as |
|---|---|
| `GROUND_TRUTH_CONSTANTS.md` | CFO canonical source; evaluation hard-fails blended-rate savings |
| `DO/DASHBOARD.md` | Live state memory (single source of truth) |
| `PLAN/WEEKLY.md`, `PLAN/BACKLOG.md` | Planner inputs |
| `ACT/BLOCKERS.md`, `ACT/LESSONS.md` | Risk Officer + Continuous Improvement inputs |
| `CHECK/REVIEW.md` | Continuous Improvement Loop input |
| `AGENTS_REGISTRY.md`, `TASK_ROUTER.md` | Dispatcher routing table source |
| `Nexus/logs/handoffs/` | Inter-harness handoff channel |
| `agents/*.md` (16 personas) | Specialist persona source — referenced by `source_persona` field |
| `scripts/core_economics.py` | Financial ground-truth generator |

## 6. Approval Gates (concrete thresholds)

Pulled from `GROUND_TRUTH_CONSTANTS.md` + `TASK_ROUTER.md` escalation rules:

| Trigger | Gate | Owner |
|---|---|---|
| Proposal > BDT 5,000,000 | Founder approval | Founder |
| Any external investor communication | Founder approval | Founder |
| Contract signature (LOI/PPA/EPC) | Founder approval | Founder |
| DSCR < 2.25x (Scenario A) | Escalate to Founder + CFO | Risk Officer |
| DSCR < 2.0x | Immediate alert (from TASK_ROUTER) | Risk Officer |
| Procurement PO | Founder approval | Founder |
| SREDA/IDCOL/NBR submission | Founder approval | Founder |
| Routing: schedule / summarize / draft | Auto (no gate) | Runtime |
| Routing: send / sign / commit | Gated | Runtime |

## 7. Scope Fence (what this is NOT)

- **No runtime code yet.** Manifests are declarative. A future runtime consumes them.
- **No other harnesses yet.** Sales/Finance/Engineering come after this is validated as the reference.
- **No other ventures yet.** Netso only. TransitBD mounts later via the same `ventures/` pattern.
- **No reimplementation of Tier-2 agents.** SPARK/AURUM/etc. keep running as-is; the dispatcher routes to them.

## 8. Success Criteria

The Executive Harness is "done" when:
1. All 14 manifests pass JSON Schema validation.
2. Every existing persona (LILTAZ/ATLAS/MINERVA/SHIELD/LENS) has a clear re-home path documented in its manifest.
3. Approval gates reference real thresholds from GROUND_TRUTH_CONSTANTS.
4. A reader can trace any decision the harness makes back to either a manifest rule or a founder approval.
5. The structure is **copyable** to build the Knowledge Harness next (the test of "reference implementation").

## 9. Next Steps

1. Write platform JSON Schemas (identity, harness, agent, tool, policy, memory, data-model).
2. Write Netso venture binding (`ventures/netso/venture.yml`).
3. Write all 14 Executive Harness manifests.
4. Self-review (placeholders, consistency, scope, ambiguity).
5. Hand to founder for review.
6. Invoke `writing-plans` for implementation plan (runtime build).

## 10. Open Questions for Founder Review

These are noted, not blocking — flag during review:
- Q1: Should the founder approval channel be Slack/WhatsApp/email/console? (Default assumption: console queue, human acts.)
- Q2: COUNCIL invocation threshold — automatic above a risk score, or founder-triggered? (Default: risk score driven, founder can override.)
- Q3: Should `chief-of-staff.yml` own the decision log, or should that live in shared memory? (Default: owns it, writes to memory.)
