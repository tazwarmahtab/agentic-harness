# Composio + Notion Integration

**Status:** ✅ Active (linked 2026-06-14, OAUTH2, ACTIVE)

## Overview

Notion access via Composio CLI with automatic OAuth token management. No manual token refresh, no `NOTION_API_KEY` env var required.

## Architecture

```
AOS Harness/Skill
    ↓
aos/integrations/composio_notion.py (Python client)
    ↓
composio CLI (subprocess)
    ↓
Composio API (manages OAuth tokens)
    ↓
Notion API
```

## Setup Verification

```bash
# Check Composio auth
composio whoami
# {"account_type":"human","email":"tazwarmahtab2@gmail.com",...}

# Check Notion link
composio link notion --list
# {"toolkit":"notion","total":1,"items":[{"status":"ACTIVE",...}]}
```

Already configured ✅

## Usage

### Python (Recommended for AOS harnesses)

```python
from aos.integrations.composio_notion import ComposioNotionClient

client = ComposioNotionClient()

# Search
result = client.search_pages(query="netso", page_size=10)
if result.successful:
    pages = result.data["results"]

# Create page
result = client.create_page(
    parent_id="PARENT_PAGE_ID",
    title="Deal Pipeline Update",
    markdown="# CGS Deal\n\nSigned LOI, proceeding to EPC tender."
)

# Query database
result = client.query_database(
    database_id="DB_ID",
    filter_obj={"property": "Status", "select": {"equals": "Active"}},
    sorts=[{"property": "Priority", "direction": "descending"}]
)
```

### CLI (for quick scripts)

```bash
# Search
composio execute "NOTION_SEARCH_NOTION_PAGE" -d '{"query":"netso","page_size":5}'

# Create
composio execute "NOTION_CREATE_NOTION_PAGE" -d '{
  "parent_id":"...",
  "title":"Meeting Notes",
  "markdown":"# Decisions\n- Proceed with IDCOL application"
}'
```

## Available Operations

| Method | Tool Slug | Purpose |
|---|---|---|
| `search_pages()` | `NOTION_SEARCH_NOTION_PAGE` | Find pages/databases |
| `create_page()` | `NOTION_CREATE_NOTION_PAGE` | Create page with markdown |
| `fetch_page_content()` | `NOTION_FETCH_BLOCK_CONTENTS` | Read page blocks |
| `fetch_database()` | `NOTION_FETCH_DATABASE` | Database schema |
| `query_database()` | `NOTION_QUERY_DATABASE_WITH_FILTER` | Query with filters |
| `insert_database_row()` | `NOTION_INSERT_ROW_DATABASE` | Add database row |
| `append_text_blocks()` | `NOTION_APPEND_TEXT_BLOCKS` | Append paragraphs |
| `append_code_blocks()` | `NOTION_APPEND_CODE_BLOCKS` | Append code |

Full list: 16 tools in `~/.composio/tool_definitions/NOTION_*.json`

## Integration Points

### 1. Harness Logging

```python
# aos/ventures/netso/harness_nodes.py
from aos.integrations.composio_notion import composio_notion_create_page

def log_execution_to_notion(state: dict) -> dict:
    """Log harness run to Notion workspace."""
    NETSO_LOG_PAGE_ID = "..."  # from env or config
    
    page = composio_notion_create_page(
        parent_id=NETSO_LOG_PAGE_ID,
        title=f"Execution {state['run_id']} — {state['timestamp']}",
        markdown=f"""
# Status: {state['status']}

## Approvals
{state['approvals_summary']}

## Actions Taken
{state['actions_log']}
"""
    )
    
    state["notion_log_url"] = page["url"]
    return state
```

### 2. Deal Pipeline Sync

```python
# Sync Netso deal pipeline from ROADMAP.md to Notion database
from aos.integrations.composio_notion import ComposioNotionClient

client = ComposioNotionClient()

deals = [
    {"name": "CGS 80kW", "status": "LOI Signed", "capacity_kw": 80},
    {"name": "IDCOL Application", "status": "In Progress", "capacity_kw": 15000},
]

for deal in deals:
    client.insert_database_row(
        database_id=NETSO_DEALS_DB_ID,
        properties={
            "Name": {"title": [{"text": {"content": deal["name"]}}]},
            "Status": {"select": {"name": deal["status"]}},
            "Capacity (kW)": {"number": deal["capacity_kw"]}
        }
    )
```

### 3. Weekly Reports

```python
# Automated weekly status update to Notion
from aos.integrations.composio_notion import composio_notion_create_page

def weekly_status_to_notion():
    markdown = generate_weekly_status()  # from ROADMAP.md + git log
    
    composio_notion_create_page(
        parent_id=WEEKLY_REPORTS_PAGE_ID,
        title=f"Week of {datetime.now().strftime('%Y-%m-%d')}",
        markdown=markdown
    )
```

## Configuration

No env vars required. Auth state stored in `~/.composio/`.

Optional: set parent page IDs in `.env` for harness integration:

```bash
NETSO_NOTION_LOG_PAGE_ID=8df0f1dc69144573a303cdf7a8ee1441
NETSO_NOTION_DEALS_DB_ID=...
```

## Troubleshooting

### Empty search results / 404 errors

Parent page not shared with Composio integration:

1. Open parent page in Notion web
2. Click `...` → `Connect to` → select Composio integration

### "composio command not found"

```bash
curl -fsSL https://composio.dev/install | sh
composio login
```

### Token expired (unlikely)

Composio auto-refreshes OAuth tokens. If broken:

```bash
composio link notion --list  # check status
composio link notion          # re-link if needed
```

## Performance

- **Latency:** +50-100ms vs direct Notion API (Composio proxy overhead)
- **Rate limits:** Same as Notion API (~3 req/s)
- **Reliability:** Composio handles transient failures and retries

Acceptable for async harness logging. For real-time user-facing ops, consider direct Notion API via `notion` skill.

## Comparison: Composio vs Direct Notion API

| | Composio | Direct (`notion` skill) |
|---|---|---|
| Auth setup | Browser OAuth (one-time) | API token in `.env` |
| Token refresh | Automatic | Manual (90 days) |
| Multi-workspace | Link each workspace | One token per workspace |
| Latency | +50-100ms | Direct |
| Workers support | ❌ | ✅ (via `ntn` CLI) |
| Best for | Background logging, sync | Real-time ops, Workers |

## References

- Python client: `aos/integrations/composio_notion.py`
- Skill doc: `.hermes/skills/productivity/composio-notion/SKILL.md`
- Composio dashboard: https://app.composio.dev
- Tool schemas: `~/.composio/tool_definitions/NOTION_*.json`
- Composio docs: https://docs.composio.dev

---

**Next Steps:**

1. ✅ Composio installed and Notion linked
2. ✅ Python client implemented (`aos/integrations/composio_notion.py`)
3. ✅ Skill doc authored
4. ⏳ Wire into Netso harness for execution logging
5. ⏳ Set up deal pipeline sync from `ROADMAP.md`
