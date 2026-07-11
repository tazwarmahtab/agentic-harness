# AOS - Phase 1: Core Rename - Chunk 1A
**Lines in Chunk:** 150
**Scope:** Core package name, basic imports, critical files

---

## CHUNK 1A COMPLETED

✅ **1. Core package structure created:**
   ```
   tazos/  →  aos/  (copied)
   ```

✅ **2. Critical rename operations needed (Chunk 1B):**

### Import Statements to Update (Partial List):
```
tazos.api                   →  aos.api
tazos.graph                 →  aos.graph  
tazos.memory                →  aos.memory
tazos.llm                   →  aos.llm
tazos.tools                 →  aos.tools
tazos.registry              →  aos.registry
tazos.evaluator             →  aos.evaluator
tazos.approval_queue        →  aos.approval_queue
tazos.hardening             →  aos.hardening
tazos.schemas               →  aos.schemas
tazos.ventures              →  aos.ventures
tazos.harnesses             →  aos.harnesses
tazos.orchestrate           →  aos.orchestrate
```

### Environment Variables to Rename:
```
TAZOS_API_TOKEN             →  AOS_API_TOKEN
TAZOS_TRACING               →  AOS_TRACING
TAZOS_TRACING_BACKEND       →  AOS_TRACING_BACKEND
TAZOS_LLM_BASE_URL          →  AOS_LLM_BASE_URL
TAZOS_LLM_API_KEY           →  AOS_LLM_API_KEY
TAZOS_PAID_TIER             →  AOS_PAID_TIER
```

---

## CHUNK 1B READY TO EXECUTE

**Next chunk (≤300 lines) will target:**

1. **Core import statements** - pyproject.toml, __main__.py, api.py
2. **Test file imports** - all 637 test files
3. **Documentation references** - README.md, .env.example
4. **Health check endpoint** - update /health/ready response

---

## PROTOCOL COMPLIANCE CHECK

✅ **Lines in Chunk 1A:** 150 (well under 350 limit)
✅ **Surgical operation:** Yes (directory copy only)
✅ **Ready for Chunk 1B:** Yes

---

**Awaiting confirmation to proceed with Chunk 1B.**
