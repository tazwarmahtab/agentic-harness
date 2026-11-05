# v0.1 integration and contribution disposition
Date: 5 November 2026, Asia/Dhaka. Agent Infrastructure only.

## Pinned foundation
main observed at 066d180c75bee9fd2101820198b3b5858a6cc9d8.
This integration branch starts from PR9 head 4a49404d362017645c5d5c553ab09eb733dee1d9, two commits ahead of main. It is a candidate, not accepted production. The branch's existing application behavior has not been rerun in this session.

## Preserve and reconcile
| Contribution | Disposition for this candidate | Required next check |
|---|---|---|
| PR9 UI, scoped SQLite records, original files, revisions and review history | Retain as candidate foundation | Reproduce tests and browser workflow; adapt prospect-specific wording and defaults for generic infrastructure use |
| PR10 planning | Preserve as reference; do not treat old gates as release evidence | Reconcile older G0–G11 names with later plans |
| PR19 isolated durable journal | Preserve; defer global integration | Compare transactional boundaries with existing scoped store; do not introduce a second competing authority |
| PR21 hook kernel | Preserve; defer wiring unless v0.1 requires it | No execution authority inferred from schema validation |
| PR22 root-mutation repair | Retain safety repair for any reachable legacy shell path | Port with mocked-denial regressions; no arbitrary shell tools in the restricted pilot |
| PR23 approval and receipt repairs | Port required corrections after semantic reconciliation | Compare graph.py and test_fix03_approval_gating.py against PR9; retain both branches' requirements |

PR23 is six commits ahead of main and contains PR21 history. Do not reapply PR21 and PR22 as independent whole branches over PR23. PR9 and PR23 overlap at least in graph.py, tools.py and test_fix03_approval_gating.py; file overlap is not yet a proven textual merge conflict. PR19 is ten commits ahead of main with a separate journal and release-contract changes. No contribution is deleted by deferral.

Archive refs: archive/pre-v01-20261105-pr9-4a49404; archive/pre-v01-20261105-pr10-c72120d; archive/pre-v01-20261105-pr19-b543df3; archive/pre-v01-20261105-pr21-43fdae7; archive/pre-v01-20261105-pr22-e10eed9; archive/pre-v01-20261105-pr23-98529de.

## First usable release
Single-founder, nonconfidential infrastructure documents -> source-linked brief -> edit -> exact-revision review -> approved internal artifact export -> independent artifact readback -> persisted history after restart. This is a bounded first workflow toward Agent Harness, not a claim of a functioning autonomous multi-provider platform.

Current source does not yet implement approved export; prospect routes provide create/list/get/generate/review/edit/original download/history. Current workflow uses buyer/bill/roof/commercial questions. These must be generalized deliberately rather than silently mixing business context into infrastructure. Existing local extraction is evidence selection, not semantic agent reasoning.

Do not expose the wider legacy API as a hardened public service. Restricted pilot entry point must expose only its intended authenticated routes, with no arbitrary shell, outbound sending, live-model disclosure, new spend or public deployment. Keep host selection open until runner availability is verified.

## Next executable slice
Recover the full selected tree with integrity checks, install reproducible dependencies in an isolated permitted runner, and run existing scoped store/API/UI tests safely. Then create the restricted pilot entry point and generic document mode, followed by exact approved-export binding and readback tests. Preserve current tests; add coverage for scope mismatch, changed revision, rejection, expiry/replay, restart and duplicate/uncertain export.

Current environment only contains a recovered source subset and lacks pytest. Connected GitHub reads/writes work; CLI network/auth and independent review remain separate open requirements. Do not spend further iterations reporting the same unchanged blocker as delivery progress.

## Later improvement loop
After the founder can run three representative tasks: observe actual failures and friction, select one ranked improvement weekly, specify acceptance, implement one change, run fixed regressions and independent review, release a versioned candidate, observe and roll back on regression. Keep one change in progress; no automatic approval, scope expansion or self-promotion.
