# v0.1 source recovery and focused baseline
6 November 2026, Asia/Dhaka. Agent Infrastructure only.

## Candidate and recovery
Recovered superproject snapshot at 63a378ad9c387dbe277cafd24817286994e24117 through the connected GitHub tool. Recursive tree returned truncated=false. All 697 blob contents were retrieved, verified by Git blob SHA-1 against the returned tree entries, then materialized into an isolated candidate-v01 directory. Executable modes and symlink targets preserved. No original or archive refs were changed.

Two gitlinks remain uninitialized: gsd-core at 5867996a6a0e6a510125aa90b48327d59c7998c3 and gsd-repo at bdcaab2c752d9a33a1a1ca9acf3a3c81fb991815. No .gitmodules file exists in this snapshot. Do not describe it as a complete recursive Git checkout or invent upstream URLs. Determine whether either is a dependency of the restricted pilot before claiming T1 complete.

Workspace maintenance removed earlier local recovery; this run fetched from remote again and saved transfer batches incrementally. Remote archives and plans were retained. Root CLAUDE.md inspected; tree shows AGENTS.md only under separate company-agent directories, which were not used for infrastructure instructions.

## Executed checks
uv sync --frozen --extra dev succeeded, building the local aos package and installing 75 packages into .venv. Lockfile was not regenerated.

.venv/bin/python -m pytest -q tests/test_prospects.py tests/test_prospect_api.py tests/test_prospect_cli.py

Result: 30 passed, 1 warning in 4.31 seconds. Warning: FastAPI/Starlette TestClient deprecates its current httpx integration. Tests use synthetic fixtures; no live worker inference, messages or customer-data disclosure invoked. Scoped cases include storage, API, CLI subprocess flow, review/revision and source access behavior. The document subsystem retains its existing prospect-specific labels; this is baseline verification, not implementation of the generic pilot.

## Task status
T1: superproject materialization and blob verification complete; recursive gitlinks and full instructions/recovery acceptance still need final disposition.
T2: existing scoped document baseline passes; destructive tool tests were not executed and their mocking repair remains open.
T3 onward: not implemented by this run. No complete restricted pilot launch, browser acceptance, new approval export, live worker, independent review, hosted CI or production verification claimed.

## Next
Determine gitlink relevance to the pilot. Make the remaining destructive-denial tests safe before running the broader tool baseline. Then implement the restricted entry point with route/auth tests, followed by the generic document flow and exact approved export. No merge/deployment/new schedule performed. This receipt changes documentation only; tested source candidate remains the pinned commit above.
