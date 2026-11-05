# v0.1 task checklist

5 November 2026. All tasks pending; no task completed by writing this plan. See tasks/plan.md for scope and contracts.

## T1: Recover pinned full candidate
- [ ] Complete and verify T1.

**Description:** Recover pinned full candidate for the single-founder infrastructure pilot.
**Dependencies:** None.
**Likely files:** checkout/recovery inventory.
**Scope:** No more than 5 paths; source recovery is an operation, not a mass edit; split further if implementation exceeds five files or one focused session.
**Acceptance:** Full candidate tree verified against Git identities; all applicable instructions inspected; accessible local edits recorded without overwrite.
**Verification:** Verify recovered inventory and original/archive references; retain unmaterialized or missing items explicitly.
**Rollback:** Restore the recorded pre-task candidate without touching unrelated edits; preserve rejected candidate and evidence.

## T2: Establish safe focused baseline
- [ ] Complete and verify T2.

**Description:** Establish safe focused baseline for the single-founder infrastructure pilot.
**Dependencies:** T1.
**Likely files:** tests/test_tools.py; tests/test_root_mutation_guard.py; test environment configuration.
**Scope:** M; split further if implementation exceeds five files or one focused session.
**Acceptance:** All destructive-denial inputs mock subprocess and assert no dispatch; isolated dependencies resolve; current focused baseline recorded.
**Verification:** Run focused tool/prospect/hook tests only after safety inspection; record failures and exact head; never execute destructive probes.
**Rollback:** Restore the recorded pre-task candidate without touching unrelated edits; preserve rejected candidate and evidence.

## T3: Expose a restricted pilot entry
- [ ] Complete and verify T3.

**Description:** Expose a restricted pilot entry for the single-founder infrastructure pilot.
**Dependencies:** T2.
**Likely files:** pilot entry module; API boundary tests; start instructions.
**Scope:** M; split further if implementation exceeds five files or one focused session.
**Acceptance:** Only intended pilot routes mounted; missing/invalid auth blocks; shell and legacy execution routes unavailable.
**Verification:** API route inventory and authenticated/unauthenticated/wrong-scope tests; launch and stop actual process.
**Rollback:** Restore the recorded pre-task candidate without touching unrelated edits; preserve rejected candidate and evidence.

## T4: Deliver generic document-to-edit flow
- [ ] Complete and verify T4.

**Description:** Deliver generic document-to-edit flow for the single-founder infrastructure pilot.
**Dependencies:** T3.
**Likely files:** aos/prospects/models.py; workflow.py; dashboard document page; focused tests.
**Scope:** M; split further if implementation exceeds five files or one focused session.
**Acceptance:** Infrastructure fixture yields source-linked brief; no prospect/business defaults; edit/revert creates distinct review revisions.
**Verification:** Run scoped generation/edit tests plus real-browser upload/source/edit flow with text injection cases.
**Rollback:** Restore the recorded pre-task candidate without touching unrelated edits; preserve rejected candidate and evidence.

## T5: Bind approval to internal export
- [ ] Complete and verify T5.

**Description:** Bind approval to internal export for the single-founder infrastructure pilot.
**Dependencies:** T4.
**Likely files:** store.py; routes.py; contract models; export tests.
**Scope:** M; split further if implementation exceeds five files or one focused session.
**Acceptance:** Only exact approved revision exports; wrong actor/scope/hash/expiry/replay denied; idempotent export identity persisted.
**Verification:** Concurrent stale edit/approve/export tests and denial cases against real storage/API.
**Rollback:** Restore the recorded pre-task candidate without touching unrelated edits; preserve rejected candidate and evidence.

## T6: Verify export recovery and restore
- [ ] Complete and verify T6.

**Description:** Verify export recovery and restore for the single-founder infrastructure pilot.
**Dependencies:** T5.
**Likely files:** artifact verifier; recovery tests; restore helper.
**Scope:** M; split further if implementation exceeds five files or one focused session.
**Acceptance:** Artifact readback matches approved bytes; restart/lost response reconciles; separate restore preserves accepted records.
**Verification:** Inject commit/response-loss windows; retry; reopen bytes independently; restore temporary database and compare identities.
**Rollback:** Restore the recorded pre-task candidate without touching unrelated edits; preserve rejected candidate and evidence.

## T7: Render trusted review/result controls
- [ ] Complete and verify T7.

**Description:** Render trusted review/result controls for the single-founder infrastructure pilot.
**Dependencies:** T5,T6.
**Likely files:** dashboard document page; API client; browser tests; styles.
**Scope:** M; split further if implementation exceeds five files or one focused session.
**Acceptance:** Approval is application-owned; only readback evidence produces verified result; stale/unknown/failed states visible.
**Verification:** Real browser desktop/phone/keyboard flow; forged result and stale revision negative cases. C2 Milestone A.
**Rollback:** Restore the recorded pre-task candidate without touching unrelated edits; preserve rejected candidate and evidence.

## T8: Add bounded read-only worker adapter
- [ ] Complete and verify T8.

**Description:** Add bounded read-only worker adapter for the single-founder infrastructure pilot.
**Dependencies:** T4.
**Likely files:** worker contract; adapter; fake-transport tests.
**Scope:** M; split further if implementation exceeds five files or one focused session.
**Acceptance:** Schema/scope/deadline/cancel/budget enforced; no side-effect tools; minimum context and receipts recorded.
**Verification:** Fake transport tests include malformed output, auth/quota failure, timeout and no paid fallback.
**Rollback:** Restore the recorded pre-task candidate without touching unrelated edits; preserve rejected candidate and evidence.

## T9: Prove one real authorized worker
- [ ] Complete and verify T9.

**Description:** Prove one real authorized worker for the single-founder infrastructure pilot.
**Dependencies:** T7,T8.
**Likely files:** one provider adapter; integration fixture; evidence record.
**Scope:** M; split further if implementation exceeds five files or one focused session.
**Acceptance:** Actual supported account round trip on target runner; no new spend without authority; output/provenance linked to central task.
**Verification:** Use nonconfidential fixture, capture exact runtime/auth mode and receipt, then complete edit/approve/export/readback.
**Rollback:** Restore the recorded pre-task candidate without touching unrelated edits; preserve rejected candidate and evidence.

## T10: Evaluate Herald client compatibility once
- [ ] Complete and verify T10.

**Description:** Evaluate Herald client compatibility once for the single-founder infrastructure pilot.
**Dependencies:** T7.
**Likely files:** isolated client adapter spike; contract tests; decision note.
**Scope:** M; split further if implementation exceeds five files or one focused session.
**Acceptance:** One task renders/reconnects under central identity; denied action remains denied; no independent approval/scheduler authority.
**Verification:** Read-only isolated spike with synthetic data; retain only if useful, otherwise mark deferred. Never block web release on desktop migration.
**Rollback:** Restore the recorded pre-task candidate without touching unrelated edits; preserve rejected candidate and evidence.

## T11: Run founder acceptance
- [ ] Complete and verify T11.

**Description:** Run founder acceptance for the single-founder infrastructure pilot.
**Dependencies:** T6,T7,T9; T10 decision recorded.
**Likely files:** acceptance fixtures; browser tests; release evidence.
**Scope:** M; split further if implementation exceeds five files or one focused session.
**Acceptance:** Three representative founder tasks complete on exact candidate; independent review resolved; required relevant CI/checks pass.
**Verification:** Upload/task through verified artifact plus restart, scope denial and keyboard/mobile flow; no simulated result labeled live.
**Rollback:** Restore the recorded pre-task candidate without touching unrelated edits; preserve rejected candidate and evidence.

## T12: Prepare operating handoff
- [ ] Complete and verify T12.

**Description:** Prepare operating handoff for the single-founder infrastructure pilot.
**Dependencies:** T11.
**Likely files:** start/stop instructions; backup/restore runbook; known limits; improvement checklist.
**Scope:** M; split further if implementation exceeds five files or one focused session.
**Acceptance:** Founder can start/stop/resume; rollback/restore rehearsed; observations and one-change improvement policy defined.
**Verification:** Follow instructions from a fresh temporary profile; verify restore; record accepted version and remaining backlog.
**Rollback:** Restore the recorded pre-task candidate without touching unrelated edits; preserve rejected candidate and evidence.

## Checkpoints
- [ ] C1, after T1-T3: runnable restricted application; safe baseline and boundary review.
- [ ] C2, after T4-T7: working document workflow, explicitly labeled Milestone A; founder can inspect it.
- [ ] C3, after T8-T12: one real worker, founder acceptance, independent review and recovery evidence; agent-enabled v0.1 accepted.

All earlier PR contributions remain archived and tracked by the disposition document. No plan, branch or tracker items were deleted.
