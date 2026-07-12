# AOS - Current System Mapping & Transformation Plan

**Date:** 2026-07-10  
**Current System:** TAZ OS (Agentic Harness)  
**Target System:** AOS (Agent Operating System)  
**Base:** Odysseus UI Framework

---

## PART 1: CURRENT SYSTEM INVENTORY

### Core Infrastructure (Production Ready ✅)
```
aos/
├── Platform Layer
│   ├── api.py                    FastAPI + WebSocket server
│   ├── graph.py                  LangGraph state machine orchestrator
│   ├── memory.py                 3-layer memory (long-term/episodic/semantic)
│   ├── tools.py                  Capability-based tool gateway
│   ├── llm.py                    Multi-provider LLM routing
│   ├── registry.py               Manifest loader & cross-reference resolver
│   ├── evaluator.py              Output validation (financial ground truth)
│   ├── approval_queue.py         Bundled decision queue
│   └── hardening.py              Rate limiting, health checks, validation
│
├── Harnesses (12 total)
│   ├── executive/                Reference implementation (HAR-EXEC-001)
│   ├── finance/                  Cash flow, forecasting
│   ├── sales/                    Pipeline, proposals
│   ├── operations/               Procurement, execution
│   ├── legal/                    Contracts, compliance
│   ├── marketing/                Content, social media
│   ├── customer_success/         Support, retention
│   ├── ai_development/           AI workflows, evaluation
│   ├── software_dev/             Code generation, review
│   ├── investor_relations/       Fundraising, updates
│   ├── personal/                 Calendar, tasks
│   └── evaluator/                Baseline evaluation harness
│
├── Ventures
│   ├── netso/                    Netso Energy (production)
│   └── transitbd/                TransitBD (planning)
│
└── Tests
    └── 637 tests (100% passing)

```

### Quality Metrics
- Score: 9.5/10
- Tests: 637 passing
- Documentation: Complete (.env.example, schemas, rate limiting)
- Status: PRODUCTION READY

---

## PART 2: TRANSFORMATION REQUIREMENTS

### Rename: TAZ OS → AOS
```
FIND:                           REPLACE WITH:
- "TAZ OS"                   →  "AOS"
- "tazos"                    →  "aos"
- "TAZOS_"                   →  "AOS_"
- "Agentic Harness"          →  "Agent Operating System"
- Project folder name        →  Keep or rename?
```

### UI Layer: Odysseus Integration
```
Current: CLI + FastAPI + WebSocket
Target:  Odysseus glass morphism UI + existing backend

Components Needed:
1. Frontend Dashboard (React/Vue?)
2. Real-time harness status view
3. Approval queue interface
4. KPI metrics display
5. Agent deck (harness gallery)
6. Settings/configuration panel
```

### Agent Deck Concept
```
┌─────────────────────────────────────────────────────┐
│                   AOS Dashboard                      │
├─────────────────────────────────────────────────────┤
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  │
│  │  EXEC  │  │  FIN   │  │  SALES │  │  OPS   │  │
│  │ Active │  │  Idle  │  │Running │  │  Idle  │  │
│  │  ✅    │  │   ⏸️   │  │  ⚡    │  │   ⏸️   │  │
│  └────────┘  └────────┘  └────────┘  └────────┘  │
│                                                     │
│  📊 KPIs          📅 Schedule       🔔 Alerts      │
│  💰 Cash: $XXX    📌 3 meetings     ⚠️ 2 pending   │
│  📈 Revenue: XX%  ⏰ Next: 2pm      ✅ 0 blockers  │
└─────────────────────────────────────────────────────┘
```

---

## PART 3: TRANSFORMATION PHASES

### Phase 1: Core Renaming (LOW RISK)
**Effort:** 2-4 hours  
**Impact:** Branding only, no functionality changes

Tasks:
- [ ] Rename package: tazos → aos
- [ ] Update all import statements
- [ ] Update environment variables (TAZOS_ → AOS_)
- [ ] Update documentation
- [ ] Update README.md
- [ ] Update pyproject.toml
- [ ] Run all tests (should still pass)

### Phase 2: Odysseus UI Integration (MEDIUM RISK)
**Effort:** 8-16 hours  
**Impact:** New frontend, existing backend preserved

Tasks:
- [ ] Locate Odysseus project
- [ ] Extract glass morphism components
- [ ] Create AOS dashboard layout
- [ ] Connect to existing FastAPI backend (/health, /api/*, /ws/*)
- [ ] Real-time WebSocket updates
- [ ] Approval queue UI
- [ ] Harness status cards

### Phase 3: Agent Deck Implementation (MEDIUM RISK)
**Effort:** 4-8 hours  
**Impact:** New visualization layer

Tasks:
- [ ] Design harness card component
- [ ] Live status indicators (running/idle/error)
- [ ] Quick actions (start/stop/configure)
- [ ] Performance metrics per harness
- [ ] Drill-down into specialist agents
- [ ] Recent outputs display

### Phase 4: Enhanced Integrations (HIGH VALUE)
**Effort:** Variable (per integration)  
**Impact:** Expanded capabilities

Tasks:
- [ ] Email integration (Gmail API)
- [ ] Calendar sync (Google Calendar)
- [ ] CRM connector
- [ ] Slack/Discord notifications
- [ ] WhatsApp Business API
- [ ] GitHub webhooks
- [ ] Financial tools

---

## PART 4: RISK ASSESSMENT

### LOW RISK (Safe to proceed immediately)
- Renaming (tazos → aos)
- Documentation updates
- Branding changes
- Environment variable prefixes

### MEDIUM RISK (Test thoroughly)
- UI integration (new frontend layer)
- WebSocket connection handling
- Real-time updates
- Agent deck visualization

### HIGH RISK (Requires planning)
- Multi-venture UI routing
- Cross-harness dispatch UI
- External API integrations
- Authentication/authorization

---

## PART 5: CHUNKED EXECUTION PLAN

Given chunked write protocol (max 350 lines), we'll execute in surgical phases:

### Phase 1A: Package Rename (Chunk 1)
- Files 1-10: Core module imports

### Phase 1B: Package Rename (Chunk 2)
- Files 11-20: Test file imports

### Phase 1C: Package Rename (Chunk 3)
- Files 21-30: Documentation

### Phase 2A: UI Foundation
- Create dashboard skeleton (≤300 lines)

### Phase 2B: UI Components
- Harness cards (≤300 lines)

### Phase 2C: UI Integration
- WebSocket connector (≤300 lines)

(And so on...)

---

## NEXT STEPS

**IMMEDIATE ACTIONS:**
1. Answer discovery questions in AOS_DISCOVERY.md
2. Confirm transformation phases priority
3. Locate Odysseus project path
4. Choose Phase 1 start date

**DECISION NEEDED:**
- Keep "Agentic Harness" folder name or rename?
- Odysseus location?
- Which integrations are P0 for v1?

