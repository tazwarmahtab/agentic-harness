# Netso Energy AI Company

This directory is the portable Paperclip/Agent Companies package for Netso Energy.

## Architecture

```text
Taz / Board
    ↓
Paperclip control plane
    ├── CEO / Maestro
    ├── COO
    ├── CFO
    ├── CRO
    ├── CTO / Energy Engineering
    └── Regulatory / Legal
            ↓
Existing AOS / agentic-harness runtime
    ├── LangGraph orchestration
    ├── capability-based tools
    ├── memory
    ├── evaluation
    ├── Netso venture context
    ├── financial validation
    └── cross-harness dispatch
            ↓
NEOS business/data layer
```

Paperclip should own workforce coordination and governance. AOS should continue owning domain execution and existing harness logic. NEOS should own canonical Netso business entities and institutional memory.

## Import

Paperclip supports importing a company from a local directory or GitHub subfolder. Prefer a dry-run and keep imported agents/routines paused until governance checks pass.

```bash
paperclipai company import \
  https://github.com/tazwarmahtab/agentic-harness/tree/feat/netso-ai-company-v1/companies/netso-energy \
  --target new \
  --new-company-name "Netso Energy AI Company" \
  --dry-run

paperclipai company import \
  https://github.com/tazwarmahtab/agentic-harness/tree/feat/netso-ai-company-v1/companies/netso-energy \
  --target new \
  --new-company-name "Netso Energy AI Company" \
  --yes \
  --json
```

After import, configure runtime adapters and local workspaces in Paperclip. Machine-local paths and secrets are intentionally not embedded in this package.

## Pilot mode

Do not activate scheduled heartbeats initially. Start with recommendation-only and reversible internal work. External communication, material pricing, PPAs, financing, payments, regulatory submissions, and final engineering approvals stay human-gated.

## Existing AOS validation

From the repository root:

```bash
python -m aos validate
python -m aos status
python -m aos run --venture netso --dry-run
pytest -q
```

The existing repository already provides the domain runtime, memory, approvals, evaluation, Netso context, and multi-harness orchestration. This package adds the company-level Paperclip configuration around it.
