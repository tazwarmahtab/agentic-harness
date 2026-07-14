<!-- /autoplan restore point: /Users/tazwarmahtab/.gstack/projects/tazwarmahtab-agentic-harness/main-autoplan-restore-20260713-213504.md -->
# Autonomous Milestone Harness for AOS

## Executive Summary
This document outlines the design for integrating a GSD-style `autonomous` workflow into the Agentic Operating System (AOS). The goal is to enable AOS to execute multi-phase development milestones autonomously, iterating through discuss, plan, and execute steps for each phase, while tracking state and pausing only for critical human approvals. This will leverage AOS's existing LangGraph-based orchestration capabilities and Python ecosystem.

## Key GSD Patterns Adopted

### 1. Phase Discovery & Roadmap Management
- **GSD Concept**: Reads `ROADMAP.md` to identify remaining phases, status, and order. Uses `gsd-tools query roadmap.analyze`.
- **AOS Implementation**:
    - A new file, `AOS_ROADMAP.md` (or extension of `FIXLIST.md`), will serve as the source for milestone phases.
    - Python parsing logic within the `discover_phases` LangGraph node will extract phase details.
    - Status updates (`pending`, `running`, `passed`, `failed`, `skipped`, `blocked`) will be reflected in this file.

### 2. Per-Phase Execution Loop (Discuss → Plan → Execute)
- **GSD Concept**: For each phase, it dispatches specialized agents for `discuss`, `plan`, and `execute` sub-steps.
- **AOS Implementation**:
    - A LangGraph `StateGraph` will orchestrate the overall flow.
    - A `run_phase` node will encapsulate the `discuss` → `plan` → `execute` sequence for a single phase.
    - Each sub-step will invoke specialist AOS agents (e.g., `planner`, `code-reviewer`, `implementer`) to perform the work.
    - These specialist agents will be defined as separate harness YAMLs under `aos/harnesses/autonomous/specialists/`.

### 3. Stateful Progress Tracking
- **GSD Concept**: Updates `.planning/STATE.md` after each phase for persistent progress tracking.
- **AOS Implementation**:
    - A dedicated JSON file (`.aos_state.json`) will be used for persistent state storage, managed by an `update_state` LangGraph node.
    - This file will track current phase, status, and any critical outputs or decisions.
    - AOS's `aos/memory.py` can be extended to manage this state file.

### 4. Milestone Completion & Reporting
- **GSD Concept**: After all phases, it performs a milestone audit, marks as complete, and cleans up.
- **AOS Implementation**:
    - An `audit_complete` LangGraph node will synthesize results from all phases.
    - A final report will be generated, detailing phase outcomes, durations, and any remaining concerns.
    - This will align with AOS's existing reporting mechanisms.

## Architecture

### AOS Directory Structure Changes

```
aos/
├── harnesses/
│   ├── autonomous/             # New autonomous harness
│   │   ├── approvals.yml       # Approval gates for autonomous loop
│   │   ├── dispatcher.yml      # Dispatches phase-specific agents
│   │   ├── evaluation.yml      # Evaluation criteria for autonomous loop
│   │   ├── harness.yml         # Main autonomous harness definition
│   │   ├── memory.yml          # Memory config for autonomous loop
│   │   ├── planner.yml         # Planner specialist for autonomous loop
│   │   ├── specialists/        # Autonomous phase specialists
│   │   │   ├── phase-executor.yml
│   │   │   └── phase-auditor.yml
│   │   └── tools.yml           # Tools available to autonomous harness
├── orchestrate/
│   ├── __init__.py
│   ├── gates.py
│   ├── pipeline.py             # Existing OrchestratePipeline
│   └── autonomous.py           # New: Core LangGraph orchestration for autonomous mode
├── __main__.py                 # Add CLI entrypoint for `aos orchestrate --autonomous`
└── tests/
    └── test_autonomous.py      # New: Unit and integration tests
```

### LangGraph StateGraph (`aos/orchestrate/autonomous.py`)

A new `AutonomousPipeline` class will encapsulate the LangGraph `StateGraph` to manage the flow.

```python
# Simplified representation
from langgraph.graph import StateGraph, END

class AutonomousState(TypedDict):
    current_phase: str
    roadmap: List[Dict]
    phase_results: Dict[str, Any]
    # ... other state variables

class AutonomousPipeline:
    def __init__(self, ctx: PipelineContext, gate_manager: Any):
        # ...
        self.graph = StateGraph(AutonomousState)
        self.graph.add_node("discover_phases", self._discover_phases)
        self.graph.add_node("run_phase", self._run_phase)
        self.graph.add_node("update_state", self._update_state)
        self.graph.add_node("audit_complete", self._audit_complete)

        self.graph.set_entry_point("discover_phases")

        self.graph.add_conditional_edges(
            "discover_phases",
            self._should_continue_phases,
            {"continue": "run_phase", "end": "audit_complete"}
        )
        self.graph.add_conditional_edges(
            "run_phase",
            self._should_continue_phases,
            {"continue": "update_state", "end": "audit_complete"}
        )
        self.graph.add_conditional_edges(
            "update_state",
            self._should_continue_phases, # Check if more phases or if current phase is done
            {"continue": "run_phase", "end": "audit_complete"}
        )
        self.graph.add_edge("audit_complete", END)

        self.compiled_graph = self.graph.compile()

    def _discover_phases(self, state: AutonomousState) -> Dict: ...
    def _run_phase(self, state: AutonomousState) -> Dict: ... # Invokes subagents
    def _update_state(self, state: AutonomousState) -> Dict: ...
    def _audit_complete(self, state: AutonomousState) -> Dict: ...
    def _should_continue_phases(self, state: AutonomousState) -> str: ...
```

### Specialist Agents (`aos/harnesses/autonomous/specialists/`)

These will be invoked by `_run_phase` within the LangGraph:

- **`phase-executor.yml`**: General purpose agent for executing the implementation steps of a phase.
- **`phase-auditor.yml`**: Reviews the output of a phase for completeness and adherence to requirements.

### CLI Integration (`aos/__main__.py`)

A new sub-command for `aos orchestrate` will be added:

`python -m aos orchestrate --autonomous [--roadmap-file <path>] [--dry-run]`

### Testing (`tests/test_autonomous.py`)

Unit tests for `_discover_phases`, `_run_phase` (mocking subagent calls), `_update_state`, and `_audit_complete`. Integration tests for the full `AutonomousPipeline` flow, potentially using dummy roadmap files.

## Open Questions / Clarifications

1.  **Roadmap File**: Should the autonomous harness use `FIXLIST.md` as its roadmap, or should we introduce a new `AOS_ROADMAP.md`? `FIXLIST.md` seems more aligned with bug/task tracking, whereas `ROADMAP.md` in GSD implied a broader, multi-phase project plan.
2.  **`gsd-tools query` equivalent**: GSD uses `gsd-tools query init.milestone-op` and `roadmap.analyze` to get project context and phase lists. How should AOS abstract this? Direct file parsing or a new AOS service?
3.  **Interactive flag**: GSD's `--interactive` flag for `discuss` phase. How should this map to AOS? A gate, or an `AskUserQuestion` tool call within the agent?

Please review this design. Once approved, I will proceed with creating the necessary files and implementing the pipeline.
