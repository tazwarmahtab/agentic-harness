# TAZ OS Expert Review Fixlist

Tracks remediation of gaps identified in the expert review (runtime 2/10, ground-truth 0/10, zero parallelization, no memory retrieval, context engineering 2/10).

## Legend
| Tag | Domain | Owner |
|-----|--------|-------|
| C# | Code/runtime | graph.py, llm.py, memory.py |
| H# | Harness YAML | manifests/ |
| M# | Platform | memory backend, infra |

---

## Completed

- [x] **C1** — Hard quality gate: `validate_output` violations now block execution (`status: "error"`) instead of logging and continuing. `tazos/graph.py:441`.
- [x] **C2** — Context builder: `tazos/context.py` assembles full system prompt from agent manifest (identity, mission, capabilities, reasoning, self-check, constraints, memory permissions, financial rules, routing). Wired into `_run_agent_node`.
- [x] **C3** — Memory retrieval at runtime: `MemoryStore.retrieve_for_agent()` injects scoped memory into agent prompts. Wired at `graph.py:394`.
- [x] **C4** — Usage tracker: `tazos/usage.py` accumulates per-agent per-model token counts. Wired at `graph.py:426`.
- [x] **C5** — Evaluator module: `tazos/evaluator.py` with 5 financial checks (blended rate, savings %, DSCR floor, PPA rate, Scenario B).
- [x] **C6** — Free-tier model pool: 5 OpenRouter free models with round-robin in `tazos/llm.py`.
- [x] **C7** — ThreadPoolExecutor parallelism: teams execute concurrently (graph.py:622, 652, 995).
- [x] **C8** — LangGraph StateGraph: entire runtime migrated from linear loop to StateGraph pipeline.

## In Progress

- [ ] **C9** — Baseline evaluation harness: quantitative metrics for financial-accuracy rate, token cost per cycle, output quality. *(stub scaffolded, tests pending)*
- [ ] **C10** — Memory persistence backend: replace in-memory defaultdict with JSON/sqlite store. *(design doc needed)*

## Backlog

| ID | Description | Priority |
|----|-------------|----------|
| H1 | Financial-accuracy KPI in DASHBOARD.md | P1 |
| H2 | Approval queue gating wired into graph nodes | P2 |
| H3 | Phase 8: multi-venture support (TransitBD mount) | P2 |
| H4 | Phase 9: cross-harness dispatch | P3 |
| M1 | Baseline evaluation + regression detection | P1 |
| M2 | Memory persistence backend (sqlite/json) | P1 |
| M3 | Async parallelization (asyncio.gather vs ThreadPoolExecutor) | P2 |
| M4 | Dashboard reflects actual status (not "production ready") | P2 |
| M5 | Vector semantic search for memory layer | P3 |

---

## Scoring History

| Dimension | Before | After | Delta |
|-----------|--------|-------|-------|
| Runtime | 2/10 | 4/10 | +2 |
| Ground-truth enforcement | 0/10 | 7/10 | +7 |
| Parallelization | 0/10 | 4/10 | +4 |
| Memory retrieval runtime | 0/10 | 5/10 | +5 |
| Context engineering | 2/10 | 5/10 | +3 |

**Composite: 2.8/10 → 5.0/10** (target for production: 7/10+)
