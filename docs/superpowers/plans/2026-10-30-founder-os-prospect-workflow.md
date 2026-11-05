# Founder OS prospect workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Consolidate Founder OS/AOS ownership and deliver one durable, evidence-linked document-to-brief workflow in the existing application.
**Architecture:** A bounded Python capability with transactional SQLite state, authenticated FastAPI routes, and an Odysseus page. Legacy graph approval decisions are repaired separately; no new platform is scaffolded.
**Tech Stack:** Python 3.12+, Pydantic 2, SQLite, FastAPI, pypdf, python-docx, vanilla JavaScript.
**Spec:** docs/superpowers/specs/2026-10-30-founder-os-consolidation-design.md

## Global Constraints
Single-founder token authentication; no outbound messaging or shell in prospect processing; no real customer data or live model calls during development. Preserve current design system and existing APIs. Never interpret review approval as send authority.

## Review Focus
- Forged or stale citations and changed output hashes must fail closed.
- Concurrent review decisions must not overwrite a terminal decision.
- Wrong venture/project must not expose sources or outputs.
- Parser errors and oversized/zip-bomb documents must not produce false success.
- Untrusted HTML in source text must remain inert in the dashboard.

### Task 1: Fix legacy approval authorization
Files: aos/graph.py; tests/test_fix03_approval_gating.py; tests/test_approval_authorization.py.
Interface: authoritative queue decisions determine execution; resolved-ID bookkeeping cannot authorize.
- [ ] Write regression tests for reject/defer/unknown IDs and direct execute invocation; run RED.
- [ ] Require explicit approve decisions, revalidated at execution; update obsolete expectations.
- [ ] Run approval/graph regressions and commit.

### Task 2: Durable prospect capability
Files: aos/prospects/{models,ingest,store,workflow}.py; tests/test_prospects.py; pyproject.toml.
Interfaces: ProspectStore.create/get/list/generate/review; typed outputs with exact quotation citations and content hash.
- [ ] Write behavioral tests for restart, file extraction, reference verification, scope, decisions, model opt-in and retry; run RED.
- [ ] Implement bounded parsers, transactional storage and extractive/default + model/injected analysis.
- [ ] Run all capability tests and commit.

### Task 3: Authenticated HTTP and existing dashboard
Files: aos/prospects/routes.py; aos/api.py; odysseus/server.py; odysseus/dashboard/pages/prospects.js; dashboard route/nav; tests/test_prospect_api.py.
Interfaces: /api/prospects, scoped job/source/generate/review operations; page uses same-origin proxy with memory-only bearer token.
- [ ] Write HTTP tests for full flow, strict auth, scope, malformed inputs and source access; run RED.
- [ ] Implement API/page; fix actual served-dashboard asset paths without replacing static preview.
- [ ] Run tests, browser desktop/mobile smoke and commit.

### Task 4: Consolidation documentation and release
Files: README.md; docs/architecture/founder-os-consolidation.md.
- [ ] Document ownership, supported launch, limits, migration boundaries and exact verification results.
- [ ] Run full suite; compare baseline failures; lint changed Python; independent branch review.
- [ ] Fix important findings with RED/GREEN regressions; push reviewable branch/PR and merge only if gates permit.
