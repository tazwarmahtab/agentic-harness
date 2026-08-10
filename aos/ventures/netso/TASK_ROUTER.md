# Netso Energy — Task Router

> Routing rules, SLAs, and escalation paths.
> Last updated: 2026-08-07

## Routing Rules

| Task Category | Route To | SLA | Escalation |
|---------------|----------|-----|------------|
| Financial modeling | AGT-EXEC-CFO | 24h | Founder if DSCR < 2.25x |
| Contract review | AGT-EXEC-LEG | 48h | Founder if value > BDT 5M |
| Risk assessment | AGT-EXEC-RSK | 24h | Immediate if DSCR < 2.0x |
| Daily operations | AGT-EXEC-COO | Same day | Founder if blocked > 48h |
| KPI reporting | AGT-EXEC-PERF | Weekly | Founder if KPI drift > 10% |
| Customer comms | AGT-EXEC-CHIEFOFSTAFF | 24h | Founder for escalations |
| Cross-harness tasks | AGT-EXEC-DISPATCH | 4h | COO if unresolved |

## Escalation Paths

### Financial Escalation
1. DSCR < 2.25x → CFO + Founder review
2. DSCR < 2.0x → Immediate alert to Founder
3. Invoice overdue > 30 days → CFO + Founder

### Operational Escalation
1. Blocker unresolved > 48h → COO escalates to Founder
2. Customer complaint → COO + Legal review
3. Installation delay > 1 week → Operations + Founder

### Regulatory Escalation
1. SREDA deadline approaching → Legal + Founder
2. IDCOL compliance issue → Legal + CFO + Founder
3. NBR tax inquiry → Legal + Founder

## SLA Summary

| Priority | Response Time | Resolution Time |
|----------|---------------|-----------------|
| P0 (Critical) | 1 hour | 4 hours |
| P1 (High) | 4 hours | 24 hours |
| P2 (Medium) | 24 hours | 72 hours |
| P3 (Low) | 72 hours | 1 week |

## Approval Gates

| Action | Threshold | Approver |
|--------|-----------|----------|
| Proposal value | > BDT 5,000,000 | Founder |
| DSCR escalation | < 2.25x | Founder + CFO |
| DSCR alert | < 2.0x | Immediate alert |
| New vendor | Any | Founder |
| Contract signing | Any | Founder |
