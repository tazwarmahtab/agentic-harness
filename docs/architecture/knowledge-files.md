# Knowledge & Files

Implemented 31 October 2026 in the existing Odysseus dashboard. Visual reference: [Inspora Folders UI](https://www.inspora.design/posts/folders-ui). Original CSS folder illustration; no reference artwork or third-party component code copied.

Open **Knowledge & Files** in the dashboard, enter the founder token and venture/project, and select **Load project files**. The token remains in the existing in-memory API client. Each saved prospect is a folder. Original files and three generated views (brief, checklist, follow-up) come from existing authenticated prospect records; no separate storage or folder permission system is introduced.

The first version supports folder navigation, filename/folder-name search, original/generated filters, text previews with source hashes, authenticated original downloads, readable revision/review history, and navigation into the selected prospect's editable review workflow. Source documents remain labeled as supplied/unverified. Generated artifacts show job status and remain subject to existing exact-version review. The file browser itself cannot approve or send anything.

Scope or credential edits immediately clear displayed records and abort pending requests. A generation counter prevents old responses repainting a new scope. Navigation away aborts requests. Text from files, filenames, prospect names and histories is inserted with textContent. No search or document data is persisted in localStorage. Downloads are fetched with authentication; object URLs are short lived.

## Limits

- Up to the latest 100 prospect records in an explicit venture/project scope, matching the existing list API. Authorized record details load with at most four concurrent requests. This is a bounded pilot implementation, not a large-library index.
- Search covers loaded folder names and filenames, not semantic or full-document search.
- These folders are derived views, not arbitrary nested folders. Rename, drag/drop, moving documents, uploads into this page, Drive/Notion sync and Ask AI are not included. Uploads remain in Prospect Briefs.
- Previews show extracted text; scanned PDFs still need a future OCR capability. Original bytes remain downloadable.
- Records are a loaded snapshot. Open the brief for current editable/reviewable state; backend version checks remain authoritative.
- The existing single-founder token boundary remains; this does not establish staff/customer multi-tenancy or a production deployment.

## Verification

Thirty prospect API/store/CLI tests pass. Real engine + real dashboard browser acceptance passes at 1440px and 390px for wrong-token denial, scope separation, folder/file counts, search, originals filtering, previews, original-byte download, revision/event history, navigation to the correct brief, inert HTML-like prospect text, empty state and scope-change clearing. Existing prospect upload/edit/review/citation/XSS/layout smoke also passes at both widths. Desktop and mobile screenshots inspected; no document or workspace horizontal overflow.

Run:

```sh
AOS_BROWSER_EXECUTABLE=/path/to/chromium NODE_PATH=/path/to/node_modules .venv/bin/python tests/browser/run_prospect_smoke.py tests/browser/knowledge-smoke.cjs
AOS_BROWSER_EXECUTABLE=/path/to/chromium NODE_PATH=/path/to/node_modules .venv/bin/python tests/browser/run_prospect_smoke.py
```

No live model or real customer data was used. Repository-wide release debt from the consolidation ledger is not resolved by this UI feature.
