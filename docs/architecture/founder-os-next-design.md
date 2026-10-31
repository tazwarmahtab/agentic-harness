# Founder OS: next design decisions

Working proposal, 31 October 2026. Owner: Taz. This records decisions proposed by the assistant, not new user-approved infrastructure spending or data disclosure. Companion: [interactive atlas](workflow-atlas.html), [machine-readable inventory](workflow-atlas.json).

## Direction

Keep one Founder OS product over the existing AOS backend. Build reusable job, evidence and action contracts, then add voice and adaptive presentation. Start with the supplied-document prospect workflow. Measure saved founder effort and completed outcomes before expanding into more workflows.

The atlas covers that slice and its shared-service dependencies. It is not a complete audit of every legacy module, business process or integration. Unknown coverage must remain visible. Source fingerprints establish freshness of reviewed files, not correctness or exhaustive coverage.

## Findings from current source

- The extractive analyzer selects up to the first 40 passages, with at most 6,000 characters per excerpt. It does not perform complete semantic review. The UI and future brief must communicate selection coverage; a missing topic is not proof that the source lacks the answer.
- Exact citation validation confirms a substring at a source locator. It does not verify real-world truth, recency or whether a quote supports a broader interpretation.
- SQLite-backed prospect records and versioned review are implemented. Legacy graphs default to process-local MemorySaver; a persistent prospect does not imply restart-safe global execution.
- Parser time/memory limits are present, but filesystem/network isolation is absent.
- Existing CI runs tests, lint/format/type checks and an evaluator. Staging and production deploy commands are placeholders, not evidence of deployment.
- The prior delivery ledger records 1,186 passing tests and outstanding full-repository checks. Those results are historical and were not rerun for this mapping change.

## Twelve responsibilities

| Responsibility | Required contract | First acceptance condition |
|---|---|---|
| Intake | Actor, venture, project, purpose, attachments, sensitivity | Bad scope and oversized uploads fail explicitly |
| Evidence | Original hash, locator, extraction method, selection coverage | Every displayed excerpt resolves to its original |
| Memory | Record kind, provenance, valid date, status, supersession, retention | Corrections cannot silently leave contradictory active facts |
| Work | Stable job ID, owner, dependencies, budget, completion criteria | Restart resumes without duplicating completed effects |
| Agent | Versioned role, duties, allowed tools, escalation and evaluation | Duties have observable outcomes and bounded authority |
| Decision | Finite options, uncertainty, model/version, evaluation | Out-of-scope input abstains or escalates |
| Action | Actor, destination, exact payload version, expiry, idempotency key | Replay, stale payload and wrong recipient cannot execute |
| Worker | Task inputs, isolation, egress, credentials, resource limits | Worker cannot access ungranted files or network destinations |
| Review | Version, evidence, changes, consequences, decision | Any material edit invalidates previous review |
| Interface | Approved component schema, permissions, stable controls | Unsupported components fail safely and drafts survive updates |
| Conversation | Session identity, project, turn events, task references | Interrupting speech does not implicitly cancel backend work |
| Operations | Traces, release manifest, alerts, backups, recovery ownership | Failed release and data restore are rehearsed |

## Voice and generative UI

The conversation layer retrieves status and submits scoped intents through AOS. It cannot bypass review or hold unrestricted provider credentials. Background jobs outlive audio connections. The screen and spoken response refer to the same job/revision and confirmed backend state.

Start with five approved components: evidence viewer, comparison, missing-information form, draft editor and review card. Navigation, save, approval and cancellation semantics remain stable. Suggestions may adapt; permissions do not. Preserve keyboard focus, text alternatives, incomplete edits and accessibility. Revalidate any cached card against server state before applying an action.

For voice, distinguish listening, thinking, working, awaiting review, reconnecting and muted. "Stop speaking" affects playback; "cancel this job" requests backend cancellation with an explicit result. Never say "sent" until a provider receipt establishes delivery status. Confirm ambiguous names, amounts, dates and recipients structurally. Evaluate Bangla, English, code-switching, local number formats, interruptions, noise, headset changes and screen lock on actual devices.

Always available means a reachable service and durable work. It does not require continuous microphone capture or a permanently billable audio session. Microphone sessions, transcript retention and optional audio retention need separate controls. Native mobile background behavior remains to be validated.

## Candidate tools: separate roles, replaceable adapters

| Candidate | Role to evaluate | Boundary / decision |
|---|---|---|
| Archify | Render architecture/workflow views from reviewed evidence | Optional renderer; the versioned inventory remains authoritative |
| OpenAI voice APIs | Conversational audio connected to our backend | Verify account access and benchmark before choosing a model |
| A2UI | Declarative component descriptions | Evaluate a small catalog without forcing a frontend rewrite |
| MCP Apps | Present interactive tools in compatible chat clients | Distribution option; host support must be checked |
| Laya | Self-hosted finite-option routing | Held-out local evaluation; calibration and language risks |
| Jev | Managed typed judgments | Same evaluation contract; live disclosure/budget agreement first |
| Boxd | Isolated job workers | Validate isolation, cost and runtime licensing; no deployment yet |
| rv | Additional host action policy | Not accepted as a replacement for a validated sandbox |
| Harness.io | Delivery, evaluations, artifacts, release governance | Compare incremental benefit to existing CI before adoption |
| Notion / GitHub | Human knowledge workspace / implementation records | Define ownership and sync direction before automatic writes |

Sources inspected in the conversation: [Archify](https://github.com/tt-a1i/archify), [voice architecture](https://developers.openai.com/api/docs/guides/voice-agents), [A2UI](https://a2ui.org/), [MCP Apps](https://modelcontextprotocol.io/docs/extensions/apps), [Laya](https://github.com/NandhaKishorM/laya), [Jev](https://docs.typesafe.ai/models.md), [Boxd](https://boxd.sh/self-hosting/), [rv](https://rykanv.com/install), [Harness Agent DLC](https://www.harness.io/products/use-cases/agent-dlc). These links are research references, not integration or acceptance evidence. Verify moving products before implementation.

## Ordered backlog

| Priority | Work | Exit condition |
|---|---|---|
| P0 | Revalidate and repair inherited release gates in bounded changes | Full required gates pass without lowering the bar; current baseline recorded |
| P0 | Make selection coverage and verification status clear | User can see selected vs extracted material and unsupported conclusions |
| P0 | Evaluate restart-safe jobs and shared action authorization | Crash, replay, concurrency, stale payload and cancellation checks pass |
| P0 before external exposure | Validate deployment authentication, worker isolation and restore | Synthetic boundary tests plus successful backup restoration |
| P1 | Establish representative, source-labeled evaluation cases | English/Bangla/mixed inputs, contradictions, missing evidence and hostile documents covered |
| P1 | Add five adaptive components to prospect review | Measured improvement in review effort without reducing accuracy |
| P1 | Add one voice workflow over the same saved job | Interruption, correction, reconnection and text fallback pass |
| P2 | Compare narrow rules/LLM/Laya/Jev routing | Quality, abstention, latency and costs measured on held-out cases |
| P2 | Connect a single additional data source | Revocation, change detection, deduplication and deletion tested |
| P2 | Add proactive exception digest | Actionable alerts have evidence, owner, next step and suppression rules |

P0 work can be split; this order is a recommendation rather than an instruction to rewrite the entire platform. Do not add every shortlisted vendor before validating the underlying need.

## Improvement loop and stop rule

Observe outcome → preserve evidence → deduplicate → classify failure → propose bounded change → independent review where warranted → run requirement-based checks → release under policy → compare outcomes. An observation may become a digest item, clarification or incident instead of a ticket.

Each actionable ticket needs source, affected step, impact, owner, dependencies, acceptance, rollback/recovery, cost ceiling and evidence of closure. Separate code defects, missing requirements, test defects, environment failures and provider outages. A failed test is not permission to delete the assertion. An agent's self-grade cannot expand its access.

Stop a release loop when its agreed requirements and required gates pass, or when budget, retry limits, missing authorization or an unresolved external dependency requires escalation. No "perfect system" claim. Track useful response latency separately from acknowledgments, task correctness, unsupported claims, founder review time, correction rate, recovery success and cost per completed outcome.

## Source freshness and maintenance

Run `python scripts/workflow_atlas.py --check` before relying on this snapshot. It checks source hashes and anchors and exits nonzero if evidence changed. Review the changed source, update step descriptions, then run `python scripts/workflow_atlas.py --refresh` to record new fingerprints and render HTML. A refresh does not prove that review occurred.

The check is deliberately not installed into CI yet: wiring an unconditional check would block every source edit until map review. A later scoped pull-request job can flag affected steps and require explicit map review. No new schedule, cloud cluster, external integration, microphone access or live model call has been enabled by this documentation work.

## Verification of this artifact

The inventory contains 15 steps: seven implemented, three gaps and five proposals. A deliberately stale fingerprint was rejected, and rendering twice produced identical HTML. The generator passes Ruff lint and format checks. Browser verification was initially unavailable; on 31 October a temporary Chromium runtime enabled successful atlas desktop/mobile overflow, status-filter and expansion checks.

The new [Knowledge & Files surface](knowledge-files.md) is implemented over existing prospect records. This is a conventional, predictable document browser; model-selected generative components and voice remain proposals. Its feature and regression checks are recorded separately in that document.
