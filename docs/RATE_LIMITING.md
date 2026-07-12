# AOS Rate Limiting Configuration

**Last Updated:** 2026-07-11  
**Version:** 1.0

## Overview

AOS implements two types of rate limiting to protect system resources and ensure fair usage:
1. **ConnectionLimiter** — Caps concurrent WebSocket connections
2. **RateLimiter** — Token-bucket rate limiting for API/tool calls

---

## ConnectionLimiter (WebSocket)

### Purpose
Prevents resource exhaustion from too many simultaneous WebSocket connections.

### Default Configuration

```python
# In tazos/api.py
_ws_limiter = ConnectionLimiter(max_connections=10)
```

**Default:** 10 concurrent connections

### Behavior

| Scenario | Action |
|----------|--------|
| New connection < 10 | Accept |
| New connection ≥ 10 | Reject with 503 error |
| Connection closes | Slot released immediately |

### Monitoring

```bash
# Check current connection count
curl http://localhost:8000/api/ws/stats

# Response:
{
  "active_connections": 3,
  "max_connections": 10,
  "available_slots": 7
}
```

### Configuration

To change the limit, edit `tazos/api.py`:

```python
# Increase to 20 connections
_ws_limiter = ConnectionLimiter(max_connections=20)
```

**Recommendations:**
- Development: 10 connections (default)
- Production: 20-50 connections (depending on server resources)
- High-traffic production: 100+ connections (with proper load balancing)

---

## RateLimiter (API/Tool Calls)

### Purpose
Prevents API abuse and ensures fair resource allocation per agent.

### Default Configuration

```python
# In tazos/hardening.py
class RateLimiter:
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
```

**Default:** 60 requests per 60 seconds (1 request/second average)

### Sliding Window Algorithm

The rate limiter uses a **sliding window** approach:
- Tracks timestamps of all requests in the last `window_seconds`
- New request allowed if `len(timestamps) < max_requests`
- Old timestamps automatically evicted

### Usage in Tools

Tools can define custom rate limits in `tools.yml`:

```yaml
# Example: tazos/harnesses/executive/tools.yml
tools:
  - id: TOL-API-CRM
    name: CRM API Access
    capability: read_crm
    rate_limit: 30  # 30 requests per hour
```

### Behavior

| Request Type | Action |
|--------------|--------|
| Within limit | Allow |
| Over limit | Return `status: "rate_limited"` |
| Window expires | Counter resets |

### Implementation Example

```python
from tazos.hardening import RateLimiter

# Create limiter: 100 requests per minute
limiter = RateLimiter(max_requests=100, window_seconds=60)

# Check if allowed
if limiter.allow("agent-123"):
    # Execute request
    pass
else:
    # Return rate limit error
    return ToolResult(
        status="rate_limited",
        error="Rate limit exceeded: 100 requests/minute"
    )
```

---

## Tool-Specific Rate Limits

Tools defined in `tools.yml` can have custom rate limits:

| Tool | Default Limit | Reason |
|------|---------------|--------|
| `read_dashboard` | None | Internal, low cost |
| `read_crm` | 30/hour | External API quota |
| `read_email` | 100/hour | External API quota |
| `write_handoff` | None | Internal, high volume OK |
| `trigger_agent` | 10/minute | Prevent infinite loops |

### Configuring Tool Rate Limits

Edit `tazos/harnesses/<harness>/tools.yml`:

```yaml
tools:
  - id: TOL-EMAIL-READ
    name: Email Reader
    capability: read_email
    rate_limit: 100  # requests per hour
```

---

## Monitoring Rate Limits

### Check Rate Limit Status

```python
# In tool execution
from tazos.hardening import RateLimiter

# Get current usage
usage = limiter.current_usage("agent-123")
remaining = limiter.remaining("agent-123")

print(f"Usage: {usage}/{max_requests}")
print(f"Remaining: {remaining}")
```

### Logging Rate Limit Events

Rate-limited requests are logged:

```
WARNING: Rate limit exceeded for agent AGT-EXEC-CFO on tool read_crm
INFO: Agent AGT-EXEC-COO rate limited, retrying in 30s
```

---

## Best Practices

### For Developers

1. **Set conservative defaults** — Better to start low and increase
2. **Document external quotas** — Note if tool calls external API with hard limits
3. **Use different limits per tool type** — Internal tools can have higher limits
4. **Monitor in production** — Watch for rate limit warnings in logs

### For Operators

1. **Monitor `/api/ws/stats`** — Track WebSocket connection usage
2. **Adjust for load** — Increase limits during high-traffic periods
3. **Set alerts** — Alert if connections approach 80% of max
4. **Load test** — Verify limits under realistic traffic

---

## Configuration Checklist

### Development Environment

- [ ] ConnectionLimiter: 10 connections (default)
- [ ] RateLimiter: 60 requests/minute (default)
- [ ] Tool rate limits: As defined in tools.yml

### Production Environment

- [ ] ConnectionLimiter: Increase to 20-50 based on server capacity
- [ ] RateLimiter: Adjust based on external API quotas
- [ ] Add monitoring for rate limit events
- [ ] Set up alerts for connection exhaustion
- [ ] Document any custom limits

---

## Troubleshooting

### Issue: "Rate limit exceeded" errors

**Causes:**
- Agent making too many requests too quickly
- External API quota exceeded
- Misconfigured rate limit in tools.yml

**Solutions:**
1. Check agent behavior (is it in a loop?)
2. Verify external API quota
3. Adjust `rate_limit` in tools.yml if appropriate

### Issue: "Connection limit reached" (WebSocket 503)

**Causes:**
- Too many concurrent connections
- Connections not closing properly
- Memory leak in connection handler

**Solutions:**
1. Increase `max_connections` in api.py
2. Check for zombie connections (restart server)
3. Monitor `/api/ws/stats` endpoint

### Issue: Requests succeed locally but fail in production

**Causes:**
- Production has stricter rate limits
- Shared rate limit across multiple instances
- External API production quota lower

**Solutions:**
1. Document production limits clearly
2. Use environment-specific configuration
3. Implement retry with exponential backoff

---

## Related Documentation

- Hardening Module: `tazos/hardening.py`
- Tools Configuration: `tazos/harnesses/<harness>/tools.yml`
- API Endpoints: `tazos/api.py`
- WebSocket Handler: `tazos/api.py` (WebSocket endpoints)

