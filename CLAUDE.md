# AOS — Agentic Operating System (Project Claude Context)

## Identity
Governance-first, multi-venture agentic operating system (Python 3.12+, Pydantic v2, FastAPI, LangGraph). Orchestrates AI workflows (harnesses) for Netso Energy + future ventures. Entry point: `python -m aos`.

## Directory Structure
.
├── pyproject.toml    # hatchling build, deps, pytest config
├── .env.example      # all env vars (AOS_* prefixed)
├── FIXLIST.md        # audit backlog + scoring history
├── README.md         # design philosophy + build order
├── aos/              # main package
│   ├── __main__.py   # CLI entry point (validate/status/run/orchestrate/ventures/approvals)
│   ├── graph.py      # LangGraph StateGraph runtime
│   ├── orchestrate/  # end-to-end pipeline (spec→plan→implement→review→ship)
│   │   ├── pipeline.py  # OrchestratePipeline
│   │   └── gates.py     # GateManager + GateDecision
│   ├── registry.py   # harness/agent registry + cross-harness dispatch
│   ├── validator.py  # manifest validation
│   ├── llm.py        # LLM routing (Anthropic + local Ollama + NVIDIA NIM)
│   ├── context.py    # system-prompt assembly from agent manifest
│   ├── usage.py      # per-agent per-model token tracking
│   ├── evaluator.py  # 5 financial checks (blended rate, savings %, DSCR, PPA, Scenario B)
│   ├── memory.py     # SQLite-backed persistent memory store
│   ├── approval_queue.py  # persistent approval queue (JSONL)
│   ├── platform/     # JSON schemas (identity, harness, agent, policy)
│   └── ventures/netso/    # Netso venture binding (financial constants, artifacts)
├── odysseus/         # Thin proxy layer + JS dashboard
│   ├── routes/       # AOS proxy (REST + WebSocket relay)
│   │   └── aos_routes.py
│   └── dashboard/    # Vanilla JS SPA (no build step)
│       ├── *.js      # 9 page modules + store + keyboard nav
│       ├── services/ # JS clients (api.js, websocket.js, keyboard.js)
│       └── dashboard.css / dashboard-a11y.css
├── tests/            # pytest suite (target 80%+ coverage)
├── docs/             # phase docs + architecture notes
├── ops/              # operational runbooks / configs
└── .claude/skills/   # project-specific Claude skills

## Quick Start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in AOS_API_TOKEN + ANTHROPIC_API_KEY
pytest                 # run suite (~600 tests)
python -m aos status   # show system status
python -m aos run --venture netso --dry-run   # dry-run a harness cycle
```

## Code Style
- PEP 8 + type annotations on every public function signature.
- Frozen dataclasses / NamedTuple for immutable data; `@dataclass(frozen=True)` preferred.
- `ruff` for lint + format; no `black`/`isort` in pyproject yet (ruff is the single tool).
- Pydantic v2 models for all I/O boundaries.
- LangGraph: StateGraph nodes are functions; state is dict-like, return new objects, never mutate in place.
- No `print()` in source — use `logging`. No `console.log` in committed code.

## Testing
```bash
pytest -q                                    # fast
pytest --cov=aos --cov=odysseus --cov-report=term-missing   # with coverage
pytest -m unit    # unit only
pytest -m integration  # integration only (requires live deps)
```
- Target 80%+ coverage.
- AAA pattern. Use `@pytest.mark.unit` / `@pytest.mark.integration`.
- Strategic surfaces: approval-gate blocking, path sanitization, WS auth, evaluator financial checks, cross-harness dispatch.

## Environment
Variable | Required | Purpose
---|---|---
`AOS_API_TOKEN` | Yes | WS + harness access bearer token
`ANTHROPIC_API_KEY` | Yes | Primary LLM auth (Claude via 9router or direct)
`ANTHROPIC_BASE_URL` | No | Override Anthropic endpoint
`AOS_LLM_BASE_URL` | No | Local LLM router (default http://localhost:20128)
`AOS_LLM_API_KEY` | No | Auth for local router if required
`NVIDIA_NIM_API_KEY` | No | GPU-accelerated inference via NVIDIA NIM
`AOS_PAID_TIER` | No | Set `"1"` for paid/faster models
`AOS_TRACING` | No | `"enabled"` (default) or `"disabled"`
`AOS_TRACING_BACKEND` | No | `"auto"`, `"langfuse"`, or `"json"`
`LANGFUSE_PUBLIC_KEY` | No | Langfuse tracing
`LANGFUSE_SECRET_KEY` | No | Langfuse tracing
`LANGFUSE_HOST` | No | Override Langfuse endpoint

### 9router model routing
Model IDs (via 9router at localhost:20128):
- `cu/claude-4.5-sonnet` — default
- `cu/claude-4.5-opus-high-thinking` — deep reasoning
- `cu/claude-4.5-haiku` — fast/simple

## Hardening Rules / Gotchas (NON-NEGOTIABLE)
1. **Path traversal**: all user-supplied paths must pass `sanitize_path()` — blocks URL-encoded traversal, null bytes, backslashes, absolute paths, tilde expansion, `..` normalization bypasses.
2. **WebSocket auth**: WS endpoint requires `AOS_API_TOKEN` env var.
3. **Approval gates**: orchestrate gates poll `wait_for_decision()` and block execution; never replace with fire-and-forget.
4. **Shell execution**: subprocess paths use regex allowlist + shlex validation; new executors must mirror `aos/hardening.py` patterns.
5. **Connection limiter**: WS endpoint caps concurrency (default 10); wire into any new socket handlers.
6. **Timing data**: graph nodes (`approval_gates`, `execute`, `log`, `loop_control`) emit `duration_ms` — preserve when refactoring.
7. **Financial constants**: all numbers sourced from `GROUND_TRUTH_CONSTANTS.md`; blended rate BDT 14.81 is **never** used for savings — true variable rate BDT 12.98 is correct.

## CLI Reference
Command | Purpose
---|---
`python -m aos validate [--harness NAME] [--venture NAME]` | Validate all manifests
`python -m aos status [--harness NAME] [--venture NAME]` | Show registry status
`python -m aos run --venture netso [--dry-run] [--prefer router]` | Execute a harness cycle
`python -m aos orchestrate --one-liner "..." [plan_path]` | End-to-end: spec → plan → implement → review → ship
`python -m aos ventures` | List discovered ventures
`python -m aos approvals [list\|approve-all\|reject-all\|approve ID\|reject ID]` | Manage approval queue

## Key Commands Reference
Command | Purpose
---|---
`pytest -q` | test suite
`pytest --cov=aos --cov=odysseus --cov-report=term-missing` | coverage with missing lines
`python -m aos status` | system / harness status
`python -m aos run --venture netso --dry-run` | dry-run harness cycle
`python -m aos orchestrate --one-liner "..."` | full pipeline
`ruff check .` | lint
`ruff format .` | format

## References
- `README.md`: design philosophy + build order
- `FIXLIST.md`: audit backlog + scoring history (composite 2.8→8.5/10)
- `docs/`: phase documentation and architecture notes
- `aos/ventures/netso/`: Netso venture binding (financial constants)
- `.env.example`: all environment variables
