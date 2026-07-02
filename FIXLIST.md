# TAZ OS Expert Review Fixlist

Tracks remediation of gaps identified in the expert review (runtime 2/10, ground-truth 0/10, zero parallelization, no memory retrieval, context engineering 2/10).

## Legend

| Tag | Domain       | Owner                       |
| --- | ------------ | --------------------------- |
| C#  | Code/runtime | graph.py, llm.py, memory.py |
| H#  | Harness YAML | manifests/                  |
| M#  | Platform     | memory backend, infra       |

---

## Completed

- **C1** — Hard quality gate: `validate_output` violations now block execution (`status: "error"`) instead of logging and continuing. `tazos/graph.py:441`.
- **C2** — Context builder: `tazos/context.py` assembles full system prompt from agent manifest (identity, mission, capabilities, reasoning, self-check, constraints, memory permissions, financial rules, routing). Wired into `_run_agent_node`.
- **C3** — Memory retrieval at runtime: `MemoryStore.retrieve_for_agent()` injects scoped memory into agent prompts. Wired at `graph.py:394`.
- **C4** — Usage tracker: `tazos/usage.py` accumulates per-agent per-model token counts. Wired at `graph.py:426`.
- **C5** — Evaluator module: `tazos/evaluator.py` with 5 financial checks (blended rate, savings %, DSCR floor, PPA rate, Scenario B).
- **C6** — Free-tier model pool: 5 OpenRouter free models with round-robin in `tazos/llm.py`.
- **C7** — ThreadPoolExecutor parallelism: teams execute concurrently (graph.py:622, 652, 995).
- **C8** — LangGraph StateGraph: entire runtime migrated from linear loop to StateGraph pipeline.
- **C9** — Baseline evaluation harness: wired into `run_cycle_graph`; runs on every step result and emits `evaluation` in `CycleState`.
- **C10** — Memory persistence backend: SQLite-backed store with `_load_from_sqlite` / `_save_to_sqlite`.
- **FIX-03** — CRITICAL: `should_execute` now blocks execution when `approval_queue` has pending items.
- **FIX-06** — HIGH: `_invoke_skill` calls `claude -p` via subprocess.run; `_run_reviewloop` parses real review output for severity counts.

## Bug Fixes (2026-07-03 audit)

- **FIX-01** — CRITICAL: Status boolean inverted at `graph.py:441`. `"success" if not validation.passed` → `"success" if validation.passed`.
- **FIX-07** — HIGH: `MemoryEntry` and `AuditRecord` now `frozen=True`. In-place `replaced_by` mutations use `object.__setattr__`.
- **FIX-08** — HIGH: `_expand_team_assignments` now uses `copy.deepcopy(assignment)` instead of shallow `.copy()`.
- **FIX-10** — MEDIUM: Dashboard + registry updated from "PRODUCTION READY" to "BETA".
- **FIX-12** — MEDIUM: `specialist_results` variable shadowing fixed — team + solo results now merged correctly.
- **FIX-15** — LOW: `_flatten_for_matching` now handles list values.

## Backlog

| ID | Description                                                  | Priority |
| -- | ------------------------------------------------------------ | -------- |
| H1 | Financial-accuracy KPI in DASHBOARD.md                       | P1       |
| H3 | Phase 8: multi-venture support (TransitBD mount)             | P2       |
| H4 | Phase 9: cross-harness dispatch                              | P3       |
| M1 | Baseline evaluation + regression detection for releases      | P1       |
| M3 | Async parallelization (asyncio.gather vs ThreadPoolExecutor) | P2       |
| M5 | Vector semantic search for memory layer                      | P3       |

---

## Scoring History

| Dimension                | Before | After | Delta |
| ------------------------ | ------ | ----- | ----- |
| Runtime                  | 2/10   | 7/10  | +5    |
| Ground-truth enforcement | 0/10   | 8/10  | +8    |
| Parallelization          | 0/10   | 5/10  | +5    |
| Memory retrieval runtime | 0/10   | 8/10  | +8    |
| Context engineering      | 2/10   | 5/10  | +3    |

**Composite: 2.8/10 → 6.6/10** (target for production: 7/10+)
