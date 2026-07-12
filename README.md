# AOS — Agentic Operating System

> **One founder. Multiple ventures. One operating system.**

AOS is a governance-first, multi-venture agentic operating system. It orchestrates autonomous business systems (harnesses) for a solo founder running multiple companies — starting with **Netso Energy** (BOO/OPEX rooftop solar, Bangladesh RMG sector).

## Philosophy

Every architectural mistake gets multiplied across every future harness. So we build one production-grade harness, establish the standards, then replicate.

- **Identity-first.** Every actor has a persistent identity.
- **Policy-driven.** Rules are declarative, versioned, centrally managed.
- **Capability-first.** Agents request capabilities, not vendor APIs.
- **Least privilege.** Every agent has explicit memory and tool permissions.
- **Auditable.** Every action leaves an immutable trail.
- **Evaluated.** Every agent output is scored against metrics with hard-fail conditions.

## Architecture

```
aos/
├── __main__.py              # CLI entry (validate/status/run/orchestrate/ventures/approvals)
├── graph.py                 # LangGraph StateGraph runtime
├── api.py                   # FastAPI + WebSocket server
├── orchestrate/             # End-to-end pipeline (spec -> plan -> implement -> review -> ship)
│   ├── pipeline.py
│   └── gates.py
├── registry.py              # Harness/agent registry + cross-harness dispatch
├── validator.py             # Manifest validation
├── llm.py                   # LLM routing (Anthropic + local Ollama + NVIDIA NIM)
├── context.py               # System-prompt assembly from agent manifest
├── usage.py                 # Per-agent per-model token tracking
├── evaluator.py             # 8 financial checks (blended rate, savings %, DSCR, PPA, Scenario B, NEM export, CAPEX A, true variable rate)
├── memory.py                # SQLite-backed persistent memory store
├── approval_queue.py        # Persistent approval queue (JSONL)
├── platform/                # JSON Schemas (identity, harness, agent, policy)
├── ventures/
│   ├── netso/               # Active venture (financial constants, artifacts)
│   └── transitbd/           # Planning-stage venture
├── harnesses/               # 13 harness bundles
│   ├── executive/           # Reference implementation (17 manifests)
│   ├── sales/
│   ├── finance/
│   ├── legal/
│   ├── marketing/
│   ├── operations/
│   ├── customer_success/
│   ├── ai_development/
│   ├── software_dev/
│   ├── investor_relations/
│   ├── personal/
│   ├── knowledge/
│   └── evaluator/
└── services/                # WebSocket telemetry, executors

odysseus/                    # FastAPI dashboard (REST + WS + UI)

docs/
└── specs/
    └── 2026-06-30-executive-harness-design.md
```

## What exists today

| Component | Status |
|---|---|
| Platform schemas (identity, harness, agent, policy) | ✅ Written |
| Netso venture binding | ✅ Written (financial constants, artifacts, re-homing map) |
| TransitBD venture | 📋 Planning stage |
| Executive Harness — 17 manifests | ✅ Written |
| 12 additional harnesses (Sales, Finance, Legal, Marketing, Operations, Customer Success, AI Development, Software Dev, Investor Relations, Personal, Knowledge, Evaluator) | ✅ Written |
| 4 SOPs (session protocol, daily loop, approval routing, weekly review) | ✅ Written |
| Design spec | ✅ Written |
| Runtime — LangGraph StateGraph (`aos/graph.py`) | ✅ Fully implemented |
| API server — FastAPI + WebSocket (`aos/api.py`) | ✅ Fully implemented |
| CLI (`python -m aos`) | ✅ validate / status / run / orchestrate / ventures / approvals |
| Orchestrate pipeline (spec -> plan -> implement -> review -> ship) | ✅ Fully implemented |
| Memory persistence (SQLite-backed store) | ✅ Fully implemented |
| Approval queue (persistent JSONL) | ✅ Fully implemented |
| Cross-harness dispatch | ✅ Fully implemented |
| Test suite | ✅ 696 tests |

## Re-homing from existing Netso AI system

The existing `Netso_HQ/ai_system/` workforce is re-homed (not replaced):

| Existing | AOS role |
|---|---|
| LILTAZ | Planner + Dispatcher core |
| ATLAS | COO specialist |
| MINERVA | CFO specialist |
| SHIELD | Splits → Legal Officer + Risk Officer |
| LENS | Performance Analyst |
| COUNCIL | Deliberation escalation tier |
| *(new)* | Chief of Staff |

Tier-2 specialists (SPARK, AURUM, SIGNAL, FORGE, NEXUS, BEACON, SCRY, etc.) stay where they are — they belong to future harnesses and are dispatched to *by* the Executive Harness.

## Build order

| Phase | Harness | Status | Why |
|---|---|---|---|
| **1** | **Executive** | ✅ Complete | Reference implementation |
| **2** | **Knowledge** | ✅ Complete | Shared memory for all agents |
| **4** | **Sales** | ✅ Complete | Highest ROI for Netso today |
| **6** | **Finance** | ✅ Complete | Cash flow + investor reporting |
| 7 | Legal | ✅ Complete | Standardized documentation |
| 8 | Operations | ✅ Complete | Day-to-day operations |
| 9 | Customer Success | ✅ Complete | Retention + satisfaction |
| 10 | Marketing | ✅ Complete | Demand generation |
| 11 | AI Dev | ✅ Complete | AI model development |
| 12 | Software Dev | ✅ Complete | Software engineering |
| 13 | Investor Relations | ✅ Complete | Fundraising + reporting |
| 14 | Personal | ✅ Complete | Founder personal workflows |
| 15 | Evaluator | ✅ Complete | Metrics + continuous improvement |
| 16+ | As needed | ⬜ Planned | Additional harnesses on demand |

## Quick Start

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in AOS_API_TOKEN + ANTHROPIC_API_KEY

# Validate all manifests
python -m aos validate

# Show system status
python -m aos status

# Dry-run a harness cycle
python -m aos run --venture netso --dry-run

# Run the test suite
pytest -q

# Run with coverage
pytest --cov=aos --cov=odysseus --cov-report=term-missing
```

## Key constraints

- All financial numbers must match `GROUND_TRUTH_CONSTANTS.md` (auto-generated by `core_economics.py`). Blended rate BDT 14.81 is **never** used for savings. True Variable Rate BDT 12.98 is correct.
- Scenario A (BDT 55,000/kW CAPEX) is default for all external docs. Scenario B activates only after NBR confirms 0% duty for RESCO.
- DSCR < 2.0x = immediate alert. DSCR < 2.25x = escalation.
- No more than 3 active P0 items. Four is scatter.

## License

Private. Founder: Tazwar Mahtab.
