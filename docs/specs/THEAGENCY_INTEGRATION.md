# TheAgency × AOS Integration Analysis

> Date: 2026-07-26
> Status: Brainstorm / Architecture Proposal
> Source: https://github.com/the-agency-ai/the-agency

## Executive Summary

TheAgency and AOS solve **complementary problems**:

| Layer | AOS | TheAgency |
|-------|-----|-----------|
| **What** | Business orchestration (ventures, financials, approvals) | Developer workflow orchestration (code, git, quality gates) |
| **How** | LangGraph StateGraph with LLM agents | Bash tools + hookify rules + SQLite ISCP |
| **Who** | COO, Planner, Dispatcher, Chief of Staff, Specialists | Captain, Tech-Lead, Reviewers (code/design/security/test) |
| **Governance** | Approval queue, financial validation, evaluation | Quality gate receipts, stage-hash chains, hookify enforcement |
| **State** | In-memory cycle state + memory store | SQLite ISCP + session handoff files + git payloads |

**Key Insight:** AOS is the **brain** (what to do, when to approve, which venture). TheAgency is the **muscle** (how to code, how to review, how to enforce quality). The integration question is: how does the brain command the muscle?

## Three Integration Models

### Model A: AOS as Orchestrator, TheAgency as Worker Harness

```
┌─────────────────────────────────────────────┐
│  AOS (Governance Layer)                      │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Planner  │→ │Dispatcher│→ │COO/CoS    │  │
│  └──────────┘  └──────────┘  └───────────┘  │
│       ↓              ↓              ↓        │
│  ┌─────────────────────────────────────────┐ │
│  │  Approval Queue  │  Financial Checks    │ │
│  └─────────────────────────────────────────┘ │
└──────────────────┬──────────────────────────┘
                   │ dispatches tasks
                   ↓
┌─────────────────────────────────────────────┐
│  TheAgency (Execution Layer)                 │
│  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ Captain  │→ │Tech-Lead │→ │ Reviewers │  │
│  └──────────┘  └──────────┘  └───────────┘  │
│       ↓              ↓              ↓        │
│  ┌─────────────────────────────────────────┐ │
│  │  Hookify  │  QGR Receipts  │  ISCP     │ │
│  └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

**How it works:**
- AOS dispatches tasks via `approval_queue` → TheAgency captain receives as ISCP dispatch
- Captain delegates to tech-lead → specialists (reviewers)
- Quality gates produce QGR receipts → AOS reads receipt status via API
- AOS approval gate blocks until QGR passes

**Pros:** Clean separation, TheAgency stays bash-native, minimal rewrite
**Cons:** Two runtimes to maintain, bash↔Python bridging overhead, TheAgency requires Claude Code CLI

### Model B: Steal Patterns, Rebuild Natively in AOS

```
┌─────────────────────────────────────────────────┐
│  AOS (Unified Runtime)                           │
│                                                   │
│  Existing:              New (from TheAgency):     │
│  ┌──────────────┐       ┌──────────────────────┐ │
│  │ LangGraph    │       │ Hookify Rules (Py)   │ │
│  │ StateGraph   │       │ QGR Receipts         │ │
│  │ Memory Store │       │ Session Handoff      │ │
│  │ Tool Gateway │       │ Agent Classes (YAML) │ │
│  │ Approval Q   │       │ Valueflow Pipeline   │ │
│  └──────────────┘       └──────────────────────┘ │
└─────────────────────────────────────────────────┘
```

**How it works:**
- Hookify → Python validator rules in `aos/validator.py` (already exists, extend it)
- ISCP → AOS event bus + SQLite persistence layer
- QGR receipts → Extend `aos/regression.py` with hash-chain verification
- Session handoff → Extend `aos/memory.py` with structured handoff files
- Agent classes → Extend harness bundle YAML schema with role definitions

**Pros:** Single runtime, no bash bridging, native Python, testable
**Cons:** Rewriting proven systems, losing TheAgency's edge cases, high effort

### Model C: Hybrid — AOS Governance + TheAgency Agent Protocol (Recommended)

```
┌─────────────────────────────────────────────────────┐
│  AOS (Orchestration + Governance)                    │
│                                                       │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ LangGraph   │  │ Approval Q   │  │ Financial  │  │
│  │ Cycle       │  │ (gates)      │  │ Validation │  │
│  └──────┬──────┘  └──────────────┘  └────────────┘  │
│         │                                             │
│         ↓                                             │
│  ┌─────────────────────────────────────────────────┐ │
│  │  Agent Worker Protocol (new)                    │ │
│  │  ┌───────────┐ ┌────────────┐ ┌──────────────┐ │ │
│  │  │ Role YAML │ │ Enforcement│ │ Receipt Chain│ │ │
│  │  │ (classes) │ │ (rules)    │ │ (QGR)        │ │ │
│  │  └───────────┘ └────────────┘ └──────────────┘ │ │
│  └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

**How it works:**
- AOS keeps its LangGraph cycle as the orchestration backbone
- TheAgency's **agent class model** becomes YAML role definitions in harness bundles
- TheAgency's **hookify rules** become declarative enforcement rules in AOS validator
- TheAgency's **QGR receipt chain** becomes a verification layer in `aos/regression.py`
- TheAgency's **session handoff** becomes structured state snapshots in AOS memory
- TheAgency's **ISCP dispatches** become events on AOS event bus with SQLite backing
- TheAgency's **Valueflow** maps to AOS orchestrate pipeline (spec→plan→implement→review→ship)

**Pros:** Best of both, incremental adoption, AOS stays Python-native, each piece is testable
**Cons:** Requires careful interface design, some concepts don't map 1:1

## Recommended: Model C — Detailed Design

### Phase 1: Agent Class System (Steal from TheAgency)

**What:** Define agent roles as structured YAML (not just prompts), with enforcement rules, tool permissions, and review responsibilities.

**TheAgency pattern:**
```markdown
# agency/agents/captain/agent.md
## Identity
I am the captain - the multi-faceted leader.
## Core Responsibilities
1. Onboarding & Guidance
2. Project Management
3. Infrastructure Management
```

**AOS adaptation — new schema `aos/schemas/agent_class.py`:**
```python
@dataclass(frozen=True)
class AgentClass:
    """Structured agent role definition with enforcement rules."""
    id: str                          # e.g. "captain", "tech-lead"
    name: str
    description: str
    responsibilities: list[str]      # what this role owns
    tool_permissions: list[str]      # which tools this role can use
    enforcement_rules: list[str]     # hookify-style rules for this role
    review_scope: list[str]          # what this role reviews
    escalation_target: str | None    # who to escalate to
    max_concurrent: int = 1          # how many instances can run
```

**Harness bundle extension:**
```yaml
# harness.yml additions
agent_classes:
  - id: captain
    name: Captain
    responsibilities:
      - project_management
      - infrastructure
      - onboarding
    tool_permissions:
      - git-safe-commit
      - dispatch-create
      - release
    enforcement_rules:
      - block-raw-git-push
      - block-raw-git-commit
    review_scope: ["all"]
    escalation_target: null
    max_concurrent: 1
```

**Files to create:**
- `aos/schemas/agent_class.py` — AgentClass dataclass
- `aos/loader.py` — add `load_agent_class()` function
- `aos/registry.py` — add `agent_classes` to HarnessBundle

### Phase 2: Enforcement Rules (Hookify → AOS Validator)

**What:** Declarative rules that block/warn/inform when agents violate patterns. TheAgency has 40 rules; we start with the 10 most impactful.

**TheAgency pattern:**
```markdown
# hookify.block-raw-push.md
decision: block
pattern: git push
message: "Use /sync or /release instead of raw git push"
```

**AOS adaptation — new file `aos/enforcement_rules.py`:**
```python
@dataclass(frozen=True)
class EnforcementRule:
    """Declarative rule that blocks/warns/informs on dangerous patterns."""
    id: str
    name: str
    decision: Literal["block", "warn", "info"]
    pattern: str           # regex pattern to match
    message: str           # guidance message
    scope: str = "all"     # "all", "agent_class:captain", "phase:implement"
    severity: str = "high" # "critical", "high", "medium", "low"

# Starter rules from TheAgency
ENFORCEMENT_RULES = [
    EnforcementRule(
        id="block-raw-git-commit",
        name="Block raw git commit",
        decision="block",
        pattern=r"^git\s+commit\b",
        message="Use /git-safe-commit or /iteration-complete instead",
        scope="all",
        severity="critical",
    ),
    EnforcementRule(
        id="block-raw-git-push",
        name="Block raw git push",
        decision="block",
        pattern=r"^git\s+push\b",
        message="Use /sync or /release instead",
        scope="all",
        severity="critical",
    ),
    EnforcementRule(
        id="block-cross-worktree-copy",
        name="Block cross-worktree cp",
        decision="block",
        pattern=r"^cp\s+.*worktree",
        message="Use cp-safe tool instead",
        scope="all",
        severity="high",
    ),
    EnforcementRule(
        id="warn-compound-bash",
        name="Warn on compound bash",
        decision="warn",
        pattern=r"&&|\|\||;",
        message="Compound bash detected — consider splitting into separate tool calls",
        scope="agent_class:specialist",
        severity="medium",
    ),
    EnforcementRule(
        id="block-force-push",
        name="Block force push",
        decision="block",
        pattern=r"git\s+push\s+.*--force",
        message="Force push is never allowed",
        scope="all",
        severity="critical",
    ),
    EnforcementRule(
        id="info-commit-without-test",
        name="Info: commit without test run",
        decision="info",
        pattern=r"^git-safe-commit",
        message="Ensure tests pass before committing",
        scope="phase:implement",
        severity="medium",
    ),
]
```

**Integration point:** `aos/hardening.py` already has `sanitize_path()` and shell validation. Add `check_enforcement_rules()` that runs before any tool execution.

**Files to create:**
- `aos/enforcement_rules.py` — rule definitions + checker
- `tests/test_enforcement_rules.py` — tests

### Phase 3: Quality Gate Receipts (QGR Chain)

**What:** Hash-chained receipts that prove a quality gate was run on the exact staged changes. Prevents "I reviewed it" without evidence.

**TheAgency pattern:**
```
stage_hash → QGR file → commit → PR
Five-hash chain links each artifact through the gate.
```

**AOS adaptation — extend `aos/regression.py`:**
```python
@dataclass(frozen=True)
class QualityGateReceipt:
    """Immutable receipt proving a QG was run on specific changes."""
    id: str
    stage_hash: str           # hash of the staged changes
    gate_type: str            # "iteration", "phase", "pre-pr"
    agent_id: str             # who ran the gate
    timestamp: str
    findings_count: int
    findings_fixed: int
    tests_passed: int
    tests_total: int
    receipt_hash: str         # hash of this receipt (chain link)
    previous_receipt_hash: str | None  # chain to previous receipt
    artifacts: list[str]      # files reviewed
    verdict: str              # "pass", "fail", "conditional"

class ReceiptChain:
    """Verify hash-chain integrity of QGR receipts."""

    def verify(self, receipts: list[QualityGateReceipt]) -> bool:
        """Verify the chain is unbroken from first to last."""
        ...

    def append(self, receipt: QualityGateReceipt) -> QualityGateReceipt:
        """Append a new receipt to the chain."""
        ...
```

**Integration point:** `git-safe-commit` equivalent in AOS checks for a valid receipt before allowing commits. The `evaluate.py` module already runs baseline evaluation — extend it to produce QGR receipts.

**Files to create:**
- `aos/receipts.py` — QualityGateReceipt + ReceiptChain
- `tests/test_receipts.py` — tests

### Phase 4: Session Handoff (Cross-Session State)

**What:** Structured handoff files that capture session state so work survives `/compact`, `/exit`, and multi-day gaps.

**TheAgency pattern:**
```
session-pause → writes handoff file (JSON)
session-pickup → reads handoff file, restores context
```

**AOS adaptation — extend `aos/memory.py`:**
```python
@dataclass(frozen=True)
class SessionHandoff:
    """Structured state snapshot for session continuity."""
    session_id: str
    agent_id: str
    venture_id: str
    harness_id: str
    cycle_id: str
    iteration: int
    phase: str                    # current pipeline phase
    pending_tasks: list[str]      # incomplete tasks
    completed_tasks: list[str]    # done this session
    context_summary: str          # compressed context
    approval_queue: list[str]     # pending approval IDs
    errors: list[str]             # unresolved errors
    created_at: str
    expires_at: str               # auto-expire after 7 days

class HandoffStore:
    """Persist and restore session handoffs."""

    def save(self, handoff: SessionHandoff) -> Path: ...
    def load(self, session_id: str) -> SessionHandoff | None: ...
    def list_pending(self, agent_id: str) -> list[SessionHandoff]: ...
    def cleanup_expired(self) -> int: ...
```

**Integration point:** `loop_control_node` in `graph.py` writes a handoff at each iteration boundary. On session start, `run_cycle_graph` checks for pending handoffs and resumes from the last iteration.

**Files to create:**
- `aos/handoff.py` — SessionHandoff + HandoffStore
- `tests/test_handoff.py` — tests

### Phase 5: Cross-Session Messaging (ISCP → Event Bus + SQLite)

**What:** Persistent message bus for agent-to-agent communication across sessions and worktrees.

**TheAgency pattern:**
```bash
dispatch create --to captain --subject "Review needed" --body "..."
flag --to tech-lead "Blocker: tests failing"
```

**AOS adaptation — extend `aos/event_bus.py`:**
```python
@dataclass(frozen=True)
class Dispatch:
    """Structured inter-session message with immutable payload."""
    id: str
    from_agent: str
    to_agent: str
    subject: str
    body: str                    # markdown payload
    dispatch_type: str           # "directive", "review", "seed", "escalation"
    status: str                  # "unread", "read", "resolved"
    created_at: str
    read_at: str | None = None
    resolved_at: str | None = None

@dataclass(frozen=True)
class Flag:
    """Quick-capture observation, agent-addressable."""
    id: str
    from_agent: str
    to_agent: str | None         # None = self-flag
    message: str
    status: str                  # "unread", "read", "processed"
    created_at: str

class ISCPStore:
    """SQLite-backed dispatch and flag storage."""

    def __init__(self, db_path: Path): ...
    def create_dispatch(self, dispatch: Dispatch) -> str: ...
    def create_flag(self, flag: Flag) -> str: ...
    def list_unread(self, agent_id: str) -> list[Dispatch | Flag]: ...
    def mark_read(self, item_id: str) -> None: ...
    def resolve_dispatch(self, dispatch_id: str) -> None: ...
```

**Integration point:** AOS event bus already exists. Add SQLite persistence layer. Each agent checks for unread dispatches at session start (via `SessionStart` hook). The `specialists_node` in `graph.py` checks for unread dispatches before executing.

**Files to create:**
- `aos/iscp.py` — Dispatch, Flag, ISCPStore (SQLite)
- `tests/test_iscp.py` — tests

### Phase 6: Valueflow Pipeline Alignment

**What:** Map TheAgency's 9-step Valueflow to AOS's orchestrate pipeline.

**TheAgency Valueflow:**
```
Idea → Seed → Research (MARFI) → Define (PVR) → Design (A&D) → Plan → Implement → Ship → Value
```

**AOS Orchestrate Pipeline:**
```
spec → autoplan → implement → reviewloop → ship
```

**Mapping:**
| TheAgency | AOS | Notes |
|-----------|-----|-------|
| Idea | (external) | User input |
| Seed | (external) | User provides one-liner or plan_path |
| Research (MARFI) | spec phase | Multi-agent research before planning |
| Define (PVR) | spec phase output | Product Vision & Requirements |
| Design (A&D) | spec phase output | Architecture & Design |
| Plan | autoplan phase | Phases × Iterations |
| Implement | implement phase | Agent execution |
| Ship | ship phase | Commit, PR, release |
| Value | (external) | Customer feedback loop |

**TheAgency additions to adopt:**
1. **Three-bucket disposition** for review findings: Disagree / Autonomous / Collaborative
2. **MAR (Multi-Agent Review)** at every transition boundary
3. **Pre-phase review** before starting next phase
4. **Sprint review** at phase completion

**Files to modify:**
- `aos/orchestrate/pipeline.py` — add MAR reviews at phase transitions
- `aos/evaluator.py` — add three-bucket disposition logic

## Implementation Priority

| Phase | Effort | Value | Dependencies |
|-------|--------|-------|-------------|
| 1. Agent Classes | Low | High | None |
| 2. Enforcement Rules | Low | High | None |
| 3. QGR Receipts | Medium | High | Phase 1 |
| 4. Session Handoff | Medium | Medium | None |
| 5. ISCP Messaging | High | High | None |
| 6. Valueflow Alignment | Medium | Medium | Phases 1-3 |

**Start with Phases 1+2** — they're low effort, high value, and don't require changing the core graph.

## What NOT to Steal

1. **Bash-native tooling** — AOS is Python; don't wrap bash tools in Python. Rewrite the logic natively.
2. **Claude Code CLI dependency** — TheAgency assumes Claude Code as the runtime. AOS uses its own LLM client.
3. **The full hookify rule set (40 rules)** — Most are Claude-Code-specific (cd-outside-worktree, enter-worktree-warn). Only steal the 5-10 that apply to AOS's execution model.
4. **Worktree discipline** — TheAgency's git worktree model is for multi-developer Claude Code instances. AOS doesn't need this yet.
5. **The "captain" role** — AOS already has Chief of Staff (AGT-EXEC-CHIEFOFSTAFF). Don't duplicate; merge the best responsibilities.

## Risks

1. **Process overhead** — TheAgency's strength is enforcement, but too many rules slow agents down. Start with 5 critical rules, not 40.
2. **Receipt chain complexity** — Five-hash chains are overkill for most use cases. Start with simple stage-hash verification.
3. **SQLite as message bus** — Fine for single-machine, problematic for distributed AOS. Consider event bus + file-based fallback.
4. **Scope creep** — This analysis identifies 6 phases. Resist doing all 6 at once. Ship Phases 1+2 first, validate, then iterate.

---

## CEO Review (Autoplan — Phase 1)

**Reviewed:** 2026-07-26 | **Voice:** Claude subagent (independent) | **Codex:** unavailable (usage limit)

### NOT in Scope

| Item | Rationale | Deferred to |
|------|-----------|-------------|
| TheAgency runtime dependency | AOS rebuilds patterns natively, no bash/CLI dependency | N/A (deliberate) |
| Full 40-rule hookify set | Only 5-10 apply to Python execution model | Phase 2+ expansion |
| Worktree discipline patterns | AOS doesn't need multi-developer git worktrees yet | Future if team grows |
| Captain role duplication | AOS already has Chief of Staff (AGT-EXEC-CHIEFOFSTAFF) | N/A (merged) |
| Distributed ISCP messaging | SQLite single-machine scope for now | Phase 5+ if distributed |
| Three-bucket disposition logic | Requires Phases 1-3 stable first | Phase 6 |
| MAR review ceremonies | Organizational change, not technical integration | Phase 6 |

### What Already Exists

| Sub-problem | Existing Code | Gap |
|-------------|--------------|-----|
| Agent role definitions | `HarnessBundle` in `registry.py`, `Agent` schema | No structured permissions/enforcement per role |
| Tool execution gating | `ToolGateway` in `tools.py` | No enforcement rules, no pattern matching |
| Path sanitization | `sanitize_path()` in `hardening.py` | Shell-level only, no agent-level rules |
| Memory/context persistence | `MemoryStore` in `memory.py` | No structured session handoff format |
| Event bus | `event_bus.py` exists | No SQLite persistence, no dispatch/flag CRUD |
| Quality evaluation | `evaluate.py` | No hash-chained receipts, no stage verification |
| Schema validation | `loader.py` + `aos/platform/*.schema.json` | No agent_class schema yet |

### Error & Rescue Registry

| Error Mode | Phase | Rescue Strategy | Owner |
|------------|-------|----------------|-------|
| Malformed AgentClass YAML | 1 | Pydantic v2 validation at load time, clear error message | Loader |
| Enforcement rule regex DoS (ReDoS) | 2 | Timeout on regex match (100ms), reject patterns with nested quantifiers | Hardening |
| Hash chain corruption | 3 | `ReceiptChain.verify()` detects breaks, quarantine broken chains | Receipts |
| Handoff file stale/corrupt | 4 | Expiry cleanup (7 days default), checksum validation | Handoff |
| SQLite lock contention | 5 | WAL mode + single-process constraint documented | ISCP |
| Schema migration breaks existing harnesses | 1 | Backwards-compatible loading: `agent_classes` optional, defaults to empty | Loader |

### Failure Modes Registry

| Failure Mode | Severity | Likelihood | Mitigation |
|-------------|----------|-----------|------------|
| TheAgency upstream format changes | High | Medium | Pin to commit hash, integration test surface |
| Enforcement rules block legitimate operations | High | Medium | Start with 5 rules, measure velocity impact, expand gradually |
| Hash chain verification false positives | Medium | Low | Stage-hash only (not 5-hash), clear error messages |
| SQLite concurrent writer corruption | Critical | Low (single-machine) | Document single-process constraint, WAL mode |
| Existing harnesses rejected by new schema | High | High | Backwards-compatible loading, optional agent_classes field |
| Session handoff loses context across /compact | Medium | Medium | HandoffStore designed for this, test with actual /compact cycles |

### Dream State Delta

**Where this plan leaves us vs 12-month ideal:**

| Capability | Now | After Integration | 12-Month Ideal |
|-----------|-----|-------------------|----------------|
| Agent role definitions | Prompt-only in YAML | Structured Pydantic models with permissions | Self-service role configuration UI |
| Tool enforcement | None (ToolGateway routes, no guards) | 5-10 regex rules block dangerous patterns | 20+ rules, ML-based anomaly detection |
| Quality receipts | None | Stage-hash verification per gate | Full audit trail with CI/CD integration |
| Session continuity | Memory store (3-layer) | + Structured handoff files | Auto-resume with LLM context restoration |
| Cross-agent messaging | Event bus (in-memory) | + SQLite-backed dispatch/flag | Distributed message bus with ordering guarantees |
| Pipeline alignment | spec→plan→implement→review→ship | + MAR reviews at transitions | Full Valueflow with three-bucket disposition |

### Completion Summary

| Dimension | Score | Notes |
|-----------|-------|-------|
| Premises | 3/5 | Brain/muscle metaphor unvalidated; YAML contract needs versioning |
| Scope | 3/5 | Missing rollback, migration, kill criteria, API contract |
| Risk | 3/5 | Top risks identified but mitigations are thin |
| Sequencing | 4/5 | Dependency ordering correct, but too linear |
| Value | 4/5 | Phases 1+2 are high ROI; later phases need validation first |
| Completeness | 2/5 | Missing: migration path, contract testing, success KPIs, ownership |
| **Overall** | **3.2/5** | **Solid architecture direction, needs engineering rigor before implementation** |

### CEO Consensus Table

```
CEO DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Premises sound?                   FLAG    N/A    N/A
  2. Scope complete?                   FLAG    N/A    N/A
  3. Risks mitigated?                  FLAG    N/A    N/A
  4. Sequencing correct?               OK      N/A    N/A
  5. Value justifies effort?           OK      N/A    N/A
  6. Missing from plan?                FLAG    N/A    N/A
═══════════════════════════════════════════════════════════════
Codex unavailable (usage limit). Single-voice review.
Findings flagged by Claude subagent are treated as critical.
```

<!-- AUTONOMOUS DECISION LOG -->
## Decision Audit Trail

| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|----------|
| 1 | CEO | AgentClass uses Pydantic v2 BaseModel, not frozen dataclass | Mechanical | P5 | Pydantic validates on construction, frozen dataclass doesn't catch malformed list[str] | No |
| 2 | CEO | Pin TheAgency to specific commit hash | Mechanical | P1 | Prevents silent breakage from upstream changes | No |
| 3 | CEO | Add rollback strategy per phase | Mechanical | P1 | Every phase needs a revert path | No |
| 4 | CEO | Insert acceptance gates between phases | Mechanical | P1 | Prevents bug propagation across phases | No |
| 5 | CEO | Scope Phase 5 SQLite to single-process | Mechanical | P5 | Pragmatic: single-machine scope documented, not pretend-distributed | No |
| 6 | CEO | Phase 4 uses ISCP persistence, no duplicate | Mechanical | P5 | DRY: handoff files should use the same message store | No |
| 7 | CEO | Reduce Phase 6 to mapping table + evaluator | Mechanical | P5 | YAGNI: full valueflow alignment is organizational, not technical | No |
| 8 | CEO | Add migration section with backwards compat | Mechanical | P1 | Existing harnesses must not break | No |
| 9 | CEO | Add measurable success KPIs per phase | Mechanical | P1 | Can't improve what you can't measure | No |

---

## Engineering Review (Autoplan — Phase 3)

**Reviewed:** 2026-07-26 | **Voice:** Claude subagent (independent) | **Codex:** unavailable

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    AOS Runtime (Python 3.12+)                   │
│                                                                 │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │ Registry │───▶│ HarnessBundle│───▶│ AgentClass (NEW)      │  │
│  │          │    │              │    │ ├─ permissions: list   │  │
│  └──────────┘    └──────────────┘    │ ├─ enforcement: list  │  │
│                                      │ └─ escalation: str    │  │
│  ┌──────────┐    ┌──────────────┐    └───────────┬───────────┘  │
│  │  Loader  │───▶│  Pydantic v2 │                │              │
│  │          │    │  Validation  │                │              │
│  └──────────┘    └──────────────┘                ▼              │
│                                      ┌───────────────────────┐  │
│  ┌──────────┐    ┌──────────────┐    │ EnforcementChecker    │  │
│  │ ToolGate │◀──│ check_rules()│◀───│ (compile-time regex)  │  │
│  │ .call()  │    │              │    └───────────────────────┘  │
│  └────┬─────┘    └──────────────┘                              │
│       │                                                         │
│       ▼                                                         │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────────────┐  │
│  │ ToolExec │───▶│ Graph Nodes  │───▶│ ReceiptChain (NEW)    │  │
│  │          │    │ (LangGraph)  │    │ ├─ append() [LOCKED]  │  │
│  └──────────┘    └──────────────┘    │ ├─ verify() [LOCKED]  │  │
│                                      │ └─ genesis_hash       │  │
│  ┌──────────┐    ┌──────────────┐    └───────────────────────┘  │
│  │ EventBus │───▶│ ISCPStore    │                              │
│  │ (lifecycle)   │ (SQLite)     │    ┌───────────────────────┐  │
│  └──────────┘    │ ├─ dispatch  │    │ SessionHandoff (NEW)  │  │
│                  │ ├─ flag      │    │ ├─ context_summary    │  │
│                  │ └─ list_unread│   │ ├─ expires_at         │  │
│                  └──────────────┘    │ └─ max 10K chars      │  │
│                                      └───────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Test Diagram

```
Phase 1 (AgentClass):
  test_agent_class_load ──────▶ test_agent_class_invalid_yaml
  test_harness_bundle_extend ─▶ test_registry_agent_class_lookup
  test_loader_schema_validate ─▶ test_backwards_compat_no_agent_classes

Phase 2 (Enforcement):
  test_enforcement_compile ───▶ test_enforcement_block_action
  test_enforcement_warn_only ─▶ test_enforcement_scope_agent_class
  test_enforcement_bypass_spoof ─▶ test_regex_rejection (ReDoS)
  test_toolgateway_enforcement_integration

Phase 3 (Receipts):
  test_receipt_stage_hash ────▶ test_receipt_chain_verify
  test_receipt_chain_concurrent_append [THREAD]
  test_receipt_chain_genesis_anchor
  test_receipt_prune_old

Phase 4 (Handoff):
  test_handoff_save_restore ──▶ test_handoff_expiry
  test_handoff_max_size_cap ──▶ test_handoff_cleanup_at_startup

Phase 5 (ISCP):
  test_iscp_create_dispatch ──▶ test_iscp_list_unread
  test_iscp_sql_injection ────▶ test_iscp_concurrent_writes [THREAD]
  test_iscp_wal_mode

Phase 6 (Valueflow):
  test_valueflow_mapping_table ─▶ test_mar_review_gate
```

### Test Plan

| Phase | Test | Type | Priority |
|-------|------|------|----------|
| 1 | AgentClass loads from YAML, validates fields | unit | P0 |
| 1 | HarnessBundle.agent_classes populated | unit | P0 |
| 1 | Backwards compat: missing agent_classes defaults to {} | unit | P0 |
| 2 | EnforcementRule regex compiles at load time | unit | P0 |
| 2 | check_enforcement_rules blocks matching action | unit | P0 |
| 2 | check_enforcement_rules allows non-matching action | unit | P0 |
| 2 | ReDoS pattern rejected at compile time | unit | P0 |
| 2 | Enforcement scope matches agent_class correctly | unit | P1 |
| 2 | ToolGateway.call() invokes enforcement check | integration | P0 |
| 3 | ReceiptChain.append() produces valid hash | unit | P0 |
| 3 | ReceiptChain.verify() detects broken chain | unit | P0 |
| 3 | ReceiptChain concurrent append (10 threads) | concurrency | P0 |
| 3 | ReceiptChain genesis anchor validation | unit | P1 |
| 3 | Receipt pruning after retention period | unit | P2 |
| 4 | SessionHandoff save + restore roundtrip | unit | P0 |
| 4 | HandoffStore.cleanup_expired removes old files | unit | P0 |
| 4 | Handoff context_summary capped at 10K chars | unit | P1 |
| 5 | ISCPStore create_dispatch + list_unread | unit | P0 |
| 5 | ISCPStore parameterized queries (injection test) | security | P0 |
| 5 | ISCPStore concurrent writes (10 threads, WAL) | concurrency | P0 |
| 5 | ISCPStore idx_dispatches_unread index exists | unit | P1 |
| 6 | Valueflow mapping table covers all phases | unit | P1 |
| 6 | MAR review gate triggers at phase transitions | integration | P2 |

### NOT in Scope (Engineering)

| Item | Rationale | Deferred to |
|------|-----------|-------------|
| Full 40-rule hookify enforcement set | 5 rules for Phase 2, expand after validation | Phase 2+ |
| Merkle-tree receipt chain | Linear chain sufficient for serial execution; redesign if parallel needed | Phase 3 redesign |
| EventBus → ISCPStore integration | EventBus for lifecycle, ISCPStore for messaging — clear boundary | Phase 5 |
| Phase scope in CycleState | No `current_phase` field exists; scoping to "all" for starter rules | Future |
| ReceiptChain genesis hash signing | Chain consistency sufficient for v1; authenticity needs signing | Phase 3+ |

### What Already Exists (Engineering)

| Component | Code | Integration Point |
|-----------|------|-------------------|
| ToolGateway.call() | `aos/tools.py` | Enforcement checker wired here (Finding A) |
| RateLimiter/ConnectionLimiter | `aos/hardening.py` | Threading.Lock pattern for ReceiptChain |
| HarnessBundle | `aos/registry.py` | Add `agent_classes: dict` field |
| SCHEMA_MAP | `aos/loader.py` | Add `agent_class` entry |
| _load_schema() | `aos/loader.py` | Compile regex at load time |
| _run_parallel() | `aos/graph.py` | Concurrent specialist execution context |

### Failure Modes Registry (Engineering)

| Failure Mode | Severity | Finding | Fix |
|-------------|----------|---------|-----|
| Enforcement checker never called | CRITICAL | A | Wire into ToolGateway.call() between rate-limit and dispatch |
| Regex crashes during tool execution | CRITICAL | F | Compile all patterns at load time in loader |
| ReDoS blocks tool gateway thread | CRITICAL | N | Compile-time nested quantifier rejection + runtime timeout |
| Hash chain meaningless under parallelism | CRITICAL | R | Serialize receipt collection or redesign as Merkle tree |
| YAML regex double-escape silently broken | HIGH | G | Document YAML escaping rules, add compile-and-log step |
| ReceiptChain race condition | HIGH | C | Add threading.Lock (follow RateLimiter pattern) |
| EventBus/ISCPStore delivery gap | HIGH | D | Clear boundary: EventBus=lifecycle, ISCPStore=messaging |
| Handoff files accumulate forever | HIGH | E | Call cleanup_expired() at run_cycle_graph startup |
| ISCPStore SQL injection | HIGH | O | Mandate parameterized queries, add injection test |
| ISCPStore cross-thread access crash | HIGH | L | WAL mode + check_same_thread=False |
| AgentClass.tool_permissions inert | HIGH | B | Drop tool_permissions from AgentClass, let tools.yml be source of truth |

### Completion Summary (Engineering)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Architecture | 3/5 | 4 CRITICAL wiring gaps; component design sound but not connected |
| Edge cases | 2/5 | ReDoS, YAML escaping, concurrency all unaddressed |
| Test coverage | 2/5 | No concurrency tests, no injection tests, no ReDoS regression |
| Security | 2/5 | SQL injection risk, ReDoS attack surface, class spoofing |
| Hidden complexity | 2/5 | Hash chain ordering, dual messaging systems, unbounded deserialization |
| Performance | 3/5 | Acceptable for 5 rules, degrades at scale; index missing |
| **Overall** | **2.3/5** | **Structural issues must be fixed before implementation** |

### Engineering Consensus Table

```
ENG DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. Architecture sound?               FLAG    N/A    FLAG (4 CRITICAL)
  2. Edge cases covered?               FLAG    N/A    FLAG (ReDoS, YAML)
  3. Tests sufficient?                 FLAG    N/A    FLAG (no concurrency)
  4. Security acceptable?              FLAG    N/A    FLAG (injection, ReDoS)
  5. Complexity manageable?            FLAG    N/A    FLAG (hash chain)
  6. Performance acceptable?           OK      N/A    OK (for 5 rules)
═══════════════════════════════════════════════════════════════
Codex unavailable. Single-voice review.
4 CRITICAL findings require fixes before Phase 1 implementation.
```

<!-- ENGINEERING DECISION AUDIT TRAIL CONTINUED -->
| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|----------|
| 10 | Eng | Wire check_enforcement_rules() into ToolGateway.call() | Mechanical | P1 | Module is orphaned without a caller | No |
| 11 | Eng | Drop tool_permissions from AgentClass | Mechanical | P5 | DRY: tools.yml is single source of truth | No |
| 12 | Eng | Add threading.Lock to ReceiptChain | Mechanical | P1 | Concurrent specialists cause race condition | No |
| 13 | Eng | EventBus=lifecycle, ISCPStore=messaging (clear boundary) | Taste | P5 | Two systems need distinct roles, not duplication | No |
| 14 | Eng | Call cleanup_expired() at run_cycle_graph startup | Mechanical | P1 | Handoff files accumulate without a cleanup owner | No |
| 15 | Eng | Compile all regex at load time, reject invalid patterns | Mechanical | P1 | Regex crashes during tool execution = production outage | No |
| 16 | Eng | Document YAML regex escaping rules + compile-and-log | Mechanical | P1 | Python raw-string syntax silently breaks in YAML | No |
| 17 | Eng | Drop phase scope from enforcement rules (Phase 2) | Mechanical | P5 | No current_phase field in CycleState; "all" is sufficient | No |
| 18 | Eng | Mandate parameterized SQL queries in ISCPStore | Mechanical | P1 | SQL injection from agent-generated markdown content | No |
| 19 | Eng | Serialize receipt collection OR redesign as Merkle tree | Taste | P5 | Linear hash chain is meaningless under parallel execution | **YES** |
| 20 | Eng | Add genesis anchor to ReceiptChain | Taste | P5 | Chain provability without signing is limited | **YES** |

---

## DX Review (Autoplan — Phase 3.5)

**Reviewed:** 2026-07-26 | **Voice:** Claude subagent (independent) | **Codex:** unavailable

### DX Findings Summary

| # | Finding | Severity | Module | Fix |
|---|---------|----------|--------|-----|
| 1 | Code examples use frozen dataclass, not Pydantic BaseModel | CRITICAL | All | Update all examples to BaseModel |
| 2 | Missing JSON Schema files for platform validation | HIGH | All | Create `aos/platform/*.schema.json` for each new type |
| 3 | No ID prefix convention for new manifest types | HIGH | All | Define `ACL-`, `ENR-`, `RCP-`, `SHO-` prefixes |
| 4 | ReceiptChain.verify() returns bool, no diagnostics | HIGH | Phase 3 | Return `VerificationResult` with broken_at, expected/actual hash |
| 5 | YAML regex escaping is a DX trap | HIGH | Phase 2 | Document escaping rules + compile-and-log at load time |
| 6 | EnforcementRule scope format undocumented | MEDIUM | Phase 2 | Define `ScopeType` enum + `ParsedScope` dataclass |
| 7 | No logging strategy for enforcement checks | MEDIUM | Phase 2 | Define log event structure for block/warn/info |
| 8 | ISCPStore missing SQLite initialization details | MEDIUM | Phase 5 | Show full `__init__` with WAL, busy_timeout, context manager |
| 9 | HandoffStore.save() returns undocumented Path | MEDIUM | Phase 4 | Define storage path + naming convention |
| 10 | context_summary max 10K not enforced | MEDIUM | Phase 4 | Add `Field(max_length=10000)` or validator |
| 11 | ReceiptChain threading.Lock not in code example | MEDIUM | Phase 3 | Show lock in example, reference RateLimiter pattern |
| 12 | No migration strategy for existing harnesses | HIGH | Phase 1 | Document HarnessBundle change with default_factory |
| 13 | No test fixture patterns | MEDIUM | All | Add factory functions per module |
| 14 | Conflating manifest loading with runtime loading | MEDIUM | Phases 3-5 | Clarify: YAML manifests vs runtime JSON/SQLite |
| 15 | EnforcementDecision uses Literal instead of Enum | MEDIUM | Phase 2 | Use `str, Enum` to match codebase pattern |

### DX Scorecard

| Dimension | Score | Notes |
|-----------|-------|-------|
| API Consistency | 2/5 | Code examples contradict codebase patterns (dataclass vs Pydantic) |
| Error Diagnostics | 2/5 | verify() returns bool, no structured error context |
| Configuration UX | 3/5 | YAML escaping trap, scope format undocumented |
| Testing DX | 3/5 | Test plan exists but no fixture patterns |
| Debugging Experience | 2/5 | No logging strategy, no diagnostic returns |
| Migration Path | 3/5 | Backward compat mentioned but not concrete |
| **Overall** | **2.5/5** | **Plan examples need alignment pass before implementation** |

### DX Consensus Table

```
DX DUAL VOICES — CONSENSUS TABLE:
═══════════════════════════════════════════════════════════════
  Dimension                           Claude  Codex  Consensus
  ──────────────────────────────────── ─────── ─────── ─────────
  1. APIs intuitive?                   FLAG    N/A    FLAG (dataclass mismatch)
  2. Error messages helpful?           FLAG    N/A    FLAG (bool return)
  3. Config clear?                     FLAG    N/A    FLAG (YAML escaping)
  4. Tests easy to write?              OK      N/A    OK (fixtures needed)
  5. Debugging at 2am?                 FLAG    N/A    FLAG (no logging)
  6. Migration safe?                   OK      N/A    OK (default_factory)
═══════════════════════════════════════════════════════════════
Codex unavailable. Single-voice review.
All DX findings are mechanical fixes — no taste decisions.
```

<!-- DX DECISION AUDIT TRAIL CONTINUED -->
| # | Phase | Decision | Classification | Principle | Rationale | Rejected |
|---|-------|----------|-----------|-----------|----------|----------|
| 21 | DX | Update all code examples to Pydantic BaseModel | Mechanical | P5 | Codebase uses BaseModel exclusively; examples must match | No |
| 22 | DX | Create JSON Schema files for each new manifest type | Mechanical | P1 | Loader validation requires schema files | No |
| 23 | DX | Define ID prefixes: ACL-, ENR-, RCP-, SHO- | Mechanical | P5 | detect_manifest_type() needs prefixes for auto-discovery | No |
| 24 | DX | Return VerificationResult from ReceiptChain.verify() | Mechanical | P1 | Bool return gives zero diagnostic context at 2am | No |
| 25 | DX | Document YAML regex escaping + compile-and-log | Mechanical | P1 | Python raw strings don't work in YAML | No |
| 26 | DX | Define ScopeType enum for enforcement rule scope | Mechanical | P5 | Undocumented format = developer confusion | No |
| 27 | DX | Add structured logging for enforcement checks | Mechanical | P1 | No logging = no debugging path | No |
| 28 | DX | Show full ISCPStore.__init__ with WAL setup | Mechanical | P5 | Developer will copy incomplete example, hit thread errors | No |
| 29 | DX | Define HandoffStore storage path + naming convention | Mechanical | P5 | Undocumented return value = ambiguity | No |
| 30 | DX | Enforce context_summary max 10K via Field/validator | Mechanical | P1 | Unbounded LLM output = OOM risk | No |
| 31 | DX | Show threading.Lock in ReceiptChain code example | Mechanical | P1 | Lockless example shipped = race condition | No |
| 32 | DX | Document HarnessBundle migration with default_factory | Mechanical | P5 | Backward compat must be explicit, not assumed | No |
| 33 | DX | Add test fixture factory functions per module | Mechanical | P5 | Test plan without fixtures = developer friction | No |
| 34 | DX | Separate manifest types from runtime types in loader | Mechanical | P5 | YAML manifests ≠ JSON/SQLite runtime data | No |
| 35 | DX | Use EnforcementDecision enum instead of Literal | Mechanical | P5 | Codebase uses str, Enum for all categorical fields | No |
