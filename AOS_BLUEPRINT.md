# AOS — Agent Operating System
## Comprehensive Architecture Blueprint
**Owner:** Tazwar Mahtab (Taz)  
**Date:** 2026-07-11  
**Status:** v1.0 — Active Development

---

## VISION

AOS is the execution platform for Netso Energy, designed to scale into a
multi-company operating system: Netso Energy → TransitBD → Investment Office
→ future ventures. One founder operating multiple companies through
autonomous, policy-driven harnesses with shared memory, event-driven
workflows, and enterprise governance.

**Founding constraint:** The UI sits on top of a functioning platform.
Architecture drives design, not the other way around.

---

## CORE PRINCIPLES (Architecture Rules)

1. **Everything is event-driven.** No direct harness-to-harness calls.
2. **Everything is an entity.** Customer, Project, Proposal, Meeting,
   Memory, Workflow, Harness, Agent — every concept has an identity.
3. **Agents never own orchestration.** Runtime owns orchestration.
   Harness owns business logic. Agent executes work.
4. **Memory is centralized.** No harness-specific databases. One global
   memory. One knowledge graph.
5. **Every external system through Tool Gateway.** Never call APIs directly.
6. **Everything produces artifacts.** Nothing exists only inside chat.
7. **Human approval gates are mandatory** for: payments, contracts,
   investor communications, legal submissions.

---

## 7-PHASE BUILD ORDER

```
Phase 1  ✅ COMPLETE — Core Rename (tazos → aos)
Phase 2  ✅ COMPLETE — Runtime + Harness Registry
Phase 3  ✅ COMPLETE — Memory + Knowledge Graph
Phase 4  ✅ COMPLETE — Workflow Engine
Phase 5  ✅ COMPLETE — Executive Harness (first working harness)
Phase 6  ✅ COMPLETE — Executive Dashboard (AOS UI)
Phase 7  🔄 NOW      — Sales Harness
```

Validate the architecture against a real business workflow (Phase 5)
before building the dashboard (Phase 6). No visualization for
components that may still evolve.

---

## PLATFORM LAYERS (P0 — v1.0)

```
┌─────────────────────────────────────────────────────────────┐
│                        FOUNDER (Taz)                        │
├─────────────────────────────────────────────────────────────┤
│                   Odysseus UI / Agent Deck                  │
│         Executive Dashboard · Approval Queue · KPIs        │
├─────────────────────────────────────────────────────────────┤
│                      Executive Harness                      │
│      Planner · Dispatcher · 6 Specialists · SOPs            │
├─────────────────────────────────────────────────────────────┤
│                      PLATFORM LAYER                         │
│  Runtime · Event Bus · Harness Registry · Workflow Engine   │
│  Policy Engine · Approval Engine · Context Builder          │
├─────────────────────────────────────────────────────────────┤
│                    FOUNDATION LAYER                         │
│  Global Memory · Knowledge Graph · Tool Gateway             │
│  LLM Router · Evaluator · Hardening                         │
├─────────────────────────────────────────────────────────────┤
│                     VENTURE LAYER                           │
│  Netso Energy (VEN-NETSO-001) · TransitBD (future)          │
└─────────────────────────────────────────────────────────────┘
```

---

## P0 COMPONENTS (v1.0 Required)

| Component | Location | Status |
|-----------|----------|--------|
| Executive Harness | `aos/harnesses/executive/` | ✅ Manifests done |
| Runtime (LangGraph) | `aos/graph.py` | ✅ Done |
| Event Bus | `aos/graph.py` (state machine) | ✅ Done |
| Harness Registry | `aos/registry.py` | ✅ Done |
| Global Memory (3-layer) | `aos/memory.py` | ✅ Done |
| Tool Gateway | `aos/tools.py` | ✅ Done |
| Policy Engine | `aos/harnesses/*/approvals.yml` | ✅ Manifests done |
| Approval Engine | `aos/approval_queue.py` | ✅ Done |
| Context Builder | `aos/context.py` | ✅ Done |
| Workflow Engine | `aos/graph.py` (StateGraph) | ✅ Done |
| Executive Dashboard | Odysseus UI (Phase 6) | ⏳ Pending |

---

## ENTITY MODEL (Everything is an entity)

Every entity has: `id`, `venture_id`, `created_at`, `created_by`,
`status`, `version`, and lives in Global Memory or Knowledge Graph.

### Core Entities

**Business**
- `Venture` — A company (Netso, TransitBD)
- `Customer` — A client or prospect
- `Project` — A revenue-generating engagement
- `Proposal` — A sales artifact for a Project
- `Contract` — A legal binding document
- `Invoice` — A financial artifact

**Operational**
- `Meeting` — A scheduled interaction
- `Decision` — A logged founder decision with rationale
- `Blocker` — An impediment with a named holder
- `Task` — A unit of work with priority, deadline, assignee
- `Handoff` — A cross-harness work item

**System**
- `Harness` — A business domain orchestrator
- `Agent` — A specialist worker within a harness
- `Memory` — An immutable knowledge entry
- `Workflow` — A state machine execution instance
- `Approval` — A gated action awaiting founder decision
- `Artifact` — Any produced document/report/output
- `Alert` — A risk-triggered escalation

---

## HARNESS CATALOGUE

### P0 — v1.0
```
Executive (HAR-EXEC-001)    Reference implementation — live
  Specialists: CEO, COO, CFO, Legal, Risk, Performance, COS
```

### P1 — v1.1
```
Sales (HAR-SAL-001)         Pipeline, proposals, CRM
Finance (HAR-FIN-001)       Cash flow, forecasting, reporting
Engineering (HAR-ENG-001)   Software dev, AI dev, code review
Legal (HAR-LEG-001)         Contracts, compliance, regulatory
Research (HAR-RES-001)      Market research, competitor intel
```

### P2 — v1.2+
```
Marketing (HAR-MKT-001)     Content, social, brand
Customer Success (HAR-CS-001) Retention, support, NPS
Personal OS (HAR-PRS-001)   Calendar, health, personal tasks
```

### Multi-venture (v2.0)
```
TransitBD instance          Separate venture mount
Investment Office           Portfolio management
```

---

## AGENT DECK — UI ARCHITECTURE

The Agent Deck is Taz's command center. Built on Odysseus glass morphism.

```
┌─────────────────────────────────────────────────────────────┐
│ AOS                               [🔔 3] [⚙️] [Taz ▾]      │
├──────────┬──────────────────────────────────────────────────┤
│          │  EXECUTIVE DASHBOARD                              │
│ HARNESSES│  ─────────────────────────────────────────────   │
│          │  📊 KPIs  |  📅 Today  |  🔔 Approvals  |  📝    │
│ ▶ EXEC   │                                                   │
│   FIN    │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐  │
│   SALES  │  │  EXEC   │ │   FIN   │ │  SALES  │ │  OPS  │  │
│   OPS    │  │ ● LIVE  │ │ ○ IDLE  │ │ ● LIVE  │ │ ○IDLE │  │
│   LEGAL  │  │ 3 tasks │ │ 1 task  │ │ 5 tasks │ │      │  │
│   MKT    │  └─────────┘ └─────────┘ └─────────┘ └───────┘  │
│   CS     │                                                   │
│   ENG    │  ⚠️  PENDING APPROVALS (2)                        │
│          │  ┌────────────────────────────────────────────┐  │
│ MEMORY   │  │ [APPROVE] Send LOI to Lhoist — CFO req.    │  │
│ GRAPH    │  │ [APPROVE] Wire BDT 45,000 — COO req.       │  │
│ APPROVALS│  └────────────────────────────────────────────┘  │
│ SETTINGS │                                                   │
└──────────┴──────────────────────────────────────────────────┘
```

### Agent Deck Panels
1. **Harness Gallery** — Status cards per harness (live/idle/error)
2. **KPI Panel** — Revenue, cash, pipeline, DSCR, risk score
3. **Approval Queue** — Bundled decisions (never single pings)
4. **Memory Explorer** — Search global memory across layers
5. **Knowledge Graph** — Visual entity relationship browser
6. **Workflow Viewer** — Running workflow state visualization
7. **Activity Feed** — Real-time agent actions + artifacts

---

## MEMORY ARCHITECTURE

```
Global Memory (SQLite + Vector)
├── Long-Term Layer
│   ├── company_facts      (financial constants, legal structure)
│   ├── venture_artifacts  (files, paths, configuration)
│   └── pricing_models     (unit economics, rate calculations)
│
├── Episodic Layer
│   ├── daily_dashboard    (KPI snapshots)
│   ├── decisions          (founder decisions + rationale)
│   ├── alerts             (risk events, escalations)
│   └── meetings           (attendees, outcomes, action items)
│
└── Semantic Layer
    ├── operational_rules  (escalation triggers, approval gates)
    ├── financial_rules    (thresholds, hard limits)
    └── routing_rules      (task routing, dispatch logic)

Knowledge Graph (entities + relationships)
├── Venture → has → Customer, Project, Agent, Harness
├── Customer → has → Project, Meeting, Contract
├── Project → has → Proposal, Contract, Invoice, Task
└── Agent → reads/writes → Memory Domain
```

---

## EVENT BUS (Event-Driven Rules)

No harness calls another harness directly. All communication via events.

```
Event Types:
  harness.task.created      → Dispatcher picks up
  harness.task.completed    → Registry logs, memory updated
  harness.task.blocked      → Escalation timer starts
  approval.requested        → Approval Engine queues
  approval.decided          → Workflow resumes
  memory.candidate.submitted → Reflection engine reviews
  alert.triggered           → Risk agent routes
  artifact.produced         → Memory + artifact store
```

---

## TOOL GATEWAY REGISTRY (P0 Tools)

```
Capability          Provider            Permission
─────────────────────────────────────────────────
read_dashboard      file_read           read
write_dashboard     file_write          write (gated)
read_crm            stub → real CRM     read
write_handoff       file_write          write
trigger_agent       runtime             execute (gated)
request_approval    approval_engine     request_approval
read_memory         memory_store        read (scoped)
write_memory        memory_store        write (via candidate)
escalate_alert      alert_router        execute
read_calendar       stub → Google Cal   read
read_email          stub → Gmail        read
```

---

## APPROVAL GATES (Human-in-the-Loop)

Always gated — NO autonomous execution:
- Financial transactions (any amount)
- Contract signing or LOI submission
- Investor communications
- Legal filings or regulatory submissions
- Hiring / firing decisions
- Strategy pivots

Approval flow: Agent submits → Queue bundles → Taz reviews batch →
Approve/Reject/Defer → Workflow resumes or stops.

---

## NON-GOALS (v1.0)

- Full autonomous company operation (no human in loop)
- Multi-tenant SaaS
- Public marketplace
- Third-party plugin ecosystem
- Mobile app
- Real-time financial transactions

---

## SYSTEM REQUIREMENTS

### Runtime
- Python ≥ 3.12
- LangGraph ≥ 0.2
- FastAPI + WebSockets
- SQLite (memory backend)
- Vector store (TF-IDF, upgradeable to embedding model)

### LLM Providers (priority order)
1. Anthropic Claude (primary, high-criticality agents)
2. Local router / Ollama (free tier, parallel fan-out)
3. NVIDIA NIM (optional, GPU-accelerated)

### Environment Variables (now AOS-prefixed)
```
AOS_API_TOKEN          WebSocket auth
AOS_LLM_BASE_URL       Local LLM router
AOS_LLM_API_KEY        Router auth
AOS_PAID_TIER          Enable paid models
AOS_TRACING            Tracing toggle
AOS_TRACING_BACKEND    Tracing backend
ANTHROPIC_API_KEY      Primary LLM
```

---

## SUCCESS METRICS (v1.0)

| Metric | Target |
|--------|--------|
| Founder time saved | > 2 hours/day |
| Pending approvals latency | < 24 hours |
| Daily executive brief | 100% delivered |
| Missed deadlines | 0 |
| Gated actions auto-executed | 0 (always gated) |
| P0 items active simultaneously | ≤ 3 |
| Test coverage | ≥ 637 tests, 100% pass |

