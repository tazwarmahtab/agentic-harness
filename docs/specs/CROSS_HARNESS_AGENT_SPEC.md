# Cross-Harness Agent Manifest Specification

**Version:** 1.0  
**Status:** Draft  
**Purpose:** Define the contract for external agents (e.g., re-homed Netso personas like LILTAZ, ATLAS, MINERVA, SHIELD, LENS, COUNCIL) to plug into AOS harnesses via `Registry.resolve_agent()`.

---

## 1. Manifest Location Convention

```
aos/harnesses/
  external/
    {harness_id}/
      harness.yml          # Harness manifest (required)
      planner.yml          # Planner agent (optional - external harnesses typically only provide specialists)
      dispatcher.yml       # Dispatcher agent (optional)
      specialists/
        {agent_id}.yml     # One file per specialist agent (required)
      memory.yml           # Memory config (optional)
      tools.yml            # Tool registry (optional)
      approvals.yml        # Approval config (optional)
      evaluation.yml       # Evaluation config (optional)
      sops/
        *.md               # SOPs (optional)
```

**Example for Netso Legacy agents:**
```
aos/harnesses/external/netso_legacy/
  harness.yml
  specialists/
    agt-netso-liltaz.yml   # Planner/Dispatcher core
    agt-netso-atlas.yml    # COO specialist
    agt-netso-minerva.yml  # CFO specialist
    agt-netso-shield.yml   # Legal + Risk specialist
    agt-netso-lens.yml     # Performance analyst
    agt-netso-council.yml  # Deliberation escalation tier
```

---

## 2. Required Agent Manifest Fields (for External Agents)

External agents **must** include these fields in their `.yml` manifest:

| Field | Required | Description |
|-------|----------|-------------|
| `id` | ✅ | Unique ID matching pattern `^AGT-[A-Z]+-[0-9A-Z]+$` (e.g., `AGT-NETSO-ATLAS`) |
| `name` | ✅ | Human-readable name |
| `harness` | ✅ | Parent harness ID (e.g., `HAR-NETSO-LEGACY-001`) |
| `version` | ✅ | Semantic version (default: `1.0.0`) |
| `status` | ✅ | One of: `draft`, `deployed`, `production`, `idle`, `blocked`, `retired` |
| `criticality` | ✅ | `low`, `medium`, `high`, `critical` — determines model tier routing |
| `mission` | ✅ | Exactly one sentence describing the agent's purpose |
| `capabilities` | ✅ | List of capability strings (must match tool capabilities in `tools.yml`) |
| `allowed_memory` | ✅ | Object with `read`, `write`, `cannot_read` arrays of memory domain refs |
| `allowed_tools` | ✅ | List of `{capability, permission}` objects |

### 2.1 Cross-Harness Specific Fields (Recommended)

| Field | Required | Description |
|-------|----------|-------------|
| `source_persona` | ✅ | Original persona name (e.g., `ATLAS`, `MINERVA`) for traceability |
| `persona_source` | ✅ | Path to original markdown persona file (e.g., `Netso_HQ/ai_system/System/agents/atlas-coo.md`) |
| `note` | Optional | Free-text notes about re-homing, special behavior, or migration context |

### 2.2 Interface Fields for Cross-Harness Dispatch

| Field | Purpose |
|-------|---------|
| `inputs` | Defines expected input artifacts (names, types, required flags) — dispatcher uses this to validate handoffs |
| `outputs` | Defines produced artifacts — enables downstream routing and artifact lineage |
| `handoff_format` | (Optional) Structured format for cross-harness task handoffs — enables dispatcher to route tasks without internal knowledge |
| `routing_table` | (Optional) Maps capability names to target agent IDs — allows external agents to declare their own routing preferences |

---

## 3. Minimal Valid External Agent Manifest

```yaml
# aos/harnesses/external/netso_legacy/specialists/agt-netso-atlas.yml
id: AGT-NETSO-ATLAS
name: ATLAS — COO Specialist
harness: HAR-NETSO-LEGACY-001
version: 1.0.0
status: production
criticality: high
source_persona: ATLAS
persona_source: "Netso_HQ/ai_system/System/agents/atlas-coo.md"
note: "Re-homed from Netso ai_system. Owns DASHBOARD.md live state and BLOCKERS.md."

mission: >
  Own execution velocity across Netso operations: track progress, identify
  bottlenecks, enforce deadlines, and ensure the DASHBOARD.md reflects
  live reality after every action.

capabilities:
  - execution_tracking
  - deadline_management
  - bottleneck_identification
  - dashboard_maintenance
  - blocker_resolution_tracking
  - weekly_prioritization
  - session_protocol_enforcement

inputs:
  - { name: dashboard_current, type: markdown, required: true }
  - { name: blockers, type: markdown, required: true }
  - { name: weekly_plan, type: markdown, required: true }
  - { name: task_assignments, type: list, required: false }

outputs:
  - { name: dashboard_update, type: markdown, becomes_artifact: true, artifact_type: dashboard }
  - { name: blocker_update, type: markdown, becomes_artifact: true, artifact_type: blockers }
  - { name: session_shutdown_log, type: markdown, becomes_artifact: true, artifact_type: session_log }

allowed_memory:
  read: [dashboard, weekly_plan, backlog, blockers, agents_registry, task_router, latest_session, lessons]
  write: [dashboard, blockers, handoffs]
  cannot_read: [founder_personal_notes, cap_table, raw_financial_models]

allowed_tools:
  - { capability: read_dashboard, permission: read }
  - { capability: write_dashboard, permission: write }
  - { capability: write_blockers, permission: write }
  - { capability: read_handoffs, permission: read }
  - { capability: write_handoff, permission: write }
  - { capability: read_crm, permission: read }
  - { capability: read_calendar, permission: read }

# Cross-harness interface (optional but recommended)
handoff_format:
  type: structured
  schema:
    task_id: string
    priority: [P0, P1, P2, P3]
    deadline: iso8601_datetime
    context_refs: [string]
    success_criteria: string

routing_table:
  execution_tracking: AGT-NETSO-ATLAS
  deadline_management: AGT-NETSO-ATLAS
  financial_modeling: AGT-NETSO-MINERVA
  legal_review: AGT-NETSO-SHIELD
```

---

## 4. Harness Manifest for External Bundle

External harnesses must provide a minimal `harness.yml`:

```yaml
# aos/harnesses/external/netso_legacy/harness.yml
id: HAR-NETSO-LEGACY-001
name: Netso Legacy Agent Bundle
venture: VEN-NETSO-001
version: 1.0.0
status: production
criticality: high

mission: >
  Provide re-homed Netso AI personas (LILTAZ, ATLAS, MINERVA, SHIELD, LENS, COUNCIL)
  as cross-harness specialists dispatchable by the Executive Harness.

scope:
  in_scope:
    - Specialist domain execution (ops, finance, legal, performance, deliberation)
    - Artifact production per defined output contracts
    - Memory read/write per allowed_memory declarations
  out_of_scope:
    - Workflow orchestration (owned by Executive Harness)
    - Approval gate management (owned by Executive Harness)
    - Tool gateway mechanics (owned by platform)

kpis:
  - name: Cross-harness task completion rate
    target: ">95%"
    frequency: weekly
  - name: Handoff format compliance
    target: "100%"
    frequency: realtime

inputs:
  - { source: executive_dispatch, items: [task_id, priority, context, deadline] }

outputs:
  - name: Specialist Output
    type: artifact
    artifact_type: specialist_output
    frequency: realtime
    description: "Structured output per agent's outputs definition"

components:
  specialists_dir: specialists/
  memory: memory.yml
  tools: tools.yml
  evaluation: evaluation.yml

execution_cycle:
  name: On-Demand Specialist Execution
  trigger: dispatch_event
  steps:
    - receive_handoff: dispatcher
    - validate_inputs: runtime
    - run_agent: specialist
    - produce_outputs: specialist
    - write_memory: specialist
    - return_handoff: dispatcher
```

---

## 5. Loading External Harnesses

The CLI `python -m aos validate` and `python -m aos run` automatically discover harnesses under `aos/harnesses/`. External harnesses are loaded identically to internal ones.

```python
# In aos/graph.py — cross-harness dispatch uses:
result = registry.resolve_agent("AGT-NETSO-ATLAS")
if result:
    agent, bundle = result
    # agent is the Agent object, bundle is the HarnessBundle
```

---

## 6. Validation Checklist for External Agents

Before deploying an external agent, verify:

- [ ] Manifest passes `python -m aos validate --harness netso_legacy`
- [ ] `id` follows `AGT-{HARNESS_PREFIX}-{AGENT_NAME}` convention
- [ ] `harness` field matches parent harness `id`
- [ ] `criticality` set appropriately (determines model tier: critical/high → paid Sonnet; medium/low → free tier)
- [ ] All `capabilities` have corresponding tool definitions in harness `tools.yml`
- [ ] `allowed_memory.read/write` domains exist in harness `memory.yml`
- [ ] `allowed_tools` capabilities exist and permissions match
- [ ] `inputs` / `outputs` define artifact types that match downstream consumers
- [ ] `source_persona` and `persona_source` documented for auditability
- [ ] `handoff_format` (if provided) matches Executive Harness dispatcher expectations

---

## 7. Re-Homing Mapping (Netso Legacy → AOS)

| Netso Persona | AOS Agent ID | Harness | Role |
|---------------|--------------|---------|------|
| LILTAZ | AGT-NETSO-LILTAZ | netso_legacy | Planner + Dispatcher Core |
| ATLAS | AGT-NETSO-ATLAS | netso_legacy | COO Specialist |
| MINERVA | AGT-NETSO-MINERVA | netso_legacy | CFO Specialist |
| SHIELD | AGT-NETSO-SHIELD | netso_legacy | Legal + Risk Specialist |
| LENS | AGT-NETSO-LENS | netso_legacy | Performance Analyst |
| COUNCIL | AGT-NETSO-COUNCIL | netso_legacy | Deliberation Escalation Tier |
| *(new)* | AGT-EXEC-CHIEFOFSTAFF | executive | Chief of Staff (AOS-native) |

---

## 8. Registry.resolve_agent() Contract

```python
def resolve_agent(self, agent_id: str) -> tuple[Agent, HarnessBundle] | None:
    """
    Resolve an agent ID to its Agent object and the bundle it belongs to.

    Args:
        agent_id: Full agent ID (e.g., "AGT-NETSO-ATLAS")

    Returns:
        Tuple of (Agent, HarnessBundle) if found, None otherwise.

    Search Order:
        1. Planner in each bundle
        2. Dispatcher in each bundle
        3. Specialists in each bundle

    Note: Returns first match. Agent IDs must be globally unique across all harnesses.
    """
```

**Usage in Graph Nodes:**
```python
# In dispatcher_node or specialists_node:
result = config.registry.resolve_agent(agent_id)
if result:
    agent, bundle = result
    # Use agent.allowed_memory, agent.allowed_tools, agent.mission, etc.
```

---

## 9. Version Compatibility

| Manifest Version | AOS Version | Notes |
|------------------|-------------|-------|
| 1.0.0 | 0.1.0+ | Initial cross-harness spec |

**Breaking Changes:** Increment major version if:
- Required fields added/removed
- `allowed_memory` / `allowed_tools` schema changed
- `handoff_format` schema changed

---

*End of Cross-Harness Agent Manifest Specification*