---
name: orchestrate
description: "End-to-end pipeline: /spec → /autoplan → /implement → /reviewloop → /ship. Turns a one-liner or plan doc into a merged PR with configurable human gates. Use when asked to 'orchestrate this', 'build end-to-end', 'ship this feature', or 'run the full pipeline'. Skills referenced: /spec, /autoplan, /implement, /reviewloop, /ship."
version: 0.1.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Agent
  - AskUserQuestion
triggers:
  - orchestrate this
  - run the full pipeline
  - end-to-end build
  - build and ship
  - full harness run
metadata:
  origin: agentic-harness
  dependencies:
    - gstack-spec
    - gstack-autoplan
    - gstack-review
    - gstack-ship
---

# Orchestrate — End-to-End Harness Pipeline

Bridge from idea to merged PR. Chains `/spec` → `/autoplan` → `/implement` → `/reviewloop` → `/ship` with configurable human gates and the ECC plan-orchestrate decomposition pattern.

## When to Invoke

- User has a feature idea or task and wants it built, reviewed, and shipped without manually running each skill.
- User says "orchestrate this", "build end-to-end", "ship this feature", "run the full pipeline".
- User provides a plan document path and wants it executed step by step.

Skip when:
- Work is a single trivial edit → edit directly, no pipeline needed.
- Only one phase is needed → invoke that skill directly (e.g., `/spec` for just spec-ing).
- User explicitly asks to skip phases.

## Flags

| Flag | Default | Effect |
|------|---------|--------|
| `--skip-spec` | OFF | Skip `/spec` — use existing plan/issue. |
| `--skip-plan` | OFF | Skip `/autoplan` — trust existing plan. |
| `--skip-review` | OFF | Skip formal review; go straight to `/ship` after `/implement`. |
| `--execute` | ON (when not in plan mode) | Auto-spawn implementation agent after `/autoplan`. |
| `--no-execute` | — | File plan only; do NOT execute. |
| `--gate spec\|plan\|ship` | all | Which human gates to enforce. Comma-separated. Use `none` for fully autonomous. |

## Pipeline Overview

```
┌──────────┐    ┌──────────┐    ┌───────────┐    ┌─────────────┐    ┌───────┐
│  /spec   │───▶│ /autoplan │───▶│ /implement │───▶│ /reviewloop │───▶│ /ship │
│ (Why→   │    │ (CEO→   │    │ (TDD→    │    │ (fix→    │    │ (PR→  │
│  What)  │    │  Eng→DX)│    │  tests)  │    │  re-review)│ │  merge)│
└──────────┘    └──────────┘    └───────────┘    └─────────────┘    └───────┘
     │               │                │                 │                │
  Gate A         Gate B           Agent             Gate C           Gate D
  (spec          (plan            spawn             (review          (final
  approval)      approval)        in worktree        approval)        merge)
```

## Phase 0 — Intake & Gate Configuration

1. Parse flags from user's invocation.
2. Detect project root: `git rev-parse --show-toplevel`.
3. Read `CLAUDE.md` for skill routing rules and project context.
4. Confirm gate configuration:

> Gates: spec=<on/off>, plan=<on/off>, review=<on/off>, ship=<on/off>
> Flags: --skip-spec=<yes/no>, --skip-plan=<yes/no>, --skip-review=<yes/no>, --execute=<yes/no>

If `--gate none`: proceed autonomously without pausing for confirmation.
If `--gate spec` (default): present spec draft for approval before Phase 2.
If `--gate plan` (default): present autoplan results for approval before Phase 3.

## Phase 1 — /spec (skip if --skip-spec)

**Goal:** Turn vague intent into a precise, executable spec.

### Step 1.1 — Trigger /spec

Invoke the `/spec` skill with:

```
/spec <user's original request> --execute=auto --plan-file <.gstack/plans/<slug>-<branch>-plan.md>
```

`--execute=auto` means: spawn an agent in a fresh worktree after filing the issue (gated by `--execute` flag and `--no-execute`).

### Step 1.2 — Collect Outputs

After `/spec` completes, collect:
- Issue number and URL
- Plan file path (from `--plan-file` or default location)
- Spawned agent worktree path (if `--execute`)

### Step 1.3 — Spec Gate (if --gate spec)

Present to user:

> **Spec filed:** #{N} — <title>
> **Plan:** <plan_path>
> **Worktree:** <path or "none">
>
> Approve this spec and continue to `/autoplan`?

Options: A) Approve and continue B) Revise spec C) Cancel

If user cancels → STOP. If user revises → re-run `/spec` with feedback.

If `--gate none`: proceed without asking.

## Phase 2 — /autoplan (skip if --skip-plan)

**Goal:** Full review gauntlet — CEO → Design → Eng → DX.

### Step 2.1 — Trigger /autoplan

Invoke `/autoplan` on the plan file produced by Phase 1:

```
/autoplan <plan_file>
```

`/autoplan` internally runs all four review phases with dual voices (Claude + Codex) and auto-decides intermediate questions.

### Step 2.2 — Collect Outputs

After `/autoplan` completes, collect:
- Review scores (CEO, Design, Eng, DX)
- Decision audit trail
- Implementation task list
- Any user challenges or taste decisions

### Step 2.3 — Plan Gate (if --gate plan)

Present to user:

> **Plan review complete.**
> **Scores:** CEO=X/6, Eng=X/6, DX=X/6
> **Decisions:** N auto-decided, M taste choices, K user challenges
>
> Approve this plan and continue to `/implement`?

Surface user challenges explicitly — these are cases where both models disagreed with the user's stated direction.

Options: A) Approve and continue B) Revise plan C) Cancel

If `--gate none`: proceed without asking.

## Phase 3 — /implement

**Goal:** Structured implementation using TDD, derived from the approved plan.

This phase reads the plan file (`<plan_path>`) and decomposes it into executable steps, then runs each step through the appropriate agent chain.

### Step 3.1 — Decompose Plan Into Steps

Read the plan file and decompose into steps using the ECC plan-orchestrate algorithm:

1. **Identify step boundaries** in priority order:
   - Explicit numbering: `## Step N`, `### Phase N`, `## N. ...`
   - "Step" column in tables
   - `---`-separated blocks with verb-led headings
   - Otherwise, treat each H2 as one step

2. **Extract per step:**
   - `id`: 1-based index
   - `title`: ≤80 chars
   - `intent`: 1-3 sentences
   - `tags`: from trigger words (see table below)
   - `acceptance`: 1-3 verifiable criteria from the plan

3. **Tag each step:**

| Tag | Trigger words | Default agent chain |
|-----|--------------|-------------------|
| `design` | architecture, design, RFC, evaluate | `planner,architect` |
| `impl` | implement, build, add, create, port | `tdd-guide,<lang>-reviewer` |
| `test` | test, coverage, e2e, integration | `tdd-guide,e2e-runner` |
| `refactor` | refactor, cleanup, dedupe, split | `architect,refactor-cleaner,<lang>-reviewer` |
| `db` | schema, migration, index, SQL, Postgres, alembic | `tdd-guide,database-reviewer,<lang>-reviewer` |
| `security` | encrypt, auth, secret, OWASP | `tdd-guide,security-reviewer,<lang>-reviewer` |
| `docs` | docs, readme, codemap, changelog | `doc-updater` |
| `review` | review, audit, verify | `<lang>-reviewer,code-reviewer` |

**Language detection:** Probe `pyproject.toml` → python, `package.json` → typescript, `go.mod` → go, `Cargo.toml` → rust. Default to `code-reviewer` when unknown.

**Chain composition rules:**
- `impl` + `security` → `tdd-guide,<lang>-reviewer,security-reviewer`
- `impl` + `db` → `tdd-guide,database-reviewer,<lang>-reviewer`
- Deduplicate after composing
- Max chain length: 4 agents
- Steps tagged `impl`/`refactor`/`migration` end with a reviewer-class agent
- `test` and `build` steps are gated by their own validators (no extra reviewer needed)

### Step 3.2 — Compress Task Descriptions

Each task description must:
- Be self-contained (first agent does not need the plan doc open)
- Start with `[Plan: <path>#step-<id>]`
- Include 1-3 Acceptance criteria
- Include `Out of scope: ...` only if the plan declares one for this step
- Be 200-600 characters, single line, escaped double quotes

### Step 3.3 — Execute Steps

For each step, invoke:

```bash
/orchestrate custom "<agent1>,<agent2>,<agent3>" "[Plan: <path>#step-<id>] <task description>; Acceptance: <criteria>; Out of scope: <guard>"
```

**Execution modes:**

| Mode | When | Mechanism |
|------|------|----------|
| **Agent team** (default) | 2+ agents in chain | `TeamCreate` + `TaskCreate` + `SendMessage` for inter-agent coordination |
| **Sub-agent** | Single agent, no coordination needed | Direct `Agent` tool call, `run_in_background` for parallel |
| **Hybrid** | Step N needs different mode than N+1 | Switch modes between steps |

**Default to agent team mode when 2+ agents collaborate.** Team communication overhead pays off for discovery sharing and conflict resolution. Use sub-agent mode only when coordination is structurally unnecessary (result delivery only).

**Parallelization:** Steps with no dependency on each other can run in parallel. Steps tagged `impl` that modify the same files run sequentially.

### Step 3.4 — Progress Tracking

After each step completes:
1. Update the plan file with completion status
2. Log step result to `_workspace/step-results.jsonl`
3. If a step fails: offer fix via `/reviewloop` before continuing

**Step result schema:**
```json
{
  "step_id": 1,
  "title": "Create User model",
  "status": "passed|failed|skipped",
  "agent_chain": "tdd-guide,python-reviewer",
  "duration_s": 45,
  "artifacts": ["src/models/user.py", "tests/test_user.py"],
  "review_notes": "..." 
}
```

## Phase 4 — /reviewloop

**Goal:** Iterative fix loop — review → auto-fix → re-review → escalate.

### Step 4.1 — Run Review

Invoke `/review` on the implementation diff:

```bash
/review --base <base_branch>
```

### Step 4.2 — Classify Findings

| Severity | Action | Exit criteria |
|----------|--------|---------------|
| **CRITICAL** | Auto-fix if deterministic; escalate to user if ambiguous | 0 CRITICAL |
| **HIGH** | Auto-fix if pattern matches known fix; escalate otherwise | 0 HIGH |
| **MEDIUM** | Log for next iteration | 0 HIGH + CRITICAL |
| **LOW** | Note only, do not block | N/A |

### Step 4.3 — Fix Loop

1. Fix all CRITICAL and HIGH findings:
   - Deterministic fixes (typos, imports, type errors) → apply directly
   - Ambiguous fixes → spawn `code-reviewer` sub-agent to propose fix
2. Re-run `/review` on the updated diff
3. Repeat until:
   - No CRITICAL or HIGH findings remain, OR
   - Max iterations reached (default: 3)

**Max iterations lock:** After 3 review-fix cycles with no improvement, escalate remaining findings to user and proceed with their decision.

### Step 4.4 — Review Gate (if --gate review)

Present to user:

> **Review complete after N iterations.**
> **Findings:** X CRITICAL (fixed), Y HIGH (fixed), Z MEDIUM (deferred)
> **Remaining:** <list any unfixed MEDIUM/LOW>
>
> Continue to `/ship`?

Options: A) Continue to ship B) Fix remaining first C) Cancel

If `--gate none`: proceed without asking.

## Phase 5 — /ship

**Goal:** Merge base → run tests → bump VERSION → update CHANGELOG → commit → push → create PR.

### Step 5.1 — Trigger /ship

Invoke:

```bash
/ship --base <base_branch> --close-issue <issue_number>
```

`--close-issue` auto-closes the original spec issue when the PR merges.

### Step 5.2 — Collect Outputs

- PR URL
- Commit SHA
- VERSION bump
- Issue closure status

## Completion Report

After all phases complete, report:

```
STATUS: DONE | DONE_WITH_CONCERNS | BLOCKED | CANCELLED
PHASES COMPLETED: spec (N min) → autoplan (N min) → implement (N steps) → reviewloop (N iterations) → ship (N min)
ISSUE: #N (<title>)
PR: <url>
DECISIONS: <N> taste decisions, <M> auto-decided
CONCERNS: <any MEDIUM findings deferred, or "none">
```

## Edge Cases

### No plan file exists (--skip-spec)
If `--skip-spec` is used but no plan file is found in the expected location (`.gstack/plans/` or user-specified path), ASK the user for the plan path. Do not guess.

### /autoplan returns user challenges
If `/autoplan` surfaces user challenges (both models disagree with user's stated direction), present them explicitly at the plan gate. Do not auto-decide these — they require human judgment.

### /implement step fails
If a step fails during implementation:
1. Log the failure with step ID and error context
2. Offer to run `/investigate` for debugging
3. If user approves, retry the step once
4. If retry fails, present options: skip step / revise plan / cancel pipeline

### /reviewloop max iterations exceeded
If 3 review-fix iterations pass without resolving CRITICAL/HIGH findings:
1. Present all remaining findings to user
2. Offer: A) Ship anyway (accept risk) B) Revise implementation C) Cancel
3. Log the decision for future learning

### Plan declares its own agents
If the plan document references specific agents (e.g., "use `python-reviewer`"):
1. Strip any namespace prefix (e.g., `everything-claude-code:`) to get the bare name
2. Validate against the agent catalogue
3. Replace invalid agents and note under "Chain rationale"
4. Re-prefix at output time per the ECC install form

### Polyglot project (--lang=auto tie)
If `--lang=auto` cannot pick a language winner (two markers match, or no clear majority):
1. Set `lang=unknown`
2. Reviewer resolves to `code-reviewer`
3. Build resolver resolves to `build-error-resolver`
4. Note the fallback in the step's chain rationale

### Large plan (>1500 lines)
If the plan file exceeds 1500 lines:
1. Enter **overview-only mode** — emit only the overview table
2. Ask user to narrow with `--scope=step:<n>` or `--scope=range:<a>-<b>`
3. Do not emit per-step commands until scope is narrowed

## Integration with Existing Skills

| This skill calls | When | What it delegates |
|-----------------|------|-------------------|
| `/spec` | Phase 1 (unless --skip-spec) | Issue creation, quality gate, redaction |
| `/autoplan` | Phase 2 (unless --skip-plan) | CEO/Design/Eng/DX review, dual voices |
| `/orchestrate custom` | Phase 3 (per step) | Agent chain execution |
| `/review` | Phase 4 | Pre-landing diff review |
| `/ship` | Phase 5 | Merge, test, version, PR |

## Human Gates Summary

| Gate | Phase | When | Can skip with |
|------|-------|------|---------------|
| **Spec Gate** | After Phase 1 | Approve spec before planning | `--gate none`, `--gate plan,ship` |
| **Plan Gate** | After Phase 2 | Approve plan before implementation | `--gate none`, `--gate spec,ship` |
| **Review Gate** | After Phase 4 | Approve review findings before ship | `--gate none`, `--gate spec,plan` |
| **Ship Gate** | Phase 5 | /ship handles its own confirmation internally | N/A (always asks) |

## Completion Status Protocol

Report one of:
- **DONE** — all phases completed, PR merged
- **DONE_WITH_CONCERNS** — completed, MEDIUM findings deferred, note them
- **BLOCKED** — cannot proceed; state blocker and what was tried
- **NEEDS_CONTEXT** — missing info; state exactly what is needed
- **CANCELLED** — user cancelled at a gate

Format: `STATUS | REASON | PHASES COMPLETED | RECOMMENDATION`
