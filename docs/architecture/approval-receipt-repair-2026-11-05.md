# Approval routing and execution receipt repair — 5 November 2026

Base: e10eed9e91589c9e46e2e0789d2ec887b70c8e94 (draft PR22).

## Behavior

Legacy graph routing no longer treats absence from pending(), or a state-carried resolved ID, as approval. A configured ApprovalQueue must contain a decided record with decision=approve for every requested approval. Rejected, deferred, unknown and unavailable authority block. Missing chief configuration cannot turn a blocked gate into success. execute_node repeats the approval check so directly invoking the node cannot bypass its routing edge.

Execution records reserve type, status and result for gateway-computed data. Input handoffs cannot overwrite them. Without a gateway, the record remains queued and carries no claimed result. A failed or approval-blocked dispatch makes the execution step error rather than success.

## Verification

New regression file: 13 cases; original implementation failed 11 of the first 12 cases, including rejected/unknown/unavailable decisions and forged receipts. The thirteenth checks an authority decision changing between routing and dispatch.

After repair: 212 tests passed across graph authority, legacy gate tests, root mutation, approval queue, tools, cross-harness fallback, governed gateway, hook contract and tracing. Tests are synchronous and provider effects mocked. Plugin autoload disabled; pytest emitted the existing unknown asyncio_mode setting warning. Command:

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest -q -o addopts='' tests/test_graph_authority_integrity.py tests/test_fix03_approval_gating.py tests/test_root_mutation_guard.py tests/test_approval_queue.py tests/test_tools.py tests/test_graph_h4_fallback.py tests/test_governed_gateway.py tests/test_hook_contract.py tests/test_tracing.py`

New test-file Ruff lint and formatting passed; git diff whitespace check passed; graph source parses. Source-file Ruff reports the same five unused imports at the base and candidate; those unrelated imports were preserved. Full-suite tests, coverage/type checks and remote CI are not certified by this run.

## Limits

This fixes the two reported graph defects. It does not implement full exact-action approval binding, expiry, one-use consumption, transactionally atomic decision-plus-dispatch, or independent external-effect reconciliation. The existing queue provides none of those guarantees. Unchanged no-approval workflows continue to route; trusted classification and mandatory approval derivation remain separate work. The governed gateway's caller-declared action class and token scope require further repair before a release safety claim.

Independent reviewer launch failed because the host could not persist the spawned-agent relationship. No independent approval is claimed. Keep the PR draft until review and broader integration checks complete. No merge, deployment, dependency installation, live action, credentials or permission changes.

## Subsequent independent review

Independent reviewer successfully retried review at code commit 82b1b8daa23e41cfedbafa9b1615161eaec49b18. No actionable defects found in the scoped repair; reviewer independently ran both focused graph/gating test files: 28 passed. Recommendation: accept the narrow repair, without transferring that conclusion to exact action binding or replay guarantees. Current-head Actions query still returned zero runs. This addendum updates the earlier reviewer-launch limitation; keep CI and broader release gates open.
