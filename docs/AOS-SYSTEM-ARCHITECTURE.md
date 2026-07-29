# AOS — Agentic Operating System: Complete System Architecture

> **Purpose of this document**: Provide an AI assistant with exhaustive, accurate contextual understanding of the AOS system — its architecture, runtime behavior, data flows, API surface, dashboard layer, and design system — so it can build a world-class dashboard for this agent system.

---

## 1. What AOS Is

AOS (Agentic Operating System) is a **governance-first, multi-venture agentic operating system** built by a solo founder. It orchestrates AI agent workflows ("harnesses") that autonomously run business operations across multiple companies. Think of it as an AI-powered executive team that monitors, prioritizes, delegates, and executes business tasks — surfacing only high-leverage decisions for founder approval.

**Stack**: Python 3.12+, Pydantic v2, FastAPI, LangGraph, SQLite (memory), vanilla ES modules (dashboard).

**Design philosophy**:
- **Identity-first**: Every agent has an explicit identity (id, role, persona, criticality)
- **Policy-driven**: Approval gates block execution; the founder is always in the loop for high-stakes decisions
- **Capability-first**: Tools are scoped per-agent via a Tool Gateway with permissions
- **Least privilege**: Agents only access what their manifest declares
- **Auditable**: Every decision, memory write, and tool call is logged immutably
- **Evaluated**: A post-validation evaluator checks outputs against financial ground truth

---

## 2. Ventures — The Business Entities

A **venture** is a business vertical bound to AOS. Each venture has its own configuration, artifacts, and routing manifest.

### Active Ventures

| Venture | ID | Domain | Status |
|---|---|---|---|
| **Netso Energy** | VEN-NETSO-001 | Bangladesh rooftop solar | Active, production |
| **TransitBD** | VEN-TRANSIT-001 | Bangladesh transit | Planning stage |

Each venture defines:
- `venture.yml` — Identity, artifacts (markdown files the agents read/write), financial constants
- `routing.manifest.json` — LLM model routing DAG specific to this venture
- Artifact paths — e.g., `DASHBOARD.md`, `WEEKLY-PLAN.md`, `BACKLOG.md`, `BLOCKERS.md`

### Netso Energy Financial Constants (Ground Truth)
These are **non-negotiable** numbers hardcoded in `aos/constants.py`:
- **True variable rate**: BDT 12.98 (NOT the blended rate of 14.81 — the evaluator rejects outputs using 14.81)
- **DSCR alert floor**: Threshold for debt-service coverage ratio alerts
- **NEM export rate**: Net energy metering export tariff
- **CAPEX per kW (Scenario A)**: Capital expenditure benchmark
- The evaluator (`aos/evaluator.py`) scans all CFO/Risk agent outputs for blended rate patterns and rejects them

---

## 3. Harnesses — AI Workflow Bundles

A **harness** is a self-contained AI workflow bundle. Each harness has a mission, scope, KPIs, input/output declarations, and a team of agents organized into roles.

### All 15 Harnesses

| Harness | Mission |
|---|---|
| `executive` | Autonomous executive team — daily briefings, cross-harness dispatch, approval gates |
| `sales` | Pipeline management, lead qualification, proposal generation |
| `finance` | Financial modeling, reporting, cash flow monitoring |
| `legal` | Contract review, compliance, regulatory monitoring |
| `marketing` | Campaign management, content strategy, brand |
| `operations` | Operational efficiency, procurement, logistics |
| `customer_success` | Customer onboarding, retention, support escalation |
| `ai_development` | AI/ML R&D, model training, experimentation |
| `software_dev` | Software engineering, code reviews, CI/CD |
| `investor_relations` | Investor communications, fundraising, board reports |
| `personal` | Founder personal tasks, scheduling, reminders |
| `knowledge` | Knowledge management, documentation, wiki |
| `evaluator` | Output quality assessment, ground truth validation |
| `autonomous` | Self-directed milestone execution from roadmap files |
| `youtube` | YouTube content strategy and optimization |

### Harness Manifest Structure (Executive Example)

Each harness directory contains:
```
aos/harnesses/executive/
├── harness.yml          # Mission, scope, KPIs, inputs, outputs, execution cycle
├── planner.yml          # Planner agent manifest (prioritization)
├── dispatcher.yml       # Dispatcher agent manifest (task routing)
├── memory.yml           # Memory configuration (domains, permissions)
├── tools.yml            # Tool registry (allowed tools per agent)
├── approvals.yml        # Approval policies (what requires founder sign-off)
├── evaluation.yml       # Output quality criteria
├── specialists/         # Specialist agent manifests
│   ├── ceo.yml
│   ├── cfo.yml
│   ├── coo.yml
│   ├── chief-of-staff.yml
│   ├── legal-officer.yml
│   ├── performance-analyst.yml
│   └── risk-officer.yml
└── sops/                # Standard operating procedures
```

### Agent Roles in a Harness

Every harness follows a **Planner → Dispatcher → Specialists** pattern:

1. **Planner** (`AGT-EXEC-PLANNER`): Reviews inputs, generates prioritized task list
2. **Dispatcher** (`AGT-EXEC-DISPATCH`): Routes tasks to the right specialists (local or cross-harness)
3. **Specialists**: Domain experts that execute tasks:
   - **COO** (`AGT-EXEC-COO`): Operations oversight, blocker tracking
   - **CFO** (`AGT-EXEC-CFO`): Financial analysis, runway calculations
   - **Chief of Staff** (`AGT-EXEC-CHIEFOFSTAFF`): Daily briefs, decision queue, inbox triage
   - **Risk Officer** (`AGT-EXEC-RSK`): DSCR monitoring, regulatory compliance
   - **Performance Analyst** (`AGT-EXEC-PERF`): KPI tracking, weekly reports
   - **Legal Officer** (`AGT-EXEC-LEGAL`): Contract and compliance review
   - **CEO** (`AGT-EXEC-CEO`): Strategic decisions, investor relations

### Agent Manifest Fields

Each agent YAML defines:
```yaml
id: AGT-EXEC-CFO
name: Chief Financial Officer
criticality: high           # critical | high | medium | low → determines LLM model tier
persona: |
  Senior CFO with deep expertise in solar project finance...
responsibilities:
  - Financial modeling and scenario analysis
  - Cash flow forecasting
  - DSCR monitoring
financial_rules: true       # enables evaluator financial checks
tools:                      # allowed tools via Tool Gateway
  - financial_calculator
  - spreadsheet_reader
memory_domains:             # what memory layers this agent can read/write
  - company_facts
  - financial_data
team:                       # optional team assignment
  name: finance_team
  strategy: sequential      # sequential | parallel | voting
  weight: 1.0               # voting weight (for voting strategy)
```

### Agent Re-homing (from Legacy System)

The previous Netso AI system had named agents that were re-homed into AOS roles:
- **LILTAZ** → Planner + Dispatcher
- **ATLAS** → COO
- **MINERVA** → CFO
- **SHIELD** → Legal + Risk Officer
- **LENS** → Performance Analyst
- **COUNCIL** → Deliberation (voting strategy teams)
- New: **Chief of Staff** (no legacy equivalent)

---

## 4. The LangGraph Runtime — How Harnesses Execute

### CycleState (TypedDict)

Every harness execution carries a `CycleState` — a typed dictionary that flows through the graph:

```python
class CycleState(TypedDict):
    # Identity
    venture_id: str
    harness_id: str
    cycle_id: str
    venture_artifacts: dict[str, str]  # artifact ref → file content

    # Inputs
    inputs: dict[str, Any]

    # Accumulated results (Annotated[list, operator.add] for list merging)
    step_results: Annotated[list[dict], operator.add]
    approval_queue: Annotated[list[dict], operator.add]
    resolved_approval_ids: Annotated[list[str], operator.add]
    handoffs: Annotated[list[dict], operator.add]
    errors: Annotated[list[dict], operator.add]

    # Per-step outputs (overwritten each node)
    review_output: dict
    prioritize_output: dict
    delegate_output: dict
    specialists_output: dict
    summarize_output: dict
    approval_gates_output: dict
    execute_output: dict
    log_output: dict

    # Loop engineering
    iteration_count: int
    max_iterations: int
    completion_criteria: dict[str, Any]
    loop_context_summary: str
    iteration_history: Annotated[list[dict], operator.add]
    execution_trace: Annotated[list[dict], operator.add]
```

### Graph Topology (9 Nodes)

```
review → prioritize → delegate → specialists → summarize → approval_gates
                                                                    │
                                                            ┌───────┴───────┐
                                                          execute          log
                                                            │               │
                                                            └──────┬────────┘
                                                                   log
                                                                   │
                                                            ┌──────┴──────┐
                                                        loop_control     END
                                                            │
                                                          review (loop back)
```

#### Node Descriptions

1. **`review_node`**: COO reads venture artifacts (DASHBOARD.md, WEEKLY-PLAN.md, BACKLOG.md, BLOCKERS.md) via ToolGateway. Falls back to direct `Path.read_text()` if gateway unavailable. Capped at 2000 chars per artifact (`ARTIFACT_READ_LIMIT_CHARS`).

2. **`prioritize_node`**: Planner agent receives review output + memory context (capped at 3000 chars via `MEMORY_CONTEXT_CHAR_LIMIT`). Generates prioritized task list as JSON.

3. **`delegate_node`**: Dispatcher routes tasks to specialists. Produces `assignments` array mapping tasks to agent IDs. **Fallback routing**: if JSON parsing fails, `_fallback_routing()` uses regex to extract `AGT-EXEC-XXX` patterns from raw LLM text and builds synthetic assignments.

4. **`specialists_node`**: Parallel fan-out to assigned specialists via `_run_parallel()`. Supports three **team coordination strategies**:
   - `sequential`: Members run in order; each receives prior members' outputs
   - `parallel`: All members run concurrently via `asyncio.gather + to_thread` (`MAX_CONCURRENCY = 8`)
   - `voting`: Members run in parallel with weights; consensus requires ≥67% weight agreement (`CONSENSUS_WEIGHT_THRESHOLD = 0.67`)

5. **`summarize_node`**: Chief of Staff synthesizes all specialist outputs into an executive brief.

6. **`approval_gates_node`**: Checks specialist outputs for items requiring founder approval. Creates approval queue items. **Critical behavior**: gates poll `wait_for_decision()` and BLOCK execution until the founder approves/rejects. Never fire-and-forget. (FIX-03 hardening fix)

7. **`execute_node`**: Runs approved actions via Tool Gateway. Only executes items that passed approval.

8. **`log_node`**: Persists results to memory store. Writes execution trace with `duration_ms` timing data. Saves to both episodic memory and session logs.

9. **`loop_control_node`**: Evaluates completion criteria via `_check_completion_criteria()`:
   - `all_tasks_complete`: planned tasks ≥ executed tasks
   - `error_threshold`: error count ≥ limit
   - `approval_cleared`: no pending approvals
   - `handoffs_empty`: no queued handoffs

   If criteria met → END. Otherwise → loop back to `review_node` with fresh state via `_reset_iteration_state()` (clears per-step outputs, preserves iteration count and history).

### Cross-Harness Agent Resolution

`Registry.resolve_agent(agent_id)` searches ALL harness bundles (planner, dispatcher, specialists) and returns `(agent, bundle)` tuple. This enables the dispatcher to route tasks to specialists in other harnesses (e.g., executive dispatcher → sales specialist).

### Parallel Execution

`_run_parallel(items, fn)` dispatches via:
1. `asyncio.gather` + `asyncio.to_thread` (preferred)
2. Fallback: `ThreadPoolExecutor` when no event loop exists
3. Max concurrency: 8 (`MAX_CONCURRENCY`)

---

## 5. LLM Routing — 9router and Model Selection

### Architecture

All LLM calls route through **9router** at `localhost:20128` (a local model proxy). The system uses a **venture-specific routing manifest** system.

### Model Table

| Tier | 9router Model ID | Direct Anthropic Fallback | Used For |
|---|---|---|---|
| `default` | `cu/claude-4.5-sonnet` | `claude-sonnet-4-20250514` | Critical + high criticality agents |
| `reasoning` | `cu/claude-4.5-opus-high-thinking` | `claude-opus-4-20250514` | Direct lookup only, never via criticality |
| `fast` | `cu/claude-4.5-haiku` | `claude-haiku-4-5-20251001` | Subagent tier |
| `free` | Round-robin pool | `claude-sonnet-4-20250514` | Medium/low criticality agents |

### Criticality → Model Mapping

```python
CRITICALITY_TO_MODEL = {
    "critical": "default",   # dispatcher, planner → paid Sonnet
    "high":     "default",   # COO, CFO, Chief of Staff → paid Sonnet
    "medium":   "free",      # routine specialists → free tier
    "low":      "free",      # lightweight tasks → free tier
}
```

### Free-Tier Round-Robin Pool

6 models cycled via thread-safe counter with `threading.Lock`:
1. `openrouter/google/gemma-4-31b-it:free`
2. `openrouter/nvidia/stepfun-ai/step-3.7-flash`
3. `openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
4. `openrouter/qwen/qwen3-next-80b-a3b-instruct:free`
5. `openrouter/meta/llama-4-scout-17b-16e-instruct`
6. `openrouter/google/gemini-2.5-flash`

### Venture Routing Manifest

Each venture declares a DAG of allowed model transitions:
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

Validated at harness load time: DAG must be acyclic, fallback path must be a valid Hamiltonian path, all criticality levels must be mapped.

### LLM Fallback Chain

```
9router (with usability guard) → NVIDIA NIM → Direct Anthropic → Dry Run
```

- **9router usability guard**: Checks `/v1/models` returns models AND `~/.9router/db.json` has at least one enabled proxy pool with valid auth
- **Per-model retry**: 3 retries with exponential backoff per model
- **HTTP 404**: Breaks immediately to next model (don't retry)
- **Model-level fallback**: `default` → `fast` → `free` tier
- **Reasoning fallback**: If response has empty content but non-empty reasoning field, reasoning text is used as content
- **`_parse_first_json`**: Extracts first complete JSON object from malformed LLM responses — handles raw JSON, fenced code blocks, partial content extraction

---

## 6. Memory System

Three-layer memory with permissions, candidates, and audit trail:

### Layers

| Layer | Purpose | Example Domains |
|---|---|---|
| **Long-term** | Persistent company facts (key-value, refs) | `company_facts`, `financial_data` |
| **Episodic** | Events, decisions, meetings (time-sequenced) | `daily_dashboard`, `meeting_notes` |
| **Semantic** | Rules, patterns, standards (how things work) | `pricing_model`, `sops` |

### Key Properties

- **Immutable writes**: Creates new entries, never modifies existing ones. `MemoryEntry` is `@dataclass(frozen=True)`
- **Content fingerprinting**: SHA-256 hash for deduplication
- **Classification levels**: `public`, `internal`, `confidential`, `restricted`, `founder_only`
- **Agent permissions**: Each agent's manifest declares which `memory_domains` it can access
- **Candidate system**: Agents submit memory candidates → reflection engine decides (store/reject/summarize/merge/version) → audit trail
- **Context compression**: `MemoryStore.retrieve_for_agent()` caps output at `max_chars=3000` to prevent prompt bloat
- **Audit trail**: Every memory operation logged as an immutable `AuditRecord`
- **Disk persistence**: Markdown files in venture artifact paths
- **Vector store**: SQLite-backed with vector search + keyword fallback (`aos/vector_store.py`)

---

## 7. Orchestration Pipeline

### Standard Pipeline (`aos/orchestrate/pipeline.py`)

End-to-end coordinator chaining: **spec → autoplan → implement → reviewloop → ship** with configurable human gates.

```python
class Phase(str, Enum):
    SPEC = "spec"
    AUTOPLAN = "autoplan"
    IMPLEMENT = "implement"
    REVIEWLOOP = "reviewloop"
    DOUBT = "doubt"
    SHIP = "ship"
```

`PipelineContext` carries: one-liner, plan path, skip flags, gate configuration, review scores, PR URL, commit SHA.

CLI: `python -m aos orchestrate --one-liner "Add user auth endpoint" --gate spec --gate plan --auto`

### Autonomous Pipeline (`aos/orchestrate/autonomous.py`)

Self-directed milestone execution from a roadmap file:

```
discuss → plan → execute → audit → [approve|rollback] → next phase
```

**Gating policies**:
- `POL-AUTO-001`: Phase Transition Gate — approval required before executing each phase
- `POL-AUTO-002`: Milestone Completion Gate — approval when all phases pass
- `POL-AUTO-003`: Phase Rollback Gate — approval before rolling back on audit failure

Uses its own LangGraph `StateGraph` (`AutonomousState`) with `PhaseRecord` tracking.

CLI: `python -m aos orchestrate --autonomous --roadmap-file ROADMAP.md`

### Approval Gates (`aos/orchestrate/gates.py`)

Human-in-the-loop gates that BLOCK execution:
- Gates poll `wait_for_decision()` and never proceed without a response
- Supports auto-approval when exit criteria met (`--auto` flag)
- Gate timeout: configurable, default 300 seconds
- All gate decisions logged with identity and rationale

---

## 8. Security & Hardening

### Path Traversal Defense (`aos/hardening.py`)
`sanitize_path()` blocks:
- URL-encoded traversal (`%2e%2e/`)
- Null bytes (`\x00`)
- Backslashes, absolute paths, tilde expansion
- `..` normalization bypasses (compares `posixpath.normpath(path)` against original)

### WebSocket Authentication
- WS endpoint requires `AOS_API_TOKEN` env var as bearer token
- Connection limiter caps concurrency at 10 (`ConnectionLimiter`)
- Both use `threading.Lock` for thread safety

### Shell Execution
- Subprocess paths use regex allowlist + `shlex` validation
- New executors must mirror `aos/hardening.py` patterns

### Output Validation (`aos/evaluator.py`)
- Validates agent outputs against financial ground truth
- Financial agents (CFO, Risk) checked for: blended rate usage (14.81), Scenario B references without approval, DSCR violations
- All agents checked for: structural issues (raw_response detection)

---

## 9. The API Layer — FastAPI Backend

Backend runs on **port 7001** (`aos/api.py` + `odysseus/routes/aos_routes.py`).

### Core REST Endpoints

| Endpoint | Method | Purpose | Response Shape |
|---|---|---|---|
| `/api/dashboard` | GET | Aggregate KPIs | `{harnesses, tests, memory_domains, entity_count, event_count, approval_count, health_score, ws_connections, ws_max_connections}` |
| `/api/harnesses` | GET | List all loaded harnesses | `[{id, name, status, venture, agents_count, ...}]` |
| `/api/summary` | GET | System summary text | `{summary: string}` |
| `/api/pipeline/status` | GET | Current pipeline state | `{phase, status, started_at, ...}` |
| `/api/pipeline/history` | GET | Historical pipeline runs | `[{id, phases, status, duration_s, ...}]` |
| `/api/approvals` | GET | Pending approval items | `[{id, type, description, status, created_at, ...}]` |
| `/api/approvals/{id}/approve` | POST | Approve an item (auth required) | `{approved: true, id}` |
| `/api/approvals/{id}/reject` | POST | Reject an item (auth required) | `{rejected: true, id}` |
| `/api/memory/summary` | GET | Memory store summary | `{layers, domains, entry_count, ...}` |
| `/api/events` | GET | Event log | `[{timestamp, event, source, ...}]` |
| `/api/entity-index` | GET | Entity relationship index | `{entities: [...], relationships: [...]}` |
| `/api/agents` | GET | All registered agents | `[{id, name, harness, criticality, role, ...}]` |
| `/api/system/status` | GET | System health and config | `{engine_online, version, uptime, ...}` |
| `/api/health` | GET | Basic health check | `{status: "ok"}` |
| `/api/ws/stats` | GET | WebSocket connection stats | `{connections, max_connections}` |

### Netso Customer Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/netso/customers/{site_id}/generation` | GET | Solar generation data for a site |
| `/api/netso/customers/{site_id}/savings` | GET | Customer savings breakdown |
| `/api/netso/customers/{site_id}/billing` | GET | Billing history and current bill |
| `/api/netso/portfolio` | GET | Internal portfolio overview (all sites) |
| `/api/netso/financials` | GET | Internal financial summary |

### Sales Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/sales/status` | GET | Sales pipeline status |

### WebSocket — Live Execution Streaming

```
ws://localhost:7001/ws/harness/{harness_name}?token={AOS_API_TOKEN}
```

- Streams graph execution events in real-time (node entry, node exit, state changes)
- Token authentication required
- Connection limiter: max 10 concurrent connections
- Events are JSON with `{event, data, timestamp}` shape

### Authentication

- Bearer token via `AOS_API_TOKEN` environment variable
- Required for: approval actions (approve/reject), WebSocket connections
- Skipped in local-dev mode (when `AOS_API_TOKEN` is not set)

### Service Layer

Backend services (in `aos/services/`):
- `pipeline.py` — Pipeline state management
- `approvals.py` — Approval queue operations
- `memory.py` — Memory store queries
- `sales.py` — Sales pipeline data
- `system.py` — System health and status
- `agents.py` — Agent registry queries
- `netso_customer.py` — Netso customer data (generation, savings, billing, portfolio, financials)

---

## 10. The Odysseus Dashboard — Frontend

### Architecture

The dashboard is a **modular vanilla ES module application** (no framework — no React, Vue, or Angular). It uses native browser modules (`import`/`export`) with a custom pub/sub store.

- **Static server**: Port 8090
- **API proxy**: All API calls go through Odysseus proxy at `/api/aos/*` and `/api/netso/*` (never direct to port 7001)
- **Entry point**: `odysseus/dashboard/index.js`

### Module Structure

```
odysseus/dashboard/
├── index.js                    # Entry point — openPanel()/closePanel() for Odysseus ModalManager
├── dashboard.css               # Main stylesheet
├── dashboard-a11y.css          # Accessibility styles
├── preview.html                # Self-contained inline app (NOT connected to modular pages)
│
├── layouts/
│   └── dashboard-layout.js     # Sidebar + header + main content area (glass-morphism)
│
├── pages/                      # Each page is an ES module with render(container) → unsub function
│   ├── overview.js             # KPI tiles, health score, system status
│   ├── harnesses.js            # Harness list and details
│   ├── pipelines.js            # Pipeline status and history
│   ├── approvals.js            # Approval queue with approve/reject actions
│   ├── memory.js               # Memory store explorer
│   ├── entities.js             # Entity relationship viewer
│   ├── events.js               # Event log viewer
│   ├── sales.js                # Sales pipeline dashboard
│   ├── system.js               # System health and configuration
│   └── netso/                  # Netso venture-specific pages
│       ├── netso-overview.js   # Netso venture overview
│       ├── customer-generation.js  # Solar generation data per site
│       ├── customer-savings.js     # Customer savings breakdown
│       ├── customer-billing.js     # Billing history
│       ├── internal-portfolio.js   # Internal portfolio (all sites)
│       └── internal-financials.js  # Internal financial summary
│
├── services/
│   ├── api.js                  # AosApi client class — all REST calls
│   ├── websocket.js            # AosWebSocket — live execution streaming with auto-reconnect
│   └── keyboard.js             # Keyboard shortcuts (Cmd+K palette, number keys)
│
├── stores/
│   └── dashboard.js            # DashboardStore — central pub/sub state management
│
├── widgets/
│   ├── kpi-tile.js             # KPI card component
│   ├── dscr-banner.js          # DSCR alert banner
│   ├── savings-tile.js         # Savings display component
│   ├── status-dot.js           # Colored status indicator
│   └── trend-indicator.js      # Trend arrow component
│
└── components/                 # (empty — available for shared UI components)
```

### Store — Central State Management

`DashboardStore` is a lightweight pub/sub store with no framework dependency:

```javascript
// State shape
{
  // Connection
  engineOnline: false,
  wsConnections: 0,
  wsMaxConnections: 10,

  // KPIs
  harnessCount: 0,
  testCount: 0,
  memoryDomains: 0,
  entityCount: 0,
  eventCount: 0,
  approvalCount: 0,
  healthScore: null,

  // Live data
  harnesses: [],
  pipeline: null,
  approvals: [],
  memory: null,
  sales: null,
  system: null,
  agents: [],
  events: [],
  entityIndex: null,

  // Netso customer dashboard
  role: 'internal',      // 'customer' | 'internal' | 'admin'
  siteId: 'CGS-001',
  netsoGeneration: null,
  netsoSavings: null,
  netsoBilling: null,
  netsoPortfolio: null,
  netsoFinancials: null,

  // UI
  currentPage: 'overview',
  loading: false,
  error: null,
  lastUpdated: null,
}
```

**Store methods**: `loadDashboard()`, `loadHarnesses()`, `loadPipeline()`, `loadApprovals()`, `loadMemory()`, `loadSales()`, `loadSystem()`, `loadAgents()`, `loadEvents()`, `loadEntityIndex()`, `loadNetsoGeneration()`, `loadNetsoSavings()`, `loadNetsoBilling()`, `loadNetsoPortfolio()`, `loadNetsoFinancials()`, `approveDecision(id)`, `rejectDecision(id)`, `setPage(page)`, `setRole(role)`, `setSiteId(siteId)`, `startAutoRefresh(intervalMs)`, `stopAutoRefresh()`.

### Page Rendering Pattern

Each page exports a `render(container)` function that:
1. Clears the container
2. Builds DOM elements
3. Subscribes to the store for reactive updates
4. Returns an unsubscribe function for cleanup
5. Uses `textContent` (not `innerHTML`) for dynamic values (XSS-safe)

### Navigation

Sidebar navigation with two sections:
1. **Core pages**: Overview, Harnesses, Pipelines, Approvals, Memory, Entities, Events, Sales, System
2. **Netso pages** (role-gated):
   - Customer-facing (`customer`, `admin`): Netso Overview, Generation, Savings, Billing
   - Internal-only (`internal`, `admin`): Portfolio, Financials

### API Client

`AosApi` class with two base URLs:
- Core: `/api/aos` (proxied to port 7001)
- Netso: `/api/netso` (proxied to port 7001)

### WebSocket Client

`AosWebSocket` class:
- Connects to `ws://host/ws/harness/{harnessName}?token=...`
- Auto-reconnect with exponential backoff (1s → 30s max)
- Event-based: `on('connected' | 'disconnected' | 'error' | 'message' | custom, callback)`
- Disconnects when switching pages (prevents stale connections)

### Known Issue: preview.html

`preview.html` is a **self-contained inline app** with all HTML/CSS/JS in a single file. It is NOT connected to the modular ES module page system. It was used for early prototyping but is now orphaned from the main dashboard architecture.

---

## 11. Design System

Reference: `DESIGN.md`

### Aesthetic

**Industrial/Utilitarian** — Bloomberg Terminal meets GitHub. Information density over decoration. **Dark mode only**.

### Typography

| Use | Font | Weights |
|---|---|---|
| Display / headings | Clash Grotesk | 400, 500, 600, 700 |
| Body / UI text | DM Sans | 400, 500, 600, 700 (+ italic) |
| Data / code / mono | JetBrains Mono | 400, 500, 600 |

### Colors

| Token | Value | Usage |
|---|---|---|
| Primary (Emerald) | `#10B981` | Accents, active states, success |
| Background | `#0D1117` | Page background |
| Surface | `#161B22` | Cards, panels |
| Border | `#30363D` | Subtle divisions |
| Text primary | `#E6EDF3` | Main text |
| Text secondary | `#8B949E` | Captions, metadata |
| Warning | `#F59E0B` | Warnings, pending states |
| Error | `#EF4444` | Errors, offline states |
| Muted | `#6E7681` | Idle states, disabled |

### Layout

- **Sidebar**: 220px fixed width
- **Content**: Fluid, fills remaining space
- **Base spacing unit**: 8px
- **Density**: Compact — maximize information per viewport

### Reference Sites for Dashboard Inspiration

- [Langfuse](https://langfuse.com) — AI observability dashboard
- [n8n](https://n8n.io) — Workflow automation UI
- [GitHub](https://github.com) — Repository management UI

---

## 12. Registry & Manifest Loading

### Registry (`aos/registry.py`)

`Registry` is the central manifest store:

```python
@dataclass
class Registry:
    venture: Venture | None = None
    harnesses: dict[str, HarnessBundle] = field(default_factory=dict)
```

`HarnessBundle` contains: `harness`, `planner`, `dispatcher`, `specialists` (dict), `teams` (dict), `memory`, `tools`, `approvals`, `evaluation`, `sops` (dict).

Key methods:
- `get_harness(id)` → HarnessBundle
- `get_agent(id)` → Agent (searches all bundles)
- `resolve_agent(id)` → (Agent, HarnessBundle) (for cross-harness dispatch)
- `all_agents()` → list of all agents across all harnesses
- `summary()` → human-readable registry state

### Schema Validation

All manifests validated against Pydantic v2 models in `aos/schemas/`:
- `harness.py` — Harness, AgentTeam
- `agent.py` — Agent
- `venture.py` — Venture
- `memory.py` — Memory config
- `tool.py` — ToolRegistry
- `evaluation.py` — Evaluation criteria
- `sop.py` — Standard Operating Procedures
- `policy_collection.py` — PolicyCollection (approval policies)

---

## 13. CLI Reference

| Command | Flags | Purpose |
|---|---|---|
| `python -m aos validate` | `[--harness NAME] [--venture NAME] [--verbose]` | Validate all manifests |
| `python -m aos status` | `[--harness NAME] [--venture NAME]` | Show system status |
| `python -m aos run` | `[--harness NAME] --venture NAME [--dry-run] [--prefer router\|anthropic] [--verbose]` | Execute a harness cycle |
| `python -m aos orchestrate` | `[plan_path] [--one-liner TEXT] [--skip-spec] [--skip-plan] [--skip-review] [--gate NAME] [--auto] [--dry-run] [--max-review-iterations N] [--autonomous] [--roadmap-file PATH] [--gate-timeout SEC] [--max-retries N]` | End-to-end pipeline |
| `python -m aos ventures` | | List all discovered ventures |
| `python -m aos approvals` | `[list\|approve-all\|reject-all\|approve ID\|reject ID] [--note TEXT]` | Manage approval queue |

---

## 14. Testing

```bash
pytest -q                                                      # fast
pytest --cov=aos --cov=odysseus --cov-report=term-missing      # coverage
pytest -m unit                                                 # unit only
pytest -m integration                                          # integration only
```

- **559+ tests** passing (as of last session)
- Coverage minimum: 60% (`fail_under = 60`)
- Sources: `aos` + `odysseus`
- Branch coverage enabled
- `asyncio_mode = "auto"` — no manual `@pytest.mark.asyncio` needed
- AAA pattern (Arrange-Act-Assert)
- Strategic surfaces: approval-gate blocking, path sanitization, WS auth, evaluator financial checks, cross-harness dispatch

---

## 15. Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `AOS_API_TOKEN` | Yes | WS + harness access bearer token |
| `ANTHROPIC_API_KEY` | Yes | Primary LLM auth |
| `ANTHROPIC_BASE_URL` | No | Override Anthropic API endpoint |
| `AOS_LLM_BASE_URL` | No | Local LLM router (default: `http://localhost:20128`) |
| `AOS_LLM_API_KEY` | No | Auth for local router |
| `NVIDIA_NIM_API_KEY` | No | GPU-accelerated inference via NVIDIA NIM |
| `AOS_PAID_TIER` | No | Set `"1"` for paid/faster models |
| `AOS_FREE_TIER` | No | Set `"1"` to route medium/low to free model pool |
| `AOS_TRACING` | No | `"enabled"` or `"disabled"` |
| `AOS_TRACING_BACKEND` | No | `"auto"`, `"langfuse"`, or `"json"` |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse public API key |
| `LANGFUSE_SECRET_KEY` | No | Langfuse secret API key |

---

## 16. Data Flow Summary

```
Venture Artifacts (markdown files)
         │
         ▼
    ┌─────────┐
    │ Registry │ ◄── Harness manifests (YAML) + Agent manifests + Tool manifests
    └────┬────┘
         │ load_registry()
         ▼
    ┌──────────────┐
    │ build_graph() │ ◄── LangGraph StateGraph with MemorySaver checkpointer
    └──────┬───────┘
           │ run_cycle_graph()
           ▼
    ┌──────────────────────────────────────────────────────┐
    │ review → prioritize → delegate → specialists →       │
    │ summarize → approval_gates → execute → log →         │
    │ loop_control → [END or review]                       │
    └──────────────────────────────────────────────────────┘
           │                    │
    LLM calls via              │
    RouterLLMClient            │
    (9router/NIM/Anthropic)    │
           │                    │
           ▼                    ▼
    ┌────────────┐     ┌──────────────┐
    │ Memory     │     │ Approval     │
    │ Store      │     │ Queue        │
    └────┬───────┘     └──────┬───────┘
         │                    │
         ▼                    ▼
    ┌──────────────────────────────────┐
    │ FastAPI Backend (port 7001)      │
    │ REST endpoints + WebSocket       │
    └──────────────┬───────────────────┘
                   │ proxy (/api/aos/*, /api/netso/*)
                   ▼
    ┌──────────────────────────────────┐
    │ Odysseus Dashboard (port 8090)   │
    │ Vanilla ES modules + pub/sub     │
    │ DashboardStore → Pages → Widgets │
    └──────────────────────────────────┘
```

---

## 17. What the Dashboard Needs to Show

Based on the API surface and current page structure, a world-class dashboard should visualize:

### Core AOS Pages
1. **Overview**: System-wide KPIs (harness count, test count, memory domains, entities, events, pending approvals, WS connections, health score), engine status
2. **Harnesses**: All 15 harnesses with status, venture binding, agent count, last execution time, criticality
3. **Pipelines**: Active orchestrate pipeline phases (spec → autoplan → implement → reviewloop → ship), history of runs with duration and status
4. **Approvals**: Pending approval queue with approve/reject actions, policy reference, decision history
5. **Memory**: Three-layer memory explorer — long-term, episodic, semantic — with domain filtering, classification badges, entry count
6. **Entities**: Entity relationship graph/index — who/what is connected to what
7. **Events**: Chronological event log with source, type, filtering
8. **Sales**: Pipeline funnel, lead stages, revenue forecasts
9. **System**: Engine health, LLM routing status, model usage, uptime, configuration

### Netso Venture Pages
10. **Netso Overview**: Venture-level metrics, site map, active projects
11. **Generation**: Per-site solar generation data (kWh, capacity factor, daily/monthly/yearly)
12. **Savings**: Customer savings breakdown (BDT saved, rate comparison, projections)
13. **Billing**: Invoice history, current bill, payment status
14. **Portfolio** (internal): All sites overview, aggregate capacity, portfolio performance
15. **Financials** (internal): Revenue, CAPEX, OPEX, DSCR tracking, cash flow

### Widgets Available
- `kpi-tile.js` — KPI card with icon, label, value, optional accent
- `dscr-banner.js` — DSCR alert banner (financial health warning)
- `savings-tile.js` — Savings display component
- `status-dot.js` — Colored dot indicator (online/offline/warning/idle)
- `trend-indicator.js` — Trend arrow (up/down/flat)

---

## 18. Resilience Patterns

These patterns are critical to understand when building dashboard features that display system status:

1. **LLM fallback chain**: 9router → NVIDIA NIM → direct Anthropic → dry run
2. **9router usability guard**: Pre-flight check before routing LLM calls
3. **`_parse_first_json`**: Extracts JSON from malformed LLM responses
4. **Tool gateway fallback**: Falls back to direct file read if gateway unavailable
5. **Memory context compression**: Caps at 3000 chars per agent retrieval
6. **Cross-harness agent resolution**: Searches all bundles for agent dispatch
7. **Fallback routing**: Regex extraction of agent IDs from raw text when JSON parsing fails
8. **Rate limiting + connection limiting**: Thread-safe with `threading.Lock`
9. **Loop state reset**: Fresh state per iteration to prevent context overflow

---

*Document generated from source code analysis of the AOS codebase. All paths, interfaces, and behaviors verified against the actual implementation.*
