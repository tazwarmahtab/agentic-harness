# Founder OS / AOS consolidation — prospect workflow

Status: implementation authorized by Taz on 30 October 2026. User selected document-to-brief workflow and authorized consolidation/refactoring with review. This records the concrete implementation choices; it does not claim all platform migrations are complete.

## Ownership
- Founder OS is the founder-facing product across ventures; AOS is its execution backend; Netso is a venture-specific capability set.
- Retain Python 3.12+, FastAPI, existing LLM protocol, and Odysseus dashboard. No second Next.js service or imported FounderOS backend.
- Bennettxai/FounderOS remains a reference; no upstream code is copied in this change. Notion remains an external knowledge/document surface. No automatic bidirectional sync.
- Original documents, extracted passages, workflow outputs and decisions have one transactional SQLite record for this capability, outside the git repository. Legacy agent memory/approvals remain compatibility surfaces, not authorities over prospect output review.
- Preserve DESIGN.md. No shell or messaging capability in prospect processing. No finance/PPA constants injected from old manifests.

## First complete workflow
Founder chooses venture/project, uploads TXT/MD, DOCX or text PDF, and enters prospect name + meeting purpose. Save original bytes, SHA-256 and page/paragraph passages. Run extraction offline by default. Produce an extractive brief, explicit open questions, and a draft follow-up. An optional model adapter may select/classify exact quoted passages; invalid quotes/references fail validation. Model disclosure requires both server enablement and per-request opt-in. This implementation's live model integration is tested only using a deterministic fake; no live customer data is sent during development.

Outputs include source references and a review hash. The founder approves/rejects/defers that exact version; approval is never permission to send. Defer remains reviewable; approve/reject are terminal for the version. A replacement output requires a new review. Conflicting sources are presented separately, with instructions to resolve, not silently reconciled. No extracted text is promoted into global company truth.

## Limits and access
Single founder token; no staff/customer multi-tenancy claim. Sensitive endpoints require AOS_API_TOKEN, failing closed if absent. Venture/project scoping applies to every lookup. Upload limits: 12 documents; 5 MiB each; 10 MiB decoded total; 100 pages; 120,000 extracted characters per job. Scanned/empty PDFs require OCR and fail explicitly. No arbitrary filesystem paths or URLs accepted by API. DOCX zip expansion bounded. No images, spreadsheets, OCR, encrypted PDF support or URL imports in this release.

## Reliability and verification
Persist intake before analysis; restart can retry unfinished or failed analysis against immutable sources. No automatic re-execution of external effects because no outbound effects exist. SQLite transactions serialize version publication and review; concurrent duplicate/conflicting review decisions are idempotent/conflict respectively. Original source downloads require authentication and matching scope. Untrusted model/document text is rendered as text, never HTML.

Legacy approval repair: missing/rejected/deferred approvals do not authorize handoffs. Recheck persisted queue at execution, not only routing. Default MemorySaver remains explicitly documented as process-local; prospect durability uses its transactional store, not a misleading claim of global graph recovery.

## Delivery gate
Synthetic E2E via HTTP and dashboard: upload -> generate -> inspect citations and original -> review -> reopen after restart. Negative tests for bad citations, malformed data, wrong scope, stale hash, missing token, rejected approvals, hostile document HTML, missing text and failed analysis retry. Full repo suite and changed-file lint; independent review before merge. Deployment is not implied by a merge. Remaining legacy gaps must be reported.
