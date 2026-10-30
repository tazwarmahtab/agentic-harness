# Founder OS / AOS / Netso OS — consolidated implementation

## Ownership decision

One program and one existing repository: `tazwarmahtab/agentic-harness`.

| Layer | Owner | Current implementation |
|---|---|---|
| Founder interface | Founder OS | Odysseus dashboard, including Prospect Briefs |
| Execution and policy | AOS | Existing Python/FastAPI/LangGraph; bounded prospect capability |
| Venture-specific work | Netso OS | Venture/project-scoped prospect records; existing legacy venture modules retained |
| External knowledge | Notion | Existing pages remain external; this change does not activate sync |
| Reference patterns | Bennettxai/FounderOS | Design reference only; no upstream code copied |

This supersedes the earlier proposal to build a separate Next.js backend for the first slice. It does not replace the entire legacy platform in one change. The original Python design system remains authoritative. The Netso black/yellow marketing site is a separate product surface.

## Working first slice

`supplied documents -> original source record -> exact evidence excerpts -> confirmation checklist -> editable draft -> exact-version human review`.

Supported: TXT/MD, text PDFs, DOCX paragraphs/tables. Scans/images/spreadsheets/URLs require a later capability. Each original has SHA-256 and a stable source ID. Each excerpt references its document and line/page/paragraph-table-row locator. Conflicting supplied assertions remain separate excerpts; source truth and disagreement require human review. Missing items mean **no selected evidence**, not proof that a document contains no answer. Offline extraction intentionally does not infer buyer, financial, or engineering facts.

### One record per responsibility

- Prospect documents, original bytes, source locators, outputs, versions and review events live transactionally in `AOS_STATE_DIR/prospects.sqlite3`.
- Default state directory: `~/.local/state/aos`; DB created owner-only. Do not commit or publish state files.
- Existing general memory/JSONL approvals are legacy compatibility surfaces. They do not approve prospect outputs. Prospect review has no send authority or tool-gateway path.
- Shared multi-workflow approval migration and shared organization-wide event ownership remain a later migration; no claim of complete deduplication of all historical storage.

## Run locally

```sh
uv venv .venv
uv pip install --python .venv/bin/python -e '.[dev]'
# Configure a strong AOS_API_TOKEN privately in the environment of the engine.
# Set AOS_STATE_DIR to a private persistent directory you back up.
.venv/bin/uvicorn aos.api:app --host 127.0.0.1 --port 7001
```

In a second terminal:

```sh
AOS_ENGINE_URL=http://127.0.0.1:7001 .venv/bin/uvicorn odysseus.server:app --host 127.0.0.1 --port 3000
```

Open `http://127.0.0.1:3000`, choose **Prospect Briefs**, enter the configured token, venture/project, meeting purpose, and files. The token remains in browser module memory; no URL or persistent browser storage. Saved jobs reopen by venture/project. Citation buttons expose the source passage; original downloads require the same authentication/scope. Draft edits invalidate review and produce a distinct revision even when text returns to an older value. Approving a draft never sends it.

The existing `preview.html` remains the standalone preview surface. The actual server now serves `live.html`, with correct `/static/` URLs and the same-origin `/api` proxy.

## Local CLI

```sh
.venv/bin/python -m aos prospects create --venture netso --project factory-demo --prospect 'Synthetic Factory' --purpose 'Discovery meeting' --files /path/to/notes.txt
.venv/bin/python -m aos prospects generate --venture netso --project factory-demo --id JOB_ID
.venv/bin/python -m aos prospects show --venture netso --project factory-demo --id JOB_ID
.venv/bin/python -m aos prospects review --venture netso --project factory-demo --id JOB_ID --hash OUTPUT_HASH --decision approve
```

CLI assumes an authorized local OS user; it is not a public authentication boundary.

## API / model disclosure

Canonical routes are `/api/prospects`, scoped `/{job_id}`, `/generate`, `/draft`, `/review`, `/sources/{source_id}`, `/events`, and `/versions`. All require a configured founder bearer token; missing server configuration returns 503, invalid credentials 401. Wrong scope returns 404. Output mismatch/terminal decision conflicts return 409.

Default generation is local and extractive. The API supports model-assisted **selection of exact evidence** through the existing AOS `LLMClient`; `AOS_PROSPECT_MODEL_ENABLED=1` and request flags `use_model=true`, `allow_model_disclosure=true` are both required. User documents are sent to the configured provider only on that explicit request. The dashboard's local-generation button never sets those flags. No real provider or customer data was used for verification. Model-selected output is citation-validated, not independently verified truth; live-model quality/cost is unvalidated.

## Limits and remaining boundaries

12 files, 5 MiB/file, 10 MiB decoded total, 15 MiB HTTP body at both engine and dashboard. Up to100 PDF pages; 120,000 extracted characters/job. PDF/DOCX parsers run with no inherited provider credentials, a 15-second wall limit, 10-second CPU limit, and 512 MiB address-space limit on POSIX. This is resource isolation, not a filesystem/network sandbox. Unsupported platforms fail explicitly for PDF/DOCX. Linux tests establish current behavior; macOS needs its own parser/host smoke before reliance.

Single founder access, not multi-tenant RBAC. No automatic inbox/CRM/Drive/Notion sync, external sending, payment, signing, or lender submission. No public deployment is established. The wider legacy API still has local-development auth behavior and agent tool risks; this change's strict boundary applies specifically to prospect routes. Do not expose the entire old service as a hardened production API.

Legacy graph approval gates now require explicit current approval decisions; resolved-ID history alone cannot authorize, and execution rechecks persisted state. Missing/rejected/deferred/unknown items block. Legacy JSONL persistence still lacks transactional multi-writer guarantees and exact handoff payload grants; global durable graph checkpointing is not implemented by this slice. MemorySaver is process-local.

## Review and verification

Independent architecture review and a separate fresh-context branch review were performed. Four important findings were fixed with RED/GREEN tests: revision identity on edit/revert, proxy upload limits, parser resource budgets, and stale persisted approval snapshots.

Browser smoke: real engine + real dashboard, synthetic uploads, desktop 1440px/mobile390px, citation expansion, editable draft, review reset, approval, HTML injection, and horizontal overflow. Script: `tests/browser/run_prospect_smoke.py` (requires Playwright/Chromium; optional `AOS_BROWSER_EXECUTABLE`). Browser screenshots are internal QA only.

Release checks and remaining debt are recorded in `../superpowers/plans/2026-10-30-founder-os-progress.md`. Repository-wide lint/type checks must not be described as green merely because the new capability passes.
