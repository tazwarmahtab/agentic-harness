# Agent Harness / FounderOS — Controlled End-to-End Build Program
**Prepared:** 2026-11-01 · **Status:** PROPOSED — NOT APPROVED FOR MERGE OR PRODUCTION
**Candidate integration repository:** `tazwarmahtab/agentic-harness` (main)
**Adjacent systems to assess, not silently absorb:** `tazwarmahtab/ai-company-os`, `tazwarmahtab/TAZ_OS`
**Change policy:** Non-destructive, review-first. Existing software and business data remain authoritative until reconciled by a human.

## 1. Objective, boundaries, and definition of finished
Deliver a reproducible, governed agent operating system that takes an authorized request through discovery, research, shaping, specification, implementation, validation, independent review, explicit approval, staged release, and measured improvement. Business domains remain isolated; the operator must be able to understand, interrupt, reject, resume, roll back, and audit a run.

**First bounded destination (G0):** an accepted target architecture plus one fully demonstrated, fail-closed vertical workflow (synthetic input → plan → implementation sandbox → independent checks → exact-action approval → non-production completion → immutable evidence). Do not claim a whole multi-venture production OS is finished when only a pilot passes.

**Non-goals for the pilot:** merging repos; replacing current financial models; creating real client communications; transferring secrets; live financial decisions; autonomous merge or deployment; importing private documents into a public repository; adding a new UI without a selected visual target.

## 2. Evidence inventory (2026-11-01, read-only)
| Source | Observed evidence | Consequence |
|---|---|---|
| [agentic-harness README](https://github.com/tazwarmahtab/agentic-harness/blob/main/README.md) | Python AOS, LangGraph, FastAPI, approval queue, evaluator, existing 13 harness bundles; README claims 696 tests | Preserve existing runtime; verify claims locally/CI before reuse. |
| [AOS CLAUDE.md](https://github.com/tazwarmahtab/agentic-harness/blob/main/CLAUDE.md) | Says ~1050 tests, 60% coverage floor, strong policy assumptions | Documentation disagrees on test count; measure actual collection. |
| [AOS gates.py](https://github.com/tazwarmahtab/agentic-harness/blob/main/aos/orchestrate/gates.py) and [autonomous.py](https://github.com/tazwarmahtab/agentic-harness/blob/main/aos/orchestrate/autonomous.py) | Gate lookups are by gate category; phase loop queries a generic SPEC decision | **Potential P0:** approved decision may be reused outside its intended phase. Prove with failing regression tests before edits. |
| [AOS ROADMAP](https://github.com/tazwarmahtab/agentic-harness/blob/main/ROADMAP.md) | Older Netso transaction assumptions and deadlines | Quarantine from autonomous external generation pending current-domain owner reconciliation; do not silently overwrite. |
| [AI Company OS](https://github.com/tazwarmahtab/ai-company-os) | Separate TypeScript control plane with task, approval, budget, adapters, web UI and tests | Compare capability-by-capability. Reuse behind contracts, not wholesale porting. |
| [TAZ OS](https://github.com/tazwarmahtab/TAZ_OS) | Python contracts, loops, Netso skills and tests | Audit for unique behavior and domain staleness before adaptation. |
| [Existing PR #9](https://github.com/tazwarmahtab/agentic-harness/pull/9) | FounderOS prospect workflow in progress | Coordinate non-conflicting changes; do not overwrite branch or assume it is merged. |
| [Recent AOS CI run](https://github.com/tazwarmahtab/agentic-harness/actions/runs/41170083686) | 2026-10-31 feature-branch test, lint and evaluator jobs failed | CI is not green on that feature branch. Identify actual failure causes; do not generalize to main. |
| Git tree on main | Contains tracked session-state paths and unusual `]` directory | Inspect repository hygiene and secret exposure *without reproducing sensitive content*. |

These are evidence-based observations, **not** a completed security audit, fresh test execution, runtime benchmark, or certification.

## 3. Architecture under evaluation (not a committed migration)
- **Control plane**: authenticated operator, task ledger, policies, approval records, progress and audit views.
- **Execution plane**: orchestrator, typed task contracts, deterministic routing, isolated workers, bounded retries, checkpoint/resume, idempotency keys.
- **Tool boundary**: centrally enforced capability grants, per-venture tenant isolation, allowed operations and paths, timeouts, network boundaries, egress logging.
- **Knowledge plane**: source-of-truth Git + structured operational DB + permission-filtered document store/retrieval; separate ephemeral working context; secrets only in secret manager.
- **Assurance plane**: unit/integration/contract/security/eval suites, provenance, trace review, independent reviewer, staged canary, rollback.
- **Business domains**: plug-ins/adapters with owners and versioned interfaces; no assumption that old Netso numbers or deal structures remain current.

Avoid premature microservices and automatic 'more agents = better' scaling. Use one coordinator unless a benchmark demonstrates specialist orchestration benefit.

## 4. Finite state machine for each approved work slice
```text
INTAKE -> TRIAGED -> EVIDENCE_READY -> SHAPED -> DESIGN_PENDING
-> DESIGN_APPROVED -> CONTRACTED -> TEST_RED -> IMPLEMENTING
-> TEST_GREEN -> INDEPENDENT_REVIEW -> RELEASE_PENDING
-> STAGING -> ACCEPTANCE -> RELEASED -> MONITORING -> CLOSED

Any state -> BLOCKED  (missing dependency, denial, ambiguous authority)
Review failure -> CORRECTION  (bounded: at most 3 attempts per defect)
CORRECTION -> TEST_RED      (new regression) -> IMPLEMENTING
Any production side effect -> exact-action approval first
Denial/timeout/unsafe state -> STOPPED, no execution, preserved evidence
```
Every transition persists `run_id`, `slice_id`, state version, actor, input artifact digests, approved action digest, attempted tool calls, timestamps (UTC), evidence links, and reason; optimistic concurrency prevents double advancement. Resume from a stored checkpoint, never replay a non-idempotent external side effect. A complete phase requires successful objective checks **and** its correct human gate.

## 5. Sequential stages and exit controls
| Stage | Work and plugin/role | Required output | Gate to advance |
|---|---|---|---|
| S00 Baseline | GitHub + gstack Health: inspect branches/PRs, collect tests, CI failures, security inventory, instructions | Baseline report with reproducible commands, known defects, gaps | G0: operator accepts target repo, branch, scope and constraints |
| S01 Framing | Planning Skills framing/shaping; define user, outcome, risks, non-goals, appetite and success | Accepted frame and risk register | G1: human accepts frame, affected repos, no accidental external changes |
| S02 Evidence | Source-graded research, Agentic Atlas, OWASP, MCP, competitor/architecture alternatives | Source ledger, option matrix, dated assumptions, prototype questions | G2: unknowns resolved or explicitly bounded |
| S03 Architecture | Architecture decision record, threat model, data-flow, tenancy and contracts | Accepted architecture and migration map | G3: human selects architecture and migration strategy |
| S04 Contracting | Statechart, interface-contracts, executable breadboards, fixture corpus | Versioned schemas, invariants, failure matrix, red tests | G4: all high-risk cases have test oracle |
| S05 Build | TDD, smallest vertical slice, isolated branch, synthetic fixtures, deterministic controls | Code + tests + changelog + reproducible runbook | G5: tests, typing, lint and evaluator green on branch |
| S06 Adversarial QA | gstack Health, OWASP mapping, prompt injection and privilege tests, dependency checks | Findings with severity, exact reproductions, fixes | G6: zero unresolved P0/P1 on approved scope |
| S07 Independent review | Separate reviewer/agent with task contract and no ability to self-approve | Independent review report + diff evidence | G7: release candidate accepted by authorized human |
| S08 Staging | Protected CI, migration rehearsal, synthetic load/fault/restart, restore/rollback | Staging trace, migration backup, observability evidence | G8: acceptance and rollback drills passed |
| S09 Pilot | One low-risk business workflow under observation, human approval for effects | Measured task, intervention, failure, cost and latency results | G9: owner accepts results and domain correctness |
| S10 Production | Least-privilege credentials, staged promotion, smoke test, operational docs | Versioned release and signed release record | G10: explicit human deployment decision |
| S11 Improve | Trace → failure classification → reproducible eval → ranked changes → TDD PR → rerun same evals | Updated measured baseline and next prioritized slice | G11: no regression; repeat only while change has justified benefit |

**Gates are binding.** An agent recommendation, passing test, old approval, `--auto` flag, or PR approval is not authorization for a different action, scope or deployment.

## 6. Non-negotiable acceptance tests for first vertical slice
1. **Approval binding:** `decision(run A, phase 1, action digest X)` cannot authorize phase 2, run B, or digest Y; approvals have identity, expiry and replay protection.
2. **Fail closed:** missing/rejected/timed-out approval prevents effects and writes a reason. `--auto` cannot override mandatory production gates. Dry run cannot report actual ship.
3. **Cross-tenant:** a Netso-scoped agent cannot read/write a separate venture's data.
4. **Untrusted input:** adversarial documents, webpages and tool results cannot change policy or invoke forbidden tools.
5. **Resumability:** interrupted run resumes from checkpoint without duplicate outgoing effects.
6. **Evaluation:** deterministic contract checks; benchmark corpus includes success, malformed input, tool errors, denial, crash, retries and realistic failure cases.
7. **Release:** required branch CI jobs pass; no P0/P1 open; an independent reviewer validates the changed surface; rollback demonstration succeeds.
8. **Evidence:** every gate and execution has attributable trace and source links; sensitive payloads are appropriately redacted.
9. **Measure before optimizing:** record completion success, approval integrity, false-positive/negative gate decisions, task cost, end-to-end latency and manual interventions. Set thresholds after a measured baseline; no invented accuracy or reliability claims.

## 7. Work packages and dependency/ownership sequence
- **W00 (now; read-only):** confirm baseline branch, PR #9 overlap, CI failure triage, security and leak exposure scan.
- **W01 (first blocking fix):** approval identity/phase isolation + fail-closed tests. Only after G0/G1.
- **W02:** canonical task, run, decision and event schemas; migration and backwards-compat tests.
- **W03:** worker sandbox + capability policy enforcement at tool gateway.
- **W04:** durable checkpoint/retry/idempotency model.
- **W05:** versioned evaluator fixture registry, traces, independent reviewer.
- **W06:** CLI/operator experience and error recovery; UI improvements only after a selected design and UX review.
- **W07:** first Netso synthetic pilot with up-to-date approved assumptions.
- **W08:** adapters into TAZ_OS/Paperclip where justified by test-backed compatibility; no dual source-of-truth.
- **W09:** staging→canary→production promotion controls, restore drills and operations runbooks.
- **W10:** continuous improvement loop on real, permissioned feedback.

## 8. Operator protocol for every iteration
1. Recover the latest accepted source and decision log; claim one unblocked work package.
2. Record `run_id`, scope, owner, evidence, versioned acceptance contract and expected side effects.
3. Investigate; publish uncertain facts and alternatives, not invented certainty.
4. Obtain necessary human gate before binding scope, granting capability, sending, merging or deployment.
5. Write failing tests (red) before fixing behavior; make minimal change.
6. Run targeted tests → broader tests → security/evals; retain commands, exit codes and commit.
7. Obtain independent review; on failure, classify defect, add regression and retry up to 3 times. Beyond this: BLOCK and escalate.
8. Write PR with changed files, reasons, evidence, risk and rollback; never merge unapproved.
9. Observe released behavior; compare against baseline; prioritize next *measurable* failure.
10. Stop when bounded exit criteria are met, work is blocked, risk is unacceptable, or next slice is not worth its cost. Do not interpret 'loop' as endless unsupervised work.

## 9. Decision register requiring human acceptance
- **D00:** confirm `agentic-harness` main as integration target versus feature PR, and define one pilot workflow.
- **D01:** choose interoperability vs consolidation with `ai-company-os` and `TAZ_OS` only after capability audit.
- **D02:** set governance tier for production deployment, external messages, money/legal actions and credentials.
- **D03:** confirm updated Netso authoritative business assumptions and forbid generation from superseded documents.
- **D04:** choose persistence, hosting and operating-budget constraints after an architecture/ops comparison.

## 10. Current progress and explicit limitations
- **Done:** repository discovery, initial architecture/security review, source-linked plan, control-loop and gates drafted.
- **Not done:** executed full local test suite, CI repair, secret scan, approval fix, migration, full product build, staging or production verification.
- **Current blockers:** human decision G0; feature-branch CI failures; unproven phase-isolation risk; domain assumptions require revalidation.
- **Next precise action:** perform W00 reproducible baseline and create a regression test for cross-phase approval reuse, without changing live behaviors until G0/G1.

## Research/standards used as design constraints
- [OWASP Top 10 for Agentic Applications (2026)](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/)
- [OpenAI agent guardrails and approvals](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals)
- [OpenAI agent improvement loop (traces, evals, Codex)](https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop)
- [MCP authorization specification, 2025-11-25](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2025-11-25/basic/authorization.mdx)
