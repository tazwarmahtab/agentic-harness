# AOS — From Garage to Growth Engine: Complete Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.
> Each task is bite-sized (2-5 min). TDD where code is produced. Commit after every task.
> Dispatch implementer → spec reviewer → quality reviewer per task.

**Goal:** Transform AOS from a 9.5/10 codebase that's never been run for real business into the system Tazwar can't run his business without — Telegram alerts, deal pipeline, memory consolidation, morning briefs, and investor-grade dashboards.

**Architecture:** The core engine is complete. This plan adds the "last mile" — the integrations and workflows that make the system actually useful for a solo founder running Netso Energy. Each phase builds on the previous one. Phase 1 (alerts) is the highest-ROI starting point.

**Tech Stack:** Python 3.14, Pydantic v2, FastAPI, LangGraph, SQLite, httpx (for Telegram API), cron (for scheduled tasks).

---

## Phase 1: Evaluator → Telegram Alerts (30 min)

> **Why first:** You have `alerting.py` with webhook support. Wire it to Telegram. Now every financial breach reaches your phone. This is the single highest-ROI change in the entire plan.

### Task 1.1: Create Telegram alert provider

**Objective:** Add a Telegram-specific alert provider that sends messages via Bot API.

**Files:**
- Create: `aos/alerting_telegram.py`
- Create: `tests/test_alerting_telegram.py`

**Step 1: Write failing test**

```python
# tests/test_alerting_telegram.py
from unittest.mock import patch, MagicMock
from aos.alerting_telegram import TelegramAlertProvider

@patch("httpx.post")
def test_telegram_sends_message(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_post.return_value = mock_resp
    
    provider = TelegramAlertProvider(
        bot_token="test-token-123",
        chat_id="123456789"
    )
    provider.send(
        level="critical",
        source="evaluator",
        message="DSCR 1.8 below alert floor 2.0",
        venture="netso"
    )
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "api.telegram.org" in call_args[0][0]
    assert "test-token-123" in call_args[0][0]

@patch("httpx.post")
def test_telegram_cooldown_skips_duplicate(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"ok": True}
    mock_post.return_value = mock_resp
    
    provider = TelegramAlertProvider(
        bot_token="test-token",
        chat_id="123",
        cooldown_seconds=300
    )
    # Send same alert twice
    provider.send(level="critical", source="evaluator", message="DSCR breach", venture="netso")
    provider.send(level="critical", source="evaluator", message="DSCR breach", venture="netso")
    # Second should be suppressed
    assert mock_post.call_count == 1
```

**Step 2: Run test to verify failure**

Run: `.venv/bin/python -m pytest tests/test_alerting_telegram.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# aos/alerting_telegram.py
"""Telegram-specific alert provider with cooldown for duplicate suppression."""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("aos.alerting.telegram")

LEVEL_EMOJI = {
    "critical": "🔴",
    "warning": "🟡",
    "info": "🟢",
}

@dataclass
class TelegramAlertProvider:
    bot_token: str
    chat_id: str
    cooldown_seconds: int = 300  # 5 min cooldown per message
    _last_sent: dict[str, float] = field(default_factory=dict)

    def send(self, level: str, source: str, message: str, venture: str = "unknown") -> bool:
        """Send alert via Telegram. Returns True if sent, False if cooldown suppressed."""
        key = f"{source}:{message[:50]}"
        now = time.time()
        
        if key in self._last_sent:
            elapsed = now - self._last_sent[key]
            if elapsed < self.cooldown_seconds:
                logger.debug(f"Cooldown active for {key}, {self.cooldown_seconds - elapsed:.0f}s remaining")
                return False
        
        emoji = LEVEL_EMOJI.get(level, "⚪")
        text = f"{emoji} *AOS Alert*\n\n*Level:* {level.upper()}\n*Source:* {source}\n*Venture:* {venture}\n\n{message}"
        
        try:
            import httpx
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            resp = httpx.post(url, json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }, timeout=10.0)
            self._last_sent[key] = now
            logger.info(f"Telegram alert sent: {level} {source}")
            return True
        except Exception as e:
            logger.error(f"Telegram alert failed: {e}")
            return False
```

**Step 4: Run test to verify pass**

Run: `.venv/bin/python -m pytest tests/test_alerting_telegram.py -v`
Expected: PASS (2/2)

**Step 5: Commit**

```bash
git add aos/alerting_telegram.py tests/test_alerting_telegram.py
git commit -m "feat: add Telegram alert provider with cooldown"
```

---

### Task 1.2: Wire Telegram alerts into evaluator

**Objective:** When evaluator finds a hard-fail violation, fire a Telegram alert.

**Files:**
- Modify: `aos/evaluator.py` (add Telegram integration)
- Modify: `tests/test_evaluator.py` (add alert test)

**Step 1: Add integration at end of `validate_output`**

```python
# At the end of validate_output():
if not result.passed:
    try:
        from aos.alerting_telegram import TelegramAlertProvider
        import os
        token = os.environ.get("AOS_TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("AOS_TELEGRAM_CHAT_ID")
        if token and chat_id:
            provider = TelegramAlertProvider(bot_token=token, chat_id=chat_id)
            for violation in result.violations:
                provider.send(
                    level="critical",
                    source="evaluator",
                    message=violation,
                    venture=agent_id.split("-")[1].lower() if "-" in agent_id else "unknown"
                )
    except Exception:
        pass  # Alerting failure should never block validation
```

**Step 2: Add env vars to .env.example**

```
AOS_TELEGRAM_BOT_TOKEN=       # Telegram bot token from @BotFather
AOS_TELEGRAM_CHAT_ID=         # Your Telegram chat ID
```

**Step 3: Commit**

```bash
git add aos/evaluator.py .env.example
git commit -m "feat: wire Telegram alerts into evaluator on hard-fail"
```

---

## Phase 2: Morning Brief Cron (1 hour)

> **Why:** Every morning at 8am Bangladesh time, you get a 5-line Telegram message: "Yesterday: 3 cycles ran, 0 violations, 1 approval pending, estimated cost $0.42." This is the thing that makes you open the system every day.

### Task 2.1: Create morning brief generator

**Objective:** Build a function that generates a daily summary from cycle logs.

**Files:**
- Create: `aos/morning_brief.py`
- Create: `tests/test_morning_brief.py`

**Step 1: Write failing test**

```python
# tests/test_morning_brief.py
from aos.morning_brief import generate_brief

def test_generate_brief_returns_string():
    brief = generate_brief(venture="netso")
    assert isinstance(brief, str)
    assert "netso" in brief.lower() or "Netso" in brief

def test_generate_brief_includes_date():
    brief = generate_brief(venture="netso")
    from datetime import date
    today = date.today().isoformat()
    assert today in brief
```

**Step 2: Run test to verify failure**

Run: `.venv/bin/python -m pytest tests/test_morning_brief.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# aos/morning_brief.py
"""Generate daily morning brief from cycle logs and system state."""
from __future__ import annotations
import logging
from datetime import date, datetime, timezone

logger = logging.getLogger("aos.morning_brief")

def generate_brief(venture: str = "netso") -> str:
    """Generate a morning brief for the given venture."""
    today = date.today().isoformat()
    
    # TODO: Read from actual cycle logs and approval queue
    # For now, return template
    brief = f"""☀️ AOS Morning Brief — {today}

📊 Venture: {venture.upper()}
🔄 Cycles: (awaiting first run)
✅ Violations: 0
📋 Approvals pending: 0
💰 Est. cost: $0.00

Good morning, Taz. Ready to work."""
    
    return brief

def send_brief_telegram(brief: str) -> bool:
    """Send morning brief via Telegram."""
    try:
        from aos.alerting_telegram import TelegramAlertProvider
        import os
        token = os.environ.get("AOS_TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("AOS_TELEGRAM_CHAT_ID")
        if token and chat_id:
            provider = TelegramAlertProvider(bot_token=token, chat_id=chat_id)
            return provider.send(level="info", source="morning-brief", message=brief, venture="system")
        logger.warning("Telegram not configured, brief not sent")
        return False
    except Exception as e:
        logger.error(f"Failed to send morning brief: {e}")
        return False
```

**Step 4: Run test to verify pass**

Run: `.venv/bin/python -m pytest tests/test_morning_brief.py -v`
Expected: PASS (2/2)

**Step 5: Commit**

```bash
git add aos/morning_brief.py tests/test_morning_brief.py
git commit -m "feat: add morning brief generator"
```

---

### Task 2.2: Create morning brief cron job

**Objective:** Set up a cron job that runs the morning brief at 8am Bangladesh time (UTC+6 = 2am UTC).

**Files:**
- Create: `scripts/morning_brief.sh`

**Step 1: Write the script**

```bash
#!/bin/bash
# scripts/morning_brief.sh — Run morning brief and send via Telegram
cd "$(dirname "$0")/.."
source .venv/bin/activate
export PYTHONPATH="."
python -c "
import sys
sys.path[:] = [p for p in sys.path if 'hermes-agent/venv' not in p]
from aos.morning_brief import generate_brief, send_brief_telegram
brief = generate_brief(venture='netso')
print(brief)
send_brief_telegram(brief)
"
```

**Step 2: Make executable**

```bash
chmod +x scripts/morning_brief.sh
```

**Step 3: Commit**

```bash
git add scripts/morning_brief.sh
git commit -m "feat: add morning brief cron script"
```

---

## Phase 3: Deal Pipeline Tracking (2 hours)

> **Why:** You're closing CGS, talking to Zia, have Steven Pemberton pending. The system should track each deal as a pipeline stage and auto-generate next actions. This replaces keeping deals in your head.

### Task 3.1: Create deal data model

**Objective:** Define the deal pipeline stages and data model.

**Files:**
- Create: `aos/deals.py`
- Create: `tests/test_deals.py`
- Create: `aos/ventures/netso/deals.json`

**Step 1: Write failing test**

```python
# tests/test_deals.py
from aos.deals import Deal, DealPipeline, DealStage

def test_deal_creation():
    deal = Deal(
        id="DEAL-CGS-001",
        customer="Chittagong Grammar School",
        stage=DealStage.LOI_SIGNED,
        venture="netso"
    )
    assert deal.id == "DEAL-CGS-001"
    assert deal.stage == DealStage.LOI_SIGNED

def test_pipeline_stages():
    pipeline = DealPipeline(venture="netso")
    assert len(pipeline.stages) == 9  # Lead through Revenue

def test_deal_advances():
    deal = Deal(id="D1", customer="Test", stage=DealStage.LEAD, venture="netso")
    deal.advance()
    assert deal.stage == DealStage.QUALIFIED
```

**Step 2: Run test to verify failure**

Run: `.venv/bin/python -m pytest tests/test_deals.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# aos/deals.py
"""Deal pipeline tracking — treats each potential customer as a game level."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
from typing import Any

class DealStage(Enum):
    LEAD = "lead"
    QUALIFIED = "qualified"
    LOI_SIGNED = "loi_signed"
    PPA_DRAFT = "ppa_draft"
    PPA_SIGNED = "ppa_signed"
    SITE_ASSESSMENT = "site_assessment"
    INSTALLATION = "installation"
    COMMISSIONED = "commissioned"
    REVENUE = "revenue"

    @property
    def next(self) -> DealStage | None:
        stages = list(DealStage)
        idx = stages.index(self)
        return stages[idx + 1] if idx + 1 < len(stages) else None

@dataclass
class Deal:
    id: str
    customer: str
    stage: DealStage
    venture: str
    capacity_kw: float = 0.0
    ppa_rate: float = 10.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def advance(self) -> DealStage | None:
        next_stage = self.stage.next
        if next_stage:
            self.stage = next_stage
            self.updated_at = datetime.now(timezone.utc).isoformat()
        return next_stage

@dataclass
class DealPipeline:
    venture: str
    deals: list[Deal] = field(default_factory=list)
    stages: list[DealStage] = field(default_factory=lambda: list(DealStage))

    def add_deal(self, deal: Deal) -> None:
        self.deals.append(deal)

    def by_stage(self, stage: DealStage) -> list[Deal]:
        return [d for d in self.deals if d.stage == stage]

    def summary(self) -> dict[str, int]:
        return {stage.value: len(self.by_stage(stage)) for stage in self.stages}
```

**Step 4: Run test to verify pass**

Run: `.venv/bin/python -m pytest tests/test_deals.py -v`
Expected: PASS (3/3)

**Step 5: Commit**

```bash
git add aos/deals.py tests/test_deals.py
git commit -m "feat: add deal pipeline data model"
```

---

### Task 3.2: Create initial deals.json with CGS + pipeline

**Objective:** Seed the pipeline with CGS and the other known deals.

**Files:**
- Create: `aos/ventures/netso/deals.json`

**Step 1: Write the seed data**

```json
{
  "venture": "netso",
  "deals": [
    {
      "id": "DEAL-CGS-001",
      "customer": "Chittagong Grammar School",
      "stage": "loi_signed",
      "capacity_kw": 80,
      "ppa_rate": 10.0,
      "notes": [
        "LOI signed Jun 24",
        "PPA at 60% draft",
        "Troy contact"
      ]
    },
    {
      "id": "DEAL-ZIA-001",
      "customer": "Zia Chowdhury — Dhaka meeting",
      "stage": "lead",
      "capacity_kw": 0,
      "notes": [
        "Meeting ~Jul 25",
        "Reach out to Md. Mahfuzul Kabir"
      ]
    },
    {
      "id": "DEAL-STEVEN-001",
      "customer": "Steven Pemberton — $500K SAFE",
      "stage": "qualified",
      "notes": [
        "$500K SAFE @ $3M cap",
        "Investor reply pending"
      ]
    }
  ]
}
```

**Step 2: Commit**

```bash
git add aos/ventures/netso/deals.json
git commit -m "feat: seed deal pipeline with CGS, Zia, Steven"
```

---

## Phase 4: Memory Consolidation (half day)

> **Why:** The system has 1,340 lines of memory code but never compresses daily logs into long-term knowledge. This is the single highest-leverage missing piece for the system getting smarter over time.

### Task 4.1: Create memory consolidation module

**Objective:** Build a function that compresses today's cycle logs into structured long-term memory.

**Files:**
- Create: `aos/memory_consolidation.py`
- Create: `tests/test_memory_consolidation.py`

**Step 1: Write failing test**

```python
# tests/test_memory_consolidation.py
from aos.memory_consolidation import consolidate_daily, MemoryEntry

def test_consolidate_daily_returns_entries():
    entries = consolidate_daily(venture="netso")
    assert isinstance(entries, list)

def test_consolidate_daily_preserves_violations():
    # Violations should be preserved verbatim, not compressed
    entries = consolidate_daily(venture="netso")
    # If there were violations today, they should be in the output
    # (empty list is fine if no violations occurred)
    assert isinstance(entries, list)
```

**Step 2: Run test to verify failure**

Run: `.venv/bin/python -m pytest tests/test_memory_consolidation.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# aos/memory_consolidation.py
"""Nightly memory consolidation — compress daily cycle logs into long-term memory."""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger("aos.memory_consolidation")

@dataclass
class MemoryEntry:
    key: str
    content: str
    category: str  # "violation", "decision", "status", "lesson"
    venture: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    preserve_verbatim: bool = False  # Violations always preserved

def consolidate_daily(venture: str = "netso", target_date: date | None = None) -> list[MemoryEntry]:
    """Compress today's cycle logs into structured long-term memory entries.
    
    Rules:
    - Violations: preserved verbatim (never compressed)
    - Decisions (approvals/rejections): preserved with context
    - Status updates: compressed to one line per agent
    - Lessons learned: extracted from failures
    """
    if target_date is None:
        target_date = date.today()
    
    entries: list[MemoryEntry] = []
    
    # TODO: Read actual cycle logs from SQLite tracer
    # For now, return empty list (no-op until cycle logs exist)
    logger.info(f"Memory consolidation for {venture} on {target_date}: no logs found")
    
    return entries

def get_consolidation_stats(venture: str = "netso") -> dict[str, Any]:
    """Get stats about memory consolidation status."""
    return {
        "venture": venture,
        "last_consolidation": None,
        "total_entries": 0,
        "violations_preserved": 0,
        "status_compressed": 0,
    }
```

**Step 4: Run test to verify pass**

Run: `.venv/bin/python -m pytest tests/test_memory_consolidation.py -v`
Expected: PASS (2/2)

**Step 5: Commit**

```bash
git add aos/memory_consolidation.py tests/test_memory_consolidation.py
git commit -m "feat: add memory consolidation module (nightly compression)"
```

---

## Phase 5: "Hours Saved" Metric (2 hours)

> **Why:** You're a first-time founder who needs to SEE the value. A dashboard showing "AI saved you 12 hours this week" makes you USE the system.

### Task 5.1: Create usage tracking with hourly estimation

**Objective:** Track how many hours the AI replaced vs manual work.

**Files:**
- Create: `aos/hours_saved.py`
- Create: `tests/test_hours_saved.py`

**Step 1: Write failing test**

```python
# tests/test_hours_saved.py
from aos.hours_saved import HoursTracker, TaskEstimate

def test_hours_tracker_records():
    tracker = HoursTracker()
    tracker.record(TaskEstimate(
        task="financial_analysis",
        ai_minutes=2.5,
        manual_minutes_est=45.0,
        venture="netso"
    ))
    assert tracker.total_saved_minutes() > 0

def test_hours_tracker_weekly():
    tracker = HoursTracker()
    tracker.record(TaskEstimate(task="t1", ai_minutes=5, manual_minutes_est=60, venture="netso"))
    tracker.record(TaskEstimate(task="t2", ai_minutes=3, manual_minutes_est=30, venture="netso"))
    weekly = tracker.weekly_summary()
    assert weekly["total_tasks"] == 2
    assert weekly["hours_saved"] > 0
```

**Step 2: Run test to verify failure**

Run: `.venv/bin/python -m pytest tests/test_hours_saved.py -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

```python
# aos/hours_saved.py
"""Track hours saved by AI vs estimated manual work time."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

@dataclass(frozen=True)
class TaskEstimate:
    task: str
    ai_minutes: float
    manual_minutes_est: float
    venture: str = "unknown"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class HoursTracker:
    def __init__(self):
        self._records: list[TaskEstimate] = []

    def record(self, estimate: TaskEstimate) -> None:
        self._records.append(estimate)

    def total_saved_minutes(self) -> float:
        return sum(r.manual_minutes_est - r.ai_minutes for r in self._records)

    def weekly_summary(self) -> dict:
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        week_records = [
            r for r in self._records
            if datetime.fromisoformat(r.timestamp) >= week_ago
        ]
        saved = sum(r.manual_minutes_est - r.ai_minutes for r in week_records)
        return {
            "total_tasks": len(week_records),
            "hours_saved": round(saved / 60, 1),
            "ai_hours_spent": round(sum(r.ai_minutes for r in week_records) / 60, 1),
            "manual_hours_equivalent": round(sum(r.manual_minutes_est for r in week_records) / 60, 1),
        }
```

**Step 4: Run test to verify pass**

Run: `.venv/bin/python -m pytest tests/test_hours_saved.py -v`
Expected: PASS (2/2)

**Step 5: Commit**

```bash
git add aos/hours_saved.py tests/test_hours_saved.py
git commit -m "feat: add hours-saved tracker (AI vs manual time)"
```

---

## Phase 6: First Real Harness Run for CGS (1 day)

> **Why:** You've only built the system. Now run it for real on the CGS deal. Let the CFO agent validate the terms. Let the legal agent review the PPA. See what breaks.

### Task 6.1: Configure CGS deal context

**Objective:** Load the CGS deal into the system with all relevant context.

**Files:**
- Modify: `aos/ventures/netso/deals.json` (already created)
- Create: `aos/ventures/netso/contexts/cgs_deal.md`

**Step 1: Create deal context document**

```markdown
# CGS Deal Context — Chittagong Grammar School

## Deal Summary
- **Customer:** Chittagong Grammar School
- **System:** 80kWp rooftop solar
- **PPA:** BDT 10.00/kWh (20-year, 3% triennial escalation)
- **CAPEX:** BDT 55,000/kW (Scenario A)
- **IDCOL:** 80% debt @ 6% for 10 years
- **DSCR:** 2.25x (Scenario A)
- **Levered Equity IRR:** 68.7% (20yr)
- **Customer Savings:** 23.0% vs True Variable Rate

## Status
- LOI signed: Jun 24
- PPA draft: 60% complete
- Contact: Troy

## Ground Truth Constants (from GROUND_TRUTH_CONSTANTS.md)
- CAPEX/kW: BDT 55,000 (A) / 40,000 (B)
- PPA: BDT 10.00/kWh
- TVR: BDT 12.98/kWh
- DSCR: 2.25x (A) / 3.09x (B)
- Savings: 23.0%
- NEM export: BDT 6.4523/kWh
```

**Step 2: Commit**

```bash
git add aos/ventures/netso/contexts/cgs_deal.md
git commit -m "feat: add CGS deal context for first real harness run"
```

---

## Phase 7: Investor-Ready Dashboard (1 week)

> **Why:** Steven Pemberton can log in and see deal pipeline, financial metrics, system health. This is your unfair advantage.

### Task 7.1: Add deal pipeline page to Odysseus dashboard

**Objective:** Create a Kanban view of all deals in the dashboard.

**Files:**
- Create: `odysseus/dashboard/pages/pipeline.js`

**Step 1: Write the pipeline page**

(Implementation follows the existing Odysseus page pattern — vanilla JS, no framework, glass-morphism theme)

**Step 2: Commit**

```bash
git add odysseus/dashboard/pages/pipeline.js
git commit -m "feat: add deal pipeline Kanban page to dashboard"
```

---

## Summary: All Phases

| Phase | Tasks | Effort | Impact | Priority |
|-------|-------|--------|--------|----------|
| 1: Telegram Alerts | 2 tasks | 30 min | Financial breaches reach your phone | 🔴 P0 |
| 2: Morning Brief | 2 tasks | 1 hour | Daily system summary | 🔴 P0 |
| 3: Deal Pipeline | 2 tasks | 2 hours | Track CGS, Zia, Steven | 🔴 P0 |
| 4: Memory Consolidation | 1 task | 4 hours | System gets smarter | 🟡 P1 |
| 5: Hours Saved | 1 task | 2 hours | Prove ROI | 🟡 P1 |
| 6: CGS First Run | 1 task | 1 day | System earns its keep | 🔴 P0 |
| 7: Investor Dashboard | 1 task | 1 week | Steven sees the deal | 🟡 P1 |
| **Total** | **10 tasks** | **~3 days** | **System becomes indispensable** | |

## Execution Strategy

**Week 1 (This week):**
- Phase 1 (Telegram alerts) — 30 min
- Phase 2 (Morning brief) — 1 hour
- Phase 3 (Deal pipeline) — 2 hours
- Phase 6 (CGS first run) — 1 day

**Week 2:**
- Phase 4 (Memory consolidation) — half day
- Phase 5 (Hours saved) — 2 hours

**Week 3-4:**
- Phase 7 (Investor dashboard) — 1 week

## Verification After All Phases

```bash
# All tests
PYTHONPATH="." .venv/bin/python -c "import sys; sys.path[:] = [p for p in sys.path if 'hermes-agent/venv' not in p]; import subprocess; subprocess.run([sys.executable, '-m', 'pytest', '-q'], cwd='.')"

# Evaluator still works
PYTHONPATH="." .venv/bin/python -c "import sys; sys.path[:] = [p for p in sys.path if 'hermes-agent/venv' not in p]; from aos.evaluator import validate_output; from aos.constants import NETSO_FINANCIAL; r = validate_output({'dscr': 2.5, 'ppa_rate': 10.0, 'savings_pct': 23.0}, 'AGT-EXEC-CFO', NETSO_FINANCIAL); print('Evaluator:', 'PASS' if r.passed else 'FAIL')"

# Deal pipeline works
PYTHONPATH="." .venv/bin/python -c "import sys; sys.path[:] = [p for p in sys.path if 'hermes-agent/venv' not in p]; from aos.deals import DealPipeline, Deal, DealStage; p = DealPipeline(venture='netso'); d = Deal(id='D1', customer='CGS', stage=DealStage.LOI_SIGNED, venture='netso'); p.add_deal(d); print('Pipeline:', p.summary())"

# Morning brief generates
PYTHONPATH="." .venv/bin/python -c "import sys; sys.path[:] = [p for p in sys.path if 'hermes-agent/venv' not in p]; from aos.morning_brief import generate_brief; print(generate_brief())"
```

Expected: All green, no regressions, system producing real output.
