# Agent Harness v0.1 delivery plan
5 November 2026, Asia/Dhaka. Planning only. Task checklist: tasks/todo.md. Revises the launch proposal; preserves all archived contributions and earlier evidence.

## Outcome and release boundary
A founder opens the application, submits a nonconfidential infrastructure task/document, obtains a source-linked brief from an explicitly identified read-only worker, edits the draft, reviews its exact revision, approves an internal artifact export and independently reopens the result. The same task, revision and evidence survive restart. One backend owns accepted state, policy and approval. Three representative founder tasks must complete.

Milestone A is a working local/extractive document workflow. It is useful but must be labeled a workflow pilot, not a functioning agent harness. Milestone B adds one real authorized worker round trip; only then can agent-enabled v0.1 be accepted. Provider quota, login and supported runner are release dependencies, never implied by installed tools. Default: no new spending or protected-data disclosure.

## Current facts
main was observed at 066d180c75bee9fd2101820198b3b5858a6cc9d8. Integration branch integration/v01-founder-pilot-20261105 derives from PR9 head 4a49404d362017645c5d5c553ab09eb733dee1d9. Six known PRs are closed/unmerged and archived; their closure is not integration. PR23 includes the hook/root-guard history and overlaps PR9 approval code. The branch currently contains planning additions, not an integrated release.

PR9 has UI/scoped storage/review history but prospect-specific prompts and no approved-export endpoint. Its historical tests are reports. Prior direct local checks: 17 hook tests and 25 mocked root cases against recovered PR22 source. Not full checkout/CI evidence.

The original 92-gap register remains unavailable here. Do not infer its closure from this reduced pilot. Full-source execution and review access remain unproven in this workspace.

## Architecture decisions and defaults
- Existing FastAPI/store and dashboard are the default delivery route. Restrict the pilot app to intended authenticated endpoints; do not publish the wider legacy API.
- Herald OS is an evaluated desktop-client candidate, not a selected backend or installed runtime. Its inspected architecture gives Hermes work/session/tool/memory/cron/approval ownership, and Electron host capabilities. A full-shell adoption would require explicit authority migration or a governed adapter; merely embedding both runtimes is not acceptable.
- Give Herald one bounded compatibility spike after Milestone A. Test one existing task's render/reconnect and denied action against our authority. Reuse only if it demonstrably reduces work without creating independent approvals, execution, cron or task truth. Otherwise defer it and ship the web UI. No OS replacement, quarantine removal, permission grants or host install in this plan.
- Controlled generative UI uses our trusted component catalog. Read-only presentation may adapt; exact approvals, identity, cancellation and verified outcomes remain application-owned. No new renderer dependency is needed to reach Milestone A. json-render/CopilotKit/AI SDK are candidate experiments after baseline delivery, not simultaneous required installations.
- Retain approved source work and history. Deferred != deleted. Reconcile PR9/23 behavior and tests before integrating shared files. PR19 journal stays archived until a transaction-boundary comparison shows it is required.

## Contracts
Task identity and workstream are server-issued/scoped. Commands bind actor, task/run, expected revision, action/resource, payload digest, idempotency key, policy and deadline. Server rechecks these at execution. Approval records bind exact action/revision/content/scope, decision maker and expiry. Rejection, missing/changed/expired/replayed authorization blocks.

Approved exports use immutable approved bytes and a durable dedup identity. Prefer one transactional artifact/outcome record for this internal effect; if a filesystem export is introduced, explicitly cover crash windows and independent file readback. Result cards say verified only after readback comparison. A completed HTTP request or generated receipt is insufficient.

Worker adapter receives minimal scoped context, explicit data destination, schema, deadline and usage cap. In v0.1 it produces text/artifacts only; no native side-effect tools. Central backend remains authority. No silent paid/provider fallback. Preserve provenance, failure, cancellation and measured/unknown usage accurately.

## Ordered task index
See tasks/todo.md: T1 source recovery; T2 safe baseline; T3 restricted entry; T4 generic document flow; T5 revision-bound export; T6 recovery/readback; T7 trusted result UI; T8 one worker adapter with fake transport; T9 real authorized worker; T10 Herald compatibility; T11 founder acceptance; T12 operating handoff.

Checkpoints: C1 after T1-T3 (runnable restricted foundation); C2 after T4-T7 (Milestone A); C3 after T8-T12 (agent-enabled v0.1). T10 may conclude deferred without blocking web release. Independent reviewer required for consequential implementation; no self-review counts as independent. Do not dispatch agents or post reviewer requests solely from this planning invocation.

## Definition of done
Exact candidate has relevant unit/API/browser checks, independently reviewed changes, no unexplained required CI failure, authentication/scope/approval/evidence adversarial cases, restart/restore evidence, and three successful founder requests. Narrow scope may exclude unreachable components, but cannot hide reachable defects or weaken tests. Whole-repository inherited failures stay documented; every excluded check needs an explicit reachability rationale. No unknown/skipped/stale gate is green.

Milestone A must work without provider keys. Milestone B requires an actual account-authorized worker run on the target runner with no unexpected spend. Do not promise a launch date until T1/T2 establish execution time and access. New suggestions go to a deferred list, not into this release.

## Failure handling and preservation
Before each implementation slice record clean baseline, branch/head, acceptance cases and rollback. Keep one active integration stream. Two failed repairs or an unchanged failure fingerprint triggers diagnosis/handoff; do not run an infinite unchanged loop. Never reset, delete branches, overwrite unrelated work, or bulk-close trackers. Archive remote heads plus inventory accessible local changes; archive refs are not an independent full backup. Separate-state restore drill must pass before founder reliance.

## Continuous improvement after acceptance
Observation is read-only and records completion/readback failure, approval mismatch, restart errors, latency, usage and user friction. A weekly review selects one improvement with measurable benefit. Fixed regression set plus held-out task -> small change -> independent review -> versioned candidate -> founder canary -> observe/retain or rollback. One change in progress; critical incident repair may preempt. No automatic self-promotion, spend, permission expansion or new schedules. Schedules are not proof of delivery. Measure successful end-to-end tasks rather than PR counts or generated documents.

## Risks and unresolved dependencies
Herald lock-in to Hermes versus central authority; mitigate by fail-fast client seam test and default web route. CLI/network failure; use supported execution access rather than bypassing policy or reporting repeated blocked checks as progress. Conflicting approval repairs; compare semantics/tests. Scope creep; frozen milestones and explicit deferral. Source loss; archives, pinned inventory and restore test. Workstream leakage; generic fixture data and scoped denial cases.

Need actual authorized runner and one worker entitlement. Request browser sign-in only at a real supported auth step, never tokens in chat. Existing user implementation authority persists, but this invocation stays planning-only. No deployment/public exposure/new spend authorized here.

## Primary references inspected
https://github.com/iamlukethedev/Herald-OS/blob/main/docs/ARCHITECTURE.md
https://github.com/iamlukethedev/Herald-OS
https://ai-sdk.dev/docs/ai-sdk-ui/generative-user-interfaces
https://github.com/CopilotKit/generative-ui
https://github.com/CopilotKit/OpenIntelligentUI
https://json-render.dev
https://research.google/blog/generative-ui-a-rich-custom-visual-interactive-user-experience-for-any-prompt/
https://generativeui.github.io
https://uizard.io/ai-design/
https://github.com/narrowin/awesome-generative-ui
Documentation review is not implementation verification. Pin exact dependencies before adoption.
