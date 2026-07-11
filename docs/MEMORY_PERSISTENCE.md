# TAZ OS Memory Persistence Schema

**Last Updated:** 2026-07-11  
**Version:** 1.0  
**Backend:** SQLite

## Overview

The three-layer memory system (long-term, episodic, semantic) persists to SQLite for durability and cross-session recall. This document describes the database schema, backup procedures, and migration strategy.

---

## Database Schema

### Primary Table: `memory_entries`

Stores all memory entries across all layers.

```sql
CREATE TABLE memory_entries (
    id TEXT PRIMARY KEY,
    layer TEXT NOT NULL,              -- 'long_term', 'episodic', 'semantic'
    domain TEXT NOT NULL,             -- e.g., 'company_facts', 'daily_dashboard'
    key TEXT,                         -- Optional key for key-value entries
    value TEXT,                       -- Optional value for key-value entries
    ref TEXT,                         -- Optional reference (e.g., file path)
    content TEXT,                     -- Full content for text entries
    classification TEXT DEFAULT 'internal',  -- 'public', 'internal', 'confidential', etc.
    source_agent TEXT,                -- Agent ID that created this entry
    created_at TEXT NOT NULL,         -- ISO 8601 timestamp
    version INTEGER DEFAULT 1,        -- Version number (immutable entries increment)
    replaced_by TEXT,                 -- ID of replacement entry if superseded
    venture_id TEXT,                  -- Venture this entry belongs to
    content_hash TEXT                 -- SHA256 hash of content for deduplication
);
```

### Indexes

```sql
CREATE INDEX idx_mem_layer_domain
ON memory_entries(layer, domain);
```

**Purpose:** Fast lookup of entries by layer and domain (most common query pattern).

---

## Data Dictionary

| Column | Type | Purpose | Example |
|--------|------|---------|---------|
| `id` | TEXT | Unique identifier | `MEM-LONG-TERM-001` |
| `layer` | TEXT | Memory layer | `long_term`, `episodic`, `semantic` |
| `domain` | TEXT | Logical grouping | `company_facts`, `daily_dashboard` |
| `key` | TEXT | Key for KV entries | `CAPEX_PER_KW_SCENARIO_A` |
| `value` | TEXT | Value for KV entries | `55000` |
| `ref` | TEXT | File reference | `/ventures/netso/DASHBOARD.md` |
| `content` | TEXT | Full text content | Multi-paragraph analysis |
| `classification` | TEXT | Access level | `founder_only`, `confidential` |
| `source_agent` | TEXT | Creator | `AGT-EXEC-CFO` |
| `created_at` | TEXT | Creation timestamp | `2026-07-11T14:30:00Z` |
| `version` | INTEGER | Version number | `1`, `2`, `3` |
| `replaced_by` | TEXT | Replacement entry ID | `MEM-LONG-TERM-002` |
| `venture_id` | TEXT | Venture scope | `VEN-NETSO-001` |
| `content_hash` | TEXT | Dedup hash | `a3f2c8d9e1b4f6...` |

---

## Memory Layers

### Long-Term Memory
- **Purpose:** Persistent company facts (never change)
- **Examples:** Financial constants, pricing models, core facts
- **Retention:** Permanent (archived, not deleted)
- **Query Pattern:** Direct key lookup (e.g., CAPEX_PER_KW)

### Episodic Memory
- **Purpose:** Events, decisions, meetings (time-sequenced)
- **Examples:** "Investor call on 2026-07-15", "DSCR breach alert on 2026-07-10"
- **Retention:** Configurable (default: 90 days), older entries archived
- **Query Pattern:** Time range queries with domain filtering

### Semantic Memory
- **Purpose:** Rules, patterns, standards (how things work)
- **Examples:** "DSCR < 2.0x triggers P0 alert", "Blended rate forbidden in savings"
- **Retention:** Permanent (versioned when updated)
- **Query Pattern:** Domain lookup + content search

---

## Domains (Logical Groupings)

Each domain represents a logical category of memory:

```
Long-Term:
  - company_facts          (financial constants, legal structure)
  - venture_artifacts      (files, paths, configuration)
  - pricing_models         (unit economics, rate calculations)

Episodic:
  - daily_dashboard        (daily status, KPI snapshots)
  - decisions              (founder decisions with rationale)
  - alerts                 (risk alerts, escalations)
  - meetings               (attendees, outcomes, action items)

Semantic:
  - operational_rules      (when to escalate, approval gates)
  - financial_rules        (valid ranges, hard thresholds)
  - validation_rules       (what passes/fails evaluator)
  - routing_rules          (task routing, escalation paths)
```

---

## Immutability & Versioning

All entries are **immutable** — never modified in place.

**When an entry changes:**
1. Old entry marked with `replaced_by = NEW_ENTRY_ID`
2. New entry created with `version = OLD_VERSION + 1`
3. Both entries preserved in database for audit trail

**Example:**
```
Entry A: {id: MEM-001, version: 1, value: "55000", replaced_by: MEM-002}
Entry B: {id: MEM-002, version: 2, value: "60000", replaced_by: null}
```

---

## Backup Strategy

### Recommended Backup Approach

1. **Production Backup (Daily)**
   ```bash
   # Backup the SQLite database file
   cp tazos/ventures/netso/memory.db tazos/ventures/netso/backups/memory-$(date +%Y%m%d).db
   
   # Keep last 30 days
   find tazos/ventures/netso/backups -name "memory-*.db" -mtime +30 -delete
   ```

2. **Export to JSON (Weekly)**
   ```bash
   # Full export for external archival
   sqlite3 tazos/ventures/netso/memory.db ".mode json" ".output memory-export-$(date +%Y%m%d).json" "SELECT * FROM memory_entries;"
   ```

3. **Verification**
   ```bash
   # Check database integrity
   sqlite3 tazos/ventures/netso/memory.db "PRAGMA integrity_check;"
   ```

---

## Migrations (Future)

### Migration 1.1: Add Audit Logging
When: If audit requirements expand beyond `source_agent` + `created_at`

```sql
ALTER TABLE memory_entries ADD COLUMN updated_by TEXT;
ALTER TABLE memory_entries ADD COLUMN updated_at TEXT;
```

### Migration 1.2: Partition by Venture
When: If multi-venture queries become slow

```sql
CREATE TABLE memory_entries_netso AS 
  SELECT * FROM memory_entries WHERE venture_id = 'VEN-NETSO-001';
CREATE TABLE memory_entries_transitbd AS 
  SELECT * FROM memory_entries WHERE venture_id = 'VEN-TRANSITBD-001';
```

---

## Recovery Procedures

### If Database is Corrupted

```bash
# 1. Restore from most recent backup
cp tazos/ventures/netso/backups/memory-YYYYMMDD.db tazos/ventures/netso/memory.db

# 2. Verify integrity
sqlite3 tazos/ventures/netso/memory.db "PRAGMA integrity_check;"

# 3. If successful, restart harness
python3 -m tazos run --venture netso
```

### If Data Loss Occurs

**Incident Response:**
1. Restore from backup immediately
2. Identify what was lost (time window)
3. Re-submit lost entries if possible (via agent memory candidates)
4. Log incident with timestamp

---

## Performance Tuning

### Current Index Strategy
- Single composite index on (layer, domain) covers most queries
- Query time: <10ms for typical domain lookup

### If Performance Degrades

```sql
-- Add index on created_at for time-range queries
CREATE INDEX idx_mem_created_at ON memory_entries(created_at);

-- Add index on source_agent for agent audit trails
CREATE INDEX idx_mem_source_agent ON memory_entries(source_agent);

-- Analyze query plans
EXPLAIN QUERY PLAN SELECT * FROM memory_entries WHERE layer='episodic' AND domain='daily_dashboard';
```

---

## Cleanup & Archival

### Episodic Memory Retention Policy

Older episodic entries should be archived after 90 days:

```bash
# Export entries older than 90 days
sqlite3 tazos/ventures/netso/memory.db << SQL
SELECT * FROM memory_entries 
WHERE layer='episodic' 
  AND created_at < datetime('now', '-90 days')
  INTO OUTFILE 'memory-archive-old.json';
SQL

# Delete archived entries
sqlite3 tazos/ventures/netso/memory.db << SQL
DELETE FROM memory_entries 
WHERE layer='episodic' 
  AND created_at < datetime('now', '-90 days');
SQL
```

---

## Monitoring

### Health Checks

```bash
# Check database size
du -h tazos/ventures/netso/memory.db

# Count entries by layer
sqlite3 tazos/ventures/netso/memory.db "SELECT layer, COUNT(*) FROM memory_entries GROUP BY layer;"

# Count entries by domain
sqlite3 tazos/ventures/netso/memory.db "SELECT domain, COUNT(*) FROM memory_entries GROUP BY domain;"
```

### Alerts (Recommended)

- ⚠️ Database size > 500MB: Archive old episodic entries
- ⚠️ PRAGMA integrity_check fails: Restore from backup
- ⚠️ Query time > 100ms: Check indexes

---

## Related Documentation

- Memory System Architecture: See `tazos/memory.py`
- Three-Layer Memory Design: See `README.md` section "Three-Layer Memory System"
- Agent Memory Permissions: See `tazos/schemas/agent.py` `allowed_memory` field

