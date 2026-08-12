# AOS Integrations

External service integrations for AOS harnesses and skills.

## Active Integrations

### Composio Notion

**Status:** ✅ Production Ready  
**Auth:** OAuth2 (linked 2026-06-14)  
**Location:** `aos/integrations/composio_notion.py`  
**Docs:** [COMPOSIO_NOTION.md](./COMPOSIO_NOTION.md)  
**Skill:** `.hermes/skills/productivity/composio-notion/`

**Use Cases:**
- Harness execution logging
- Deal pipeline sync from ROADMAP.md
- Weekly status reports
- Meeting notes capture

**Quick Start:**
```python
from aos.integrations.composio_notion import ComposioNotionClient

client = ComposioNotionClient()
result = client.create_page(
    parent_id="PAGE_ID",
    title="Log Entry",
    markdown="# Content"
)
```

**Verified Operations:**
- ✅ Search pages (tested 2026-08-12)
- ✅ Create pages with markdown (tested 2026-08-12)
- ⏳ Query databases
- ⏳ Insert database rows

---

## Integration Architecture

```
Harness/Skill
    ↓
Python Client (aos/integrations/)
    ↓
External CLI/API
    ↓
Service (Notion, GitHub, etc.)
```

**Design Principles:**
1. **Stateless auth** — OAuth/tokens managed by external tool (Composio, gh CLI)
2. **Subprocess isolation** — CLI calls via subprocess, not SDKs
3. **Result wrapping** — Typed dataclasses for success/error/data
4. **Convenience functions** — Top-level shortcuts for skills
5. **Fail-fast** — RuntimeError on auth/network failures

---

## Adding New Integrations

1. **Auth:** Use existing CLI tools (composio, gh, etc.) — don't manage tokens in AOS
2. **Client:** Create `aos/integrations/<service>.py` with typed client class
3. **Skill:** Document in `.hermes/skills/<category>/<service>/`
4. **Test:** Verify auth + one read + one write operation
5. **Doc:** Add entry to this README + detailed doc in `docs/integrations/`

**Template:**
```python
# aos/integrations/service_name.py
from dataclasses import dataclass
import subprocess, json

@dataclass
class ServiceResult:
    successful: bool
    data: dict | None
    error: str | None

class ServiceClient:
    def _execute(self, command: list) -> ServiceResult:
        result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        # parse and wrap
        
    def operation(self, param: str) -> ServiceResult:
        return self._execute(["cli", "operation", param])
```

---

## Future Integrations

- GitHub (via `gh` CLI) — issue/PR management
- Telegram (via `tdlib` or HTTP API) — notification delivery
- Airtable (via Composio or direct API) — structured data
- Google Sheets (via Composio) — financial model sync
