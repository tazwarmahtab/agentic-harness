# AOS — First Run Guide

## Prerequisites
- Python 3.14+ (via [uv](https://github.com/astral-sh/uv))
- `.env` configured (copy from `.env.example`)

## Step 1: Setup

```bash
cd ~/Documents/10-Projects/Agentic\ Harness
uv venv --python 3.14
source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env   # fill in AOS_API_TOKEN + ANTHROPIC_API_KEY
```

## Step 2: Validate Everything

```bash
python -m aos validate
# Expected: All 13 harnesses validated, 0 errors
```

## Step 3: Check Status

```bash
python -m aos status
# Expected: System operational, memory loaded, LLM connected
```

## Step 4: Dry-Run Netso Executive

```bash
python -m aos run --venture netso --dry-run
# Expected: Pipeline executes in dry-run mode, no LLM calls made
```

## Step 5: Run Tests

```bash
pytest -q
# Expected: 898+ tests passing
```

## Step 6: Run Evaluator Golden Tests

```bash
python -m aos evaluator --golden-dir tests/golden
# Expected: All 9 golden tests pass (CFO blended rate, DSCR, PPA, savings, Scenario B, NEM export, CAPEX, risk agent)
```

## Step 7: Start Dashboard

```bash
python -m aos api --port 8642
# Open http://localhost:8642/docs for API docs
# Open odysseus/dashboard/preview.html for the UI
```

## Step 8: Check Approvals

```bash
python -m aos approvals list
# Expected: Empty queue (nothing pending)
```

## What Just Happened

You validated the full AOS stack:

1. **Manifests loaded** — 13 harnesses, 52+ agents, 176 YAML files parsed
2. **Engine verified** — LangGraph StateGraph compiles and runs
3. **Evaluator tested** — 8 financial hard-fail checks (DSCR, PPA, blended rate, savings, Scenario B, NEM export, CAPEX, true variable rate)
4. **Memory ready** — SQLite-backed store with vector search
5. **Dashboard live** — 24+ pages, real-time WebSocket
6. **All tests pass** — 898+ unit, integration, and golden tests

## Troubleshooting

### `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`

The hermes-agent venv (Python 3.11) leaks into sys.path. Fix:

```python
# Add to top of your script:
import sys
sys.path[:] = [p for p in sys.path if 'hermes-agent/venv' not in p]
```

Or use the built-in utility:

```python
from aos._venv_compat import clean_sys_path  # auto-cleans on import
```

### `AOS_API_TOKEN` missing

```bash
export AOS_API_TOKEN=$(openssl rand -hex 32)
# Add to .env permanently
echo "AOS_API_TOKEN=$AOS_API_TOKEN" >> .env
```

### Dashboard shows "Connection refused"

Start the API server first:

```bash
python -m aos api --port 8642 &
```
