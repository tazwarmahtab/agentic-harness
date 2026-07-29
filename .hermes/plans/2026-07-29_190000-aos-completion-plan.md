# AOS — Complete System Finish Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.
> Each task is bite-sized (2-5 min). TDD where code is produced. Commit after every task.
> Dispatch implementer → spec reviewer → quality reviewer per task.

**Goal:** Take AOS from 8.5/10 BETA to 10/10 PRODUCTION — fix environment, add hardening, monitoring, alerting, documentation, and operational tooling so the system is fully usable for Netso Energy and future ventures.

**Architecture:** The system is architecturally complete (LangGraph StateGraph, 13 harnesses, 52 agents, evaluator, memory, dashboard). This plan covers the remaining 15% — environment fixes, pre-commit hooks, type safety, structured alerting, cost tracking, error reporting, env validation, documentation, and a "First Run" guide that proves the system works end-to-end.

**Tech Stack:** Python 3.14, Pydantic v2, FastAPI, LangGraph, SQLite, uv, ruff, mypy, pytest, pre-commit, optional: slack-sdk/webhooks, sentry-sdk.

---

## Phase 0: Environment Fix (Unblocks Everything Else)

### Task 0.1: Fix pydantic_core import leak in hermes venv

**Objective:** Stop hermes-agent's Python 3.11 site-packages from poisoning the AOS project's Python 3.14 venv.

**Files:**
- Modify: `.venv/pyvenv.cfg` (verify `include-system-site-packages = false`)
- Modify: `pyproject.toml` (add `[tool.pythonpath]` or sys.path guard)
- Create: `aos/_venv_compat.py` (sys.path cleanup utility)
- Test: `tests/test_venv_compat.py`

**Step 1: Write failing test**

```python
# tests/test_venv_compat.py
def test_venv_compat_hermes_paths_excluded():
    """After importing _venv_compat, hermes-agent paths should not be in sys.path."""
    import sys
    from aos._venv_compat import clean_sys_path
    original = sys.path.copy()
    # Simulate hermes path injection
    sys.path.insert(0, '/Users/tazwarmahtab/.hermes/hermes-agent/venv/lib/python3.11/site-packages')
    clean_sys_path()
    hermes_paths = [p for p in sys.path if 'hermes-agent/venv' in p]
    assert len(hermes_paths) == 0, f"Hermes paths still in sys.path: {hermes_paths}"
    sys.path = original  # restore

def test_venv_compat_preserves_aos_paths():
    """AOS project paths should remain in sys.path."""
    import sys
    from aos._venv_compat import clean_sys_path
    original = sys.path.copy()
    sys.path.insert(0, '/Users/tazwarmahtab/.hermes/hermes-agent/venv/lib/python3.11/site-packages')
    clean_sys_path()
    aos_paths = [p for p in sys.path if '10-Projects/Agentic Harness' in p or 'uv' in p.lower()]
    assert len(aos_paths) > 0, "AOS project paths removed by clean_sys_path"
    sys.path = original
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_venv_compat.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aos._venv_compat'`

**Step 3: Write minimal implementation**

```python
# aos/_venv_compat.py
"""Sys-path cleanup utility for environments where hermes-agent venv leaks into sys.path."""
from __future__ import annotations
import sys

def clean_sys_path() -> None:
    """Remove hermes-agent venv site-packages from sys.path if present."""
    sys.path[:] = [p for p in sys.path if 'hermes-agent/venv' not in p]

# Auto-clean on import if hermes paths are detected
if any('hermes-agent/venv' in p for p in sys.path):
    clean_sys_path()
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_venv_compat.py -v`
Expected: PASS (2/2)

**Step 5: Commit**

```bash
git add aos/_venv_compat.py tests/test_venv_compat.py
git commit -m "fix: add sys.path cleanup for hermes venv leak"
```

---

### Task 0.2: Add .env validation at startup

**Objective:** Validate required environment variables exist and are non-empty when `python -m aos` runs.

**Files:**
- Create: `aos/env_check.py`
- Modify: `aos/__main__.py` (import env_check at startup)
- Test: `tests/test_env_check.py`

**Step 1: Write failing test**

```python
# tests/test_env_check.py
import os
from aos.env_check import validate_env, EnvVar

def test_validate_env_passes_with_required_vars(monkeypatch):
    monkeypatch.setenv("AOS_API_TOKEN", "test-token-123")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-456")
    result = validate_env(required=["AOS_API_TOKEN", "ANTHROPIC_API_KEY"])
    assert result.ok is True
    assert result.missing == []

def test_validate_env_fails_on_missing_var(monkeypatch):
    monkeypatch.delenv("AOS_API_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = validate_env(required=["AOS_API_TOKEN", "ANTHROPIC_API_KEY"])
    assert result.ok is False
    assert "AOS_API_TOKEN" in result.missing

def test_validate_env_warns_on_empty_var(monkeypatch):
    monkeypatch.setenv("AOS_API_TOKEN", "")
    result = validate_env(required=["AOS_API_TOKEN"])
    assert result.ok is False
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_env_check.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aos.env_check'`

**Step 3: Write minimal implementation**

```python
# aos/env_check.py
"""Validate required environment variables at startup."""
from __future__ import annotations
from dataclasses import dataclass, field
import os
import logging

logger = logging.getLogger("aos.env")

@dataclass
class EnvVar:
    name: str
    required: bool = True

@dataclass
class EnvCheckResult:
    ok: bool = True
    missing: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

def validate_env(required: list[str] | None = None, optional: list[str] | None = None) -> EnvCheckResult:
    result = EnvCheckResult()
    for name in (required or []):
        val = os.environ.get(name, "")
        if not val.strip():
            result.ok = False
            result.missing.append(name)
            logger.error(f"Required env var {name} is missing or empty")
    for name in (optional or []):
        val = os.environ.get(name, "")
        if not val.strip():
            result.warnings.append(name)
            logger.warning(f"Optional env var {name} is not set")
    return result
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_env_check.py -v`
Expected: PASS (3/3)

**Step 5: Commit**

```bash
git add aos/env_check.py tests/test_env_check.py
git commit -m "feat: add .env validation at startup"
```

---

### Task 0.3: Wire env_check into __main__.py

**Objective:** Run env validation when `python -m aos` is invoked, print warnings/errors.

**Files:**
- Modify: `aos/__main__.py` (add env check call after arg parsing)
- Test: `tests/test_env_check.py` (add integration test)

**Step 1: Write failing test**

```python
def test_main_warns_on_missing_env(capsys, monkeypatch):
    monkeypatch.delenv("AOS_API_TOKEN", raising=False)
    from aos.__main__ import main
    # Should print warning but not crash on --help
    import sys
    monkeypatch.setattr(sys, 'argv', ['aos', '--help'])
    try:
        main()
    except SystemExit:
        pass
    captured = capsys.readouterr()
    assert "AOS_API_TOKEN" in captured.out or "AOS_API_TOKEN" in captured.err
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_env_check.py::test_main_warns_on_missing_env -v`
Expected: FAIL (env check not wired)

**Step 3: Wire env check**

In `aos/__main__.py`, add after the logging setup:

```python
from aos.env_check import validate_env
env_result = validate_env(required=["AOS_API_TOKEN"], optional=["ANTHROPIC_API_KEY", "AOS_LLM_BASE_URL"])
if not env_result.ok:
    print(f"⚠️  Missing required env vars: {', '.join(env_result.missing)}", file=sys.stderr)
    print("   Copy .env.example to .env and fill in the values.", file=sys.stderr)
if env_result.warnings:
    print(f"ℹ️  Optional env vars not set: {', '.join(env_result.warnings)}", file=sys.stderr)
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_env_check.py -v`
Expected: PASS (4/4)

**Step 5: Commit**

```bash
git add aos/__main__.py
git commit -m "feat: wire env validation into CLI startup"
```

---

## Phase 1: Hardening (Pre-commit, Type Safety, Lint)

### Task 1.1: Add pre-commit configuration

**Objective:** Add `.pre-commit-config.yaml` with ruff format + ruff check hooks.

**Files:**
- Create: `.pre-commit-config.yaml`
- Test: `pre-commit run --all-files` (should pass on clean tree)

**Step 1: Write .pre-commit-config.yaml**

```yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.5.0
    hooks:
      - id: ruff-format
      - id: ruff
        args: [--fix]
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.10.0
    hooks:
      - id: mypy
        args: [--ignore-missing-imports]
        additional_dependencies: [pydantic>=2.0]
```

**Step 2: Verify it passes on clean tree**

Run: `pre-commit run --all-files`
Expected: All hooks pass (ruff clean, mypy clean or only pre-existing warnings)

**Step 3: Commit**

```bash
git add .pre-commit-config.yaml
git commit -m "chore: add pre-commit hooks (ruff, mypy)"
```

---

### Task 1.2: Fix DASHBOARD.md BETA inconsistency

**Objective:** Update DASHBOARD.md to match the BETA status.

**Files:**
- Modify: `ops/DASHBOARD.md` (line 7: change "PRODUCTION" to "BETA")

**Step 1: Fix the line**

Change `**Status:** PRODUCTION` to `**Status:** BETA`

**Step 2: Commit**

```bash
git add ops/DASHBOARD.md
git commit -m "fix: DASHBOARD.md status to BETA (matches FIX-10)"
```

---

## Phase 2: Monitoring & Alerting (P1 Gap)

### Task 2.1: Create structured alerting module

**Objective:** Create `aos/alerting.py` with webhook support for financial breaches (DSCR < 2.0, wrong PPA, blended rate in savings).

**Files:**
- Create: `aos/alerting.py`
- Test: `tests/test_alerting.py`

**Step 1: Write failing test**

```python
# tests/test_alerting.py
from unittest.mock import patch, MagicMock
from aos.alerting import AlertingService, Alert

def test_alert_dscr_breach():
    svc = AlertingService(webhook_url=None)  # no webhook = just log
    alert = Alert(
        level="critical",
        source="evaluator",
        message="DSCR 1.8 below alert floor 2.0",
        venture="netso"
    )
    # Should not raise
    svc.send(alert)

@patch("aos.alerting.httpx")
def test_alert_webhook_sends_http(mock_httpx):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_httpx.post.return_value = mock_resp
    svc = AlertingService(webhook_url="https://hooks.slack.com/test")
    alert = Alert(level="critical", source="evaluator", message="PPA deviation", venture="netso")
    svc.send(alert)
    mock_httpx.post.assert_called_once()
    call_args = mock_httpx.post.call_args
    assert "hooks.slack.com" in str(call_args)

def test_alert_empty_url_just_logs():
    svc = AlertingService(webhook_url="")
    alert = Alert(level="warning", source="evaluator", message="test", venture="netso")
    svc.send(alert)  # should not raise
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_alerting.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'aos.alerting'`

**Step 3: Write minimal implementation**

```python
# aos/alerting.py
"""Structured alerting for financial breaches and system events."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("aos.alerting")

@dataclass(frozen=True)
class Alert:
    level: str  # "critical", "warning", "info"
    source: str  # "evaluator", "graph", "approval", "system"
    message: str
    venture: str = "unknown"
    metadata: dict[str, Any] = field(default_factory=dict)

class AlertingService:
    def __init__(self, webhook_url: str | None = None):
        self.webhook_url = webhook_url
        self._sent: list[Alert] = []

    def send(self, alert: Alert) -> None:
        """Send alert via webhook (if configured) and always log."""
        self._sent.append(alert)
        log_fn = logger.critical if alert.level == "critical" else logger.warning
        log_fn(f"[{alert.level.upper()}] {alert.source}: {alert.message} (venture={alert.venture})")
        if self.webhook_url:
            self._send_webhook(alert)

    def _send_webhook(self, alert: Alert) -> None:
        try:
            import httpx
            payload = {
                "text": f"[{alert.level.upper()}] {alert.source}: {alert.message}",
                "venture": alert.venture,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            httpx.post(self.webhook_url, json=payload, timeout=10.0)
        except Exception as e:
            logger.error(f"Webhook delivery failed: {e}")

    @property
    def sent(self) -> list[Alert]:
        return list(self._sent)
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_alerting.py -v`
Expected: PASS (3/3)

**Step 5: Commit**

```bash
git add aos/alerting.py tests/test_alerting.py
git commit -m "feat: add structured alerting service with webhook support"
```

---

### Task 2.2: Wire alerting into evaluator

**Objective:** When evaluator finds a hard-fail violation, fire an alert.

**Files:**
- Modify: `aos/evaluator.py` (import alerting, fire on violation)
- Modify: `tests/test_evaluator.py` (add alert integration test)

**Step 1: Add alert integration**

In `aos/evaluator.py`, at the end of `validate_output`:

```python
from aos.alerting import AlertingService, Alert

_default_alerting: AlertingService | None = None

def get_alerting() -> AlertingService:
    global _default_alerting
    if _default_alerting is None:
        import os
        _default_alerting = AlertingService(webhook_url=os.environ.get("AOS_ALERT_WEBHOOK_URL"))
    return _default_alerting

def validate_output(output, agent_id, constants=None):
    result = ValidationResult()
    # ... existing checks ...
    if not result.passed:
        for violation in result.violations:
            get_alerting().send(Alert(
                level="critical",
                source="evaluator",
                message=violation,
                venture=agent_id.split("-")[1].lower() if "-" in agent_id else "unknown"
            ))
    return result
```

**Step 2: Write failing test**

```python
def test_evaluator_fires_alert_on_violation():
    from aos.evaluator import validate_output
    from aos.constants import NETSO_FINANCIAL
    result = validate_output({"dscr": 1.5}, "AGT-EXEC-CFO", NETSO_FINANCIAL)
    assert not result.passed
    # Check that alert was sent (via default service)
```

**Step 3: Run test**

Run: `pytest tests/test_evaluator.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add aos/evaluator.py tests/test_evaluator.py
git commit -m "feat: fire alert on evaluator hard-fail violation"
```

---

## Phase 3: Cost Tracking (P2 Gap)

### Task 3.1: Create cost tracker module

**Objective:** Track token usage per harness and convert to dollar estimates.

**Files:**
- Create: `aos/cost_tracker.py`
- Test: `tests/test_cost_tracker.py`

**Step 1: Write failing test**

```python
from aos.cost_tracker import CostTracker, CostRecord

def test_cost_tracker_records_usage():
    tracker = CostTracker()
    tracker.record(CostRecord(
        harness="executive",
        agent="AGT-EXEC-CFO",
        model="claude-3.5-sonnet",
        input_tokens=1000,
        output_tokens=500,
    ))
    assert tracker.total_cost() > 0

def test_cost_tracker_per_harness():
    tracker = CostTracker()
    tracker.record(CostRecord(harness="executive", agent="AGT-EXEC-CFO", model="claude-3.5-sonnet", input_tokens=1000, output_tokens=500))
    tracker.record(CostRecord(harness="finance", agent="AGT-FIN-UNIT", model="claude-3.5-sonnet", input_tokens=2000, output_tokens=1000))
    by_harness = tracker.cost_by_harness()
    assert "executive" in by_harness
    assert "finance" in by_harness
    assert by_harness["finance"] > by_harness["executive"]
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_cost_tracker.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# aos/cost_tracker.py
"""Per-harness cost tracking (tokens → dollar estimates)."""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import defaultdict

# Approximate costs per 1M tokens (USD)
MODEL_COSTS: dict[str, dict[str, float]] = {
    "claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "free": {"input": 0.0, "output": 0.0},
    "_default": {"input": 3.0, "output": 15.0},
}

@dataclass(frozen=True)
class CostRecord:
    harness: str
    agent: str
    model: str
    input_tokens: int
    output_tokens: int

class CostTracker:
    def __init__(self):
        self._records: list[CostRecord] = []

    def record(self, rec: CostRecord) -> None:
        self._records.append(rec)

    def total_cost(self) -> float:
        return sum(self._cost(r) for r in self._records)

    def cost_by_harness(self) -> dict[str, float]:
        costs: dict[str, float] = defaultdict(float)
        for r in self._records:
            costs[r.harness] += self._cost(r)
        return dict(costs)

    def _cost(self, rec: CostRecord) -> float:
        prices = MODEL_COSTS.get(rec.model, MODEL_COSTS["_default"])
        return (rec.input_tokens / 1_000_000 * prices["input"] +
                rec.output_tokens / 1_000_000 * prices["output"])
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_cost_tracker.py -v`
Expected: PASS (2/2)

**Step 5: Commit**

```bash
git add aos/cost_tracker.py tests/test_cost_tracker.py
git commit -m "feat: add per-harness cost tracker (tokens → dollars)"
```

---

## Phase 4: Knowledge Base Sync

### Task 4.1: Sync AOS status to tazwar-knowledge-base

**Objective:** Update the knowledge base with current AOS status from the audit.

**Files:**
- Modify: `~/tazwar-knowledge-base/global/projects.md` (update AOS section)
- Modify: `~/tazwar-knowledge-base/memory-bank/hermes-setup/` (add AOS deployment notes)

**Step 1: Read current projects.md**

Run: `cat ~/tazwar-knowledge-base/global/projects.md`

**Step 2: Update AOS section**

```markdown
## AOS (Agentic Operating System)
- **Status:** BETA — 8.5/10 production readiness
- **Location:** `~/Documents/10-Projects/Agentic Harness`
- **Repo:** git, 132 commits, 5 branches
- **What it is:** Governance-first multi-venture agentic OS
- **Built:** 13 harnesses, 52+ agents, 898 tests, 12,381 lines Python
- **Last audit:** 2026-07-29, full system audit completed
- **Remaining:** Hardening (pre-commit, alerting, cost tracking, env validation)
- **How to use:** `python -m aos run --venture netso --dry-run`
```

**Step 3: Commit and push**

```bash
cd ~/tazwar-knowledge-base && git add -A && git commit -m "docs: AOS audit status update (8.5/10, BETA)" && git push
```

---

## Phase 5: First Run Guide (Prove It Works)

### Task 5.1: Create FIRST_RUN.md

**Objective:** Step-by-step guide that proves the system works end-to-end.

**Files:**
- Create: `FIRST_RUN.md`

**Step 1: Write the guide**

```markdown
# AOS — First Run Guide

## Prerequisites
- Python 3.14+ (via uv)
- `.env` configured (copy from `.env.example`)

## Step 1: Setup

```bash
cd ~/Documents/10-Projects/Agentic\ Harness
uv venv --python 3.14
source .venv/bin/activate
uv pip install -e ".[dev]"
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
# Expected: Pipeline executes in dry-run mode, no LLM calls
```

## Step 5: Run Tests

```bash
pytest -q
# Expected: 898+ tests passing
```

## Step 6: Run Evaluator

```bash
python -m aos evaluator --golden-dir tests/golden
# Expected: All 9 golden tests pass
```

## Step 7: Start Dashboard

```bash
python -m aos api --port 8642
# Open http://localhost:8642/docs for API
# Open odysseus/dashboard/preview.html for UI
```

## Step 8: Check Approvals

```bash
python -m aos approvals list
# Expected: Empty queue (nothing pending)
```

## What Just Happened
You validated the full AOS stack: manifests → engine → evaluator → memory → dashboard.
```

**Step 2: Commit**

```bash
git add FIRST_RUN.md
git commit -m "docs: add FIRST_RUN.md — end-to-end setup guide"
```

---

## Phase 6: Wiki Reconciliation (Cross-Reference Audit)

### Task 6.1: Audit AOS constants against GROUND_TRUTH_CONSTANTS.md

**Objective:** Ensure `aos/constants.py` matches `~/Documents/10-Projects/Netso_HQ/GROUND_TRUTH_CONSTANTS.md`.

**Files:**
- Read: `aos/constants.py`
- Read: `~/Documents/10-Projects/Netso_HQ/GROUND_TRUTH_CONSTANTS.md`
- Test: `tests/test_constants_match.py`

**Step 1: Write failing test**

```python
# tests/test_constants_match.py
def test_constants_match_ground_truth():
    """Verify aos/constants.py matches GROUND_TRUTH_CONSTANTS.md."""
    from aos.constants import (
        CAPEX_PER_KW_SCENARIO_A,
        PPA_RATE,
        TRUE_VARIABLE_RATE,
        DSCR_ALERT_FLOOR,
        NEM_EXPORT_RATE,
        CUSTOMER_SAVINGS_PCT,
    )
    # Canonical values from GROUND_TRUTH_CONSTANTS.md
    assert CAPEX_PER_KW_SCENARIO_A == 55_000, f"CAPEX_A should be 55000, got {CAPEX_PER_KW_SCENARIO_A}"
    assert PPA_RATE == 10.0, f"PPA should be 10.0, got {PPA_RATE}"
    assert TRUE_VARIABLE_RATE == 12.98, f"TVR should be 12.98, got {TRUE_VARIABLE_RATE}"
    assert DSCR_ALERT_FLOOR == 2.0, f"DSCR floor should be 2.0, got {DSCR_ALERT_FLOOR}"
    assert NEM_EXPORT_RATE == 6.4523, f"NEM should be 6.4523, got {NEM_EXPORT_RATE}"
    assert CUSTOMER_SAVINGS_PCT == 23.0, f"Savings should be 23.0, got {CUSTOMER_SAVINGS_PCT}"
```

**Step 2: Run test**

Run: `pytest tests/test_constants_match.py -v`
Expected: PASS (if constants match) or FAIL (if drift detected — then fix constants.py)

**Step 3: Commit**

```bash
git add tests/test_constants_match.py
git commit -m "test: verify AOS constants match GROUND_TRUTH_CONSTANTS.md"
```

---

## Phase 7: Deployment Readiness

### Task 7.1: Verify deploy/ directory is complete

**Objective:** Ensure systemd units, nginx config, healthcheck, and backup scripts are production-ready.

**Files:**
- Read: `deploy/aos-engine.service`
- Read: `deploy/aos-dashboard.service`
- Read: `deploy/aos.nginx.conf`
- Read: `deploy/healthcheck.sh`
- Read: `deploy/backup.sh`
- Read: `deploy/RUNBOOK.md`

**Step 1: Verify each file exists and is non-empty**

```bash
ls -la deploy/
cat deploy/RUNBOOK.md | head -5
cat deploy/healthcheck.sh | head -5
cat deploy/backup.sh | head -5
```

**Step 2: If any are missing or empty, create them**

**Step 3: Commit if any changes made**

---

## Summary: All Phases

| Phase | Tasks | Effort | Impact |
|-------|-------|--------|--------|
| 0: Environment Fix | 3 tasks | 15 min | Unblocks hermes tool use |
| 1: Hardening | 2 tasks | 10 min | Prevents drift |
| 2: Monitoring & Alerting | 2 tasks | 15 min | Catches financial breaches |
| 3: Cost Tracking | 1 task | 10 min | Measures harness ROI |
| 4: KB Sync | 1 task | 5 min | Knowledge preserved |
| 5: First Run Guide | 1 task | 5 min | Proves system works |
| 6: Wiki Reconciliation | 1 task | 5 min | Constants verified |
| 7: Deployment | 1 task | 5 min | Production ready |
| **Total** | **12 tasks** | **~70 min** | **8.5/10 → 9.5/10** |

## Execution Strategy

Use **subagent-driven-development** for Phases 0-3 (code tasks with TDD).
Use **direct execution** for Phases 4-7 (docs, verification, sync).

Dispatch tasks in parallel where possible:
- Phase 0 tasks are sequential (each depends on prior)
- Phase 1 tasks can run in parallel with Phase 2
- Phase 3 can run in parallel with Phase 2
- Phases 4-7 are independent and can run in any order

## Verification After All Phases

```bash
# Full suite
pytest -q

# Evaluator golden tests
python -m aos evaluator --golden-dir tests/golden

# Validate all manifests
python -m aos validate

# Status check
python -m aos status

# Pre-commit (if installed)
pre-commit run --all-files
```

Expected: All green, no regressions, AOS at 9.5/10 production readiness.
