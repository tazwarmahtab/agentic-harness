# Registry.resolve_agent() Contract

**Version:** 1.0  
**Module:** `aos.registry.Registry`  
**Purpose:** Cross-harness agent resolution for dispatcher and specialist fan-out

---

## Function Signature

```python
def resolve_agent(self, agent_id: str) -> tuple[Agent, HarnessBundle] | None:
    """
    Resolve an agent ID to its Agent object and the bundle it belongs to.

    Args:
        agent_id: Full agent ID (e.g., "AGT-NETSO-ATLAS", "AGT-EXEC-CFO")

    Returns:
        Tuple of (Agent, HarnessBundle) if found, None otherwise.

    Search Order:
        1. Planner in each bundle
        2. Dispatcher in each bundle
        3. Specialists in each bundle (by agent_id key)

    Note: Returns first match. Agent IDs must be globally unique across all loaded harnesses.
    """
```

---

## Usage in Graph Nodes

### Dispatcher Node (`delegate_node`)
```python
def delegate_node(state: CycleState) -> dict:
    config = state.get("config", {})
    registry = config.get("registry")
    
    # Build available agents including cross-harness
    available_agents = []
    for bundle in registry.harnesses.values():
        if bundle.dispatcher:
            available_agents.append(bundle.dispatcher)
        if bundle.planner:
            available_agents.append(bundle.planner)
        available_agents.extend(bundle.specialists.values())
    
    # Or use resolve_agent for specific routing:
    result = registry.resolve_agent("AGT-NETSO-MINERVA")
    if result:
        agent, bundle = result
        # Use agent.mission, agent.capabilities, agent.allowed_tools, etc.
```

### Specialists Node (`specialists_node`)
```python
def specialists_node(state: CycleState) -> dict:
    config = state.get("config", {})
    registry = config.get("registry")
    
    # Resolve assigned specialists from any harness
    for assignment in state.get("assignments", []):
        agent_id = assignment["agent"]
        result = registry.resolve_agent(agent_id)
        if not result:
            logger.warning(f"Agent {agent_id} not found in any harness")
            continue
        
        agent, bundle = result
        # Run agent with its harness context
        output = await run_agent(agent, bundle, state)
```

---

## Fallback Routing

When dispatcher JSON output has no `assignments`, `_fallback_routing()` extracts `AGT-XXX-YYY` patterns from raw text:

```python
def _fallback_routing(raw_text: str, routing_table: dict) -> dict:
    """
    Extracts agent mentions from free-form dispatcher output.
    Matches against routing_table (internal + cross-harness routes).
    Builds synthetic assignments for specialist_node to execute.
    """
    # Regex: AGT-[A-Z]+-[0-9A-Z]+
    matches = re.findall(r'AGT-[A-Z]+-[0-9A-Z]+', raw_text)
    for agent_id in matches:
        result = registry.resolve_agent(agent_id)
        if result:
            agent, bundle = result
            # Create assignment...
```

---

## Return Values

| Scenario | Return |
|----------|--------|
| Agent found | `(Agent, HarnessBundle)` |
| Agent not found | `None` |
| Multiple matches (should not happen) | First match (global uniqueness required) |

---

## HarnessBundle Structure

```python
@dataclass
class HarnessBundle:
    harness: Harness
    planner: Agent | None = None
    dispatcher: Agent | None = None
    specialists: dict[str, Agent] = field(default_factory=dict)
    teams: dict[str, AgentTeam] = field(default_factory=dict)
    memory: Memory | None = None
    tools: ToolRegistry | None = None
    approvals: PolicyCollection | None = None
    evaluation: Evaluation | None = None
    sops: dict[str, SOP] = field(default_factory=dict)
```

---

## Cross-Harness Dispatch Rules

1. **Global Uniqueness**: Agent IDs must be unique across ALL loaded harnesses (including `external/`).
2. **Bundle Context**: The returned `HarnessBundle` provides access to the agent's memory, tools, approvals, and evaluation config.
3. **Permission Inheritance**: Agent permissions (`allowed_memory`, `allowed_tools`) are enforced at runtime by `ToolGateway` and `MemoryStore`.
4. **Isolation**: Agents cannot directly access other bundles' memory unless explicitly granted via `allowed_memory.read`.

---

## Example: Loading External Harness

```python
# In aos/graph.py build_graph() or CLI
registry = load_registry(
    venture_path="aos/ventures/netso",
    harness_dirs=[
        "aos/harnesses/executive",
        "aos/harnesses/sales",
        "aos/harnesses/external/netso_legacy",  # Auto-discovered
    ]
)
```

---

## Testing Contract

```python
def test_resolve_agent_cross_harness():
    registry = load_test_registry()
    
    # Internal agent
    result = registry.resolve_agent("AGT-EXEC-CFO")
    assert result is not None
    agent, bundle = result
    assert agent.id == "AGT-EXEC-CFO"
    assert bundle.harness.id == "HAR-EXEC-001"
    
    # External agent
    result = registry.resolve_agent("AGT-NETSO-MINERVA")
    assert result is not None
    agent, bundle = result
    assert agent.id == "AGT-NETSO-MINERVA"
    assert bundle.harness.id == "HAR-NETSO-001"
    
    # Non-existent
    result = registry.resolve_agent("AGT-UNKNOWN-999")
    assert result is None
```

---

## Integration Points

| Component | Uses `resolve_agent()` |
|-----------|------------------------|
| `delegate_node` | Building available agents list + specific routing |
| `specialists_node` | Resolving assigned specialists |
| `_fallback_routing` | Regex extraction → resolution |
| CLI `aos run` | Status display, dry-run validation |
| Dashboard API | Agent registry endpoint |

---

*End of Contract*