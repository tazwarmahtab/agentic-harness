# AOS — Agentic Operating System (Project Claude Context)

## Identity
Governance-first, multi-venture agentic operating system (Python 3.12+, Pydantic v2, FastAPI, LangGraph). Orchestrates AI workflows (harnesses) for Netso Energy + future ventures. Entry point: `python -m aos`.

## Directory Structure
<!-- Run `ls` to see current layout -->


## Quick Start
<!-- See README.md for setup instructions -->
**Important:** Always activate the venv first: `source .venv/bin/activate`
Tests: `python -m pytest -q` (~7 min for 1050 tests)


## Code Style
- PEP 8 + type annotations on every public function signature.
- Frozen dataclasses / NamedTuple for immutable data; `@dataclass(frozen=True)` preferred.
- `ruff` for lint + format (single tool, no `black`/`isort`).
- Pydantic v2 models for all I/O boundaries.
- LangGraph: StateGraph nodes are functions; state is dict-like, return new objects, never mutate.
- No `print()` in source — use `logging`. No `console.log` in committed code.

## Testing
```bash
pytest -q                                    # fast
pytest --cov=aos --cov=odysseus --cov-report=term-missing   # with coverage
pytest -m unit    # unit only
pytest -m integration  # integration only (requires live deps)
```
- Coverage minimum: 60% (`fail_under = 60` in pyproject.toml). Source: `aos` + `odysseus`, branch coverage enabled.
- `asyncio_mode = "auto"` — no manual `@pytest.mark.asyncio` needed; async tests run automatically.
- Test root: `tests/` (configured via `testpaths`).
- AAA pattern. Use `@pytest.mark.unit` / `@pytest.mark.integration` to categorize.
- Strategic surfaces: approval-gate blocking, path sanitization, WS auth, evaluator financial checks, cross-harness dispatch.

## Environment
| Variable | Required | Default | Purpose |
|---|---|---|---|
| `AOS_API_TOKEN` | Yes | — | WS + harness access bearer token (generate with `openssl rand -hex 32`) |
| `ANTHROPIC_API_KEY` | Yes | — | Primary LLM auth (Claude via 9router or direct) |
| `ANTHROPIC_AUTH_TOKEN` | No | — | Anthropic auth token (alternative auth flow) |
| `ANTHROPIC_BASE_URL` | No | Official Anthropic endpoint | Override Anthropic API endpoint |
| `AOS_LLM_BASE_URL` | No | `http://localhost:20128` | Local LLM router (Ollama, vLLM, 9router) |
| `AOS_LLM_API_KEY` | No | — | Auth for local router if required |
| `NVIDIA_NIM_API_KEY` | No | — | GPU-accelerated inference via NVIDIA NIM |
| `AOS_PAID_TIER` | No | — | Set `"1"` for paid/faster models (free tier uses OpenRouter round-robin) |
| `AOS_FREE_TIER` | No | — | Set `"1"` to route medium/low criticality agents to free model pool (legacy `TAZOS_FREE_TIER` accepted) |
| `AOS_TRACING` | No | `enabled` | `"enabled"` or `"disabled"` |
| `AOS_TRACING_BACKEND` | No | `auto` | `"auto"`, `"langfuse"`, or `"json"` (stdout) |
| `LANGFUSE_PUBLIC_KEY` | No | — | Langfuse public API key (from https://cloud.langfuse.com) |
| `LANGFUSE_SECRET_KEY` | No | — | Langfuse secret API key |
| `LANGFUSE_HOST` | No | `https://cloud.langfuse.com` | Override Langfuse endpoint (for self-hosted) |
| `DATABASE_URL` | No | — | Postgres connection string for CocoIndex RAG pipeline + pgvector (e.g. `postgresql://postgres:aos@localhost:5432/aos`). When set, RAG auto-activates: relevant Netso venture doc chunks are injected into every agent's system prompt via `_run_agent_node`. |

## 9router Model Routing
All LLM calls route through 9router (localhost:20128) unless overridden.

### Routing Manifest System (New)
AOS now uses **venture-specific routing manifests** to define model routing logic. Each venture declares:

1. **DAG of allowed model transitions** — prevents invalid fallback paths
2. **Criticality-to-model mapping** — venture-specific overrides
3. **Fallback path** — guaranteed Hamiltonian path through the DAG
4. **Circuit breaker thresholds** — per-model failure limits

Manifests are validated at harness load time and stored in `aos/ventures/[venture]/routing.manifest.json`.

**Example (Netso Energy):**
```json
{
  "version": "1.0",
  "venture": "netso",
  "dag": [["reasoning", "default"], ["default", "fast"], ["fast", "free"]],
  "criticality_map": {
    "critical": "reasoning",
    "high": "default",
    "medium": "fast",
    "low": "free"
  },
  "fallback_path": ["reasoning", "default", "fast", "free"],
  "circuit_breaker": {
    "reasoning": {"failure_threshold": 3, "recovery_window_sec": 600},
    "default": {"failure_threshold": 5, "recovery_window_sec": 300}
  }
}
```

**Primary models (via MODEL_TABLE lookup):**
- `cu/claude-4.5-sonnet` — default (critical + high criticality)
- `cu/claude-4.5-opus-high-thinking` — reasoning (direct lookup only, never via criticality)
- `cu/claude-4.5-haiku` — fast/subagent tier

**Free-tier round-robin (CRITICALITY_TO_MODEL for medium/low agents):**
FREE_MODEL_POOL cycles through 6 models: openrouter/google/gemma-4-31b-it:free, openrouter/nvidia/stepfun-ai/step-3.7-flash, openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free, openrouter/qwen/qwen3-next-80b-a3b-instruct:free, openrouter/meta/llama-4-scout-17b-16e-instruct, openrouter/google/gemini-2.5-flash. Thread-safe counter with Lock.

**Criticality mapping (fallback when no manifest):**
- critical → default (paid Sonnet)
- high → default (paid Sonnet)
- medium → free (round-robin)
- low → free (round-robin)

**Key behaviors:**
- `AOS_PAID_TIER=1` forces fast-tier subagents to paid cu/claude-4.5-haiku instead of free round-robin
- Model-level fallback: on 9router failure, retries with default → fast → free tier models (3 retries each, exponential backoff)
- HTTP 404 breaks immediately to next model; other errors retry up to 3 times
- Reasoning fallback: if response has empty content but non-empty reasoning field, reasoning text is used as content

## Hardening Rules / Gotchas (NON-NEGOTIABLE)
1. **Path traversal**: all user-supplied paths must pass `sanitize_path()` — blocks URL-encoded traversal, null bytes, backslashes, absolute paths, tilde expansion, `..` normalization bypasses.
2. **WebSocket auth**: WS endpoint requires `AOS_API_TOKEN` env var.
3. **Approval gates**: orchestrate gates poll `wait_for_decision()` and block execution; never replace with fire-and-forget.
4. **Shell execution**: subprocess paths use regex allowlist + shlex validation; new executors must mirror `aos/hardening.py` patterns.
5. **Connection limiter**: WS endpoint caps concurrency (default 10); wire into any new socket handlers.
6. **Timing data**: graph nodes (`approval_gates`, `execute`, `log`, `loop_control`) emit `duration_ms` — preserve when refactoring.
7. **Financial constants**: all numbers sourced from `GROUND_TRUTH_CONSTANTS.md`; blended rate BDT 14.81 is **never** used for savings — true variable rate BDT 12.98 is correct.
8. **Null byte detection**: `sanitize_path()` rejects `\x00` in any user-supplied path — dangerous in C-backed path operations (open, stat).
9. **Normalization bypass detection**: `sanitize_path()` compares `posixpath.normpath(path)` against original; if `//` or `/.` segments are present and normalization changed the string, the path is rejected.
10. **Thread-safe rate limiting**: `RateLimiter` and `ConnectionLimiter` use `threading.Lock` — never bypass locks when accessing shared state from async or multi-threaded callers.

## CLI Reference
<!-- Run `python -m aos --help` for full CLI reference -->

## Key Commands Reference
| Command | Purpose |
|---|---|
| `pytest -q` | test suite |
| `pytest --cov=aos --cov=odysseus --cov-report=term-missing` | coverage with missing lines |
| `python -m aos status` | system / harness status |
| `python -m aos run --venture netso --dry-run` | dry-run harness cycle |
| `python -m aos orchestrate --one-liner "..."` | full pipeline |
| `ruff check .` | lint |
| `ruff format .` | format |

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

## References
- `README.md`: design philosophy + build order
- `FIXLIST.md`: audit backlog + scoring history
- `DESIGN.md`: design system (typography, colors, spacing, aesthetic direction)
- `docs/`: phase documentation and architecture notes
- `aos/ventures/netso/`: Netso venture binding (financial constants)
- `.env.example`: all environment variables

## GBrain Search Guidance (configured by /sync-gbrain)
<!-- gstack-gbrain-search-guidance:start -->

GBrain is set up and synced on this machine. The agent should prefer gbrain
over Grep when the question is semantic or when you don't know the exact
identifier yet. Two indexed corpora available via the `gbrain` CLI:
- This repo's code (registered as `gstack-code-<repo>` source).
- `~/.gstack/` curated memory (registered as `gstack-brain-<user>` source via
  the existing federation pipeline).

Prefer gbrain when:
- "Where is X handled?" / semantic intent, no exact string yet:
    `gbrain search "<terms>"` or `gbrain query "<question>"`
- "Where is symbol Y defined?" / symbol-based code questions:
    `gbrain code-def <symbol>` or `gbrain code-refs <symbol>`
- "What calls Y?" / "What does Y depend on?":
    `gbrain code-callers <symbol>` / `gbrain code-callees <symbol>`
- "What did we decide last time?" / past plans, retros, learnings:
    `gbrain search "<terms>" --source gstack-brain-<user>`

Grep is still right for known exact strings, regex, multiline patterns, and
file globs. The brain auto-syncs incrementally on every gstack skill start.
Run `/sync-gbrain` to force-refresh, `/sync-gbrain --full` for full reindex.

<!-- gstack-gbrain-search-guidance:end -->

## Permissions
- Auto mode enabled as default (`permissions.defaultMode: auto` in `~/.claude/settings.json`)
- Revert: set `defaultMode` back to `"default"` in settings

## Skill routing

**Context budget note:** gstack skills inject ~30-55KB each at invocation. If context fills fast, disable unused gstack skills via `/doctor` or reduce SessionStart hooks.

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
- Author a backlog-ready spec/issue → invoke /spec
