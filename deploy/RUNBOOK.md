# AOS Operations Runbook

## Quick Reference

| Command | Purpose |
|---------|---------|
| `python -m aos status` | System status |
| `python -m aos ventures` | List ventures |
| `python -m aos run --venture netso` | Run daily cycle |
| `python -m aos approvals list` | Pending approvals |
| `python -m aos approvals approve <ID>` | Approve item |
| `python -m aos approvals reject <ID>` | Reject item |

## Daily Operations (09:00 BDT)

### Morning Checklist
1. Check dashboard: `https://aos.yourdomain.com`
2. Verify daily executive brief generated (check DASHBOARD.md)
3. Check approval queue: `python -m aos approvals list`
4. Review overnight escalations

### Evening Checklist
1. Run harness cycle if needed: `python -m aos run --venture netso`
2. Review weekly report (Fridays)
3. Archive session logs

## Approval Management

```bash
# List pending
python -m aos approvals list

# Approve specific (with note)
python -m aos approvals approve APR-0001 --note "Approved per CFO review"

# Reject specific
python -m aos approvals reject APR-0002 --note "DSCR below floor"

# Approve all (bundled)
python -m aos approvals approve-all --note "Bulk approved per weekly review"
```

## Incident Response

### DSCR Breach (< 2.0)
1. Automatic escalation alert fires (AGT-EXEC-RSK)
2. Check dashboard: DSCR KPI
3. CFO (MINERVA) runs scenario analysis
4. Founder decision via approval gate

### LLM Provider Outage
1. Check logs: `journalctl -u aos-engine -f | grep -i llm`
2. System auto-falls back: 9router → NVIDIA NIM → Anthropic direct → dry-run
3. Verify free-tier pool health: `curl localhost:20128/v1/models`

### WebSocket Disconnect Storm
1. Check engine health: `curl /health/ready`
2. Restart engine: `sudo systemctl restart aos-engine`
3. Dashboard auto-reconnects (exponential backoff built-in)

## Backup & Recovery

### Daily Backup (cron 02:00)
```bash
./deploy/backup.sh
```

### Recovery Procedure
```bash
sudo systemctl stop aos-engine aos-dashboard
cp /backup/aos/2026-01-15/aos_memory.db /Users/tazwarmahtab/orca/agentic-harness/
cp /backup/aos/2026-01-15/approvals.db /Users/tazwarmahtab/orca/agentic-harness/
cp /backup/aos/2026-01-15/usage.db /Users/tazwarmahtab/orca/agentic-harness/
cp -r /backup/aos/2026-01-15/artifacts/* /Users/tazwarmahtab/Documents/10-Projects/Netso_HQ/ai_system/System/
sudo systemctl start aos-engine aos-dashboard
```

## Key Metrics & Alerts

| Metric | Warning | Critical |
|--------|---------|----------|
| Harness cycle duration | > 10 min | > 30 min |
| LLM error rate | > 5% | > 20% |
| Approval queue depth | > 10 | > 50 |
| DSCR (Netso) | < 2.25 | < 2.0 |
| WebSocket disconnects/hr | > 10 | > 50 |

## Health Checks

```bash
# Liveness
curl https://aos.yourdomain.com/health

# Readiness (includes LLM provider check)
curl https://aos.yourdomain.com/health/ready

# WebSocket stats
curl -H "Authorization: Bearer $AOS_API_TOKEN" https://aos.yourdomain.com/api/ws/stats
```

## Logs

```bash
# Engine logs
sudo journalctl -u aos-engine -f

# Dashboard logs
sudo journalctl -u aos-dashboard -f

# Recent errors
sudo journalctl -u aos-engine --since "1 hour ago" | grep -i error
```

## Multi-Venture Expansion

### Add TransitBD
```bash
# 1. Create venture config
mkdir -p aos/ventures/transitbd/seed
cp aos/ventures/netso/venture.yml aos/ventures/transitbd/
# Edit venture.yml for TransitBD specifics

# 2. Create harness bundle
mkdir -p aos/harnesses/transitbd/{specialists,sops}

# 3. Register
python -m aos ventures

# 4. Test
python -m aos run --venture transitbd --harness executive --dry-run
```

## Contact
- Founder: Tazwar Mahtab
- System: AOS (Agentic Operating System) — Netso Energy Venture