#!/bin/bash
# AOS Health Check Script
# Used by monitoring systems and load balancers

set -euo pipefail

AOS_API_TOKEN="${AOS_API_TOKEN:-}"
AOS_BASE_URL="${AOS_BASE_URL:-http://localhost:7001}"

usage() {
    echo "Usage: $0 [liveness|readiness|ws-stats]"
    echo "  liveness   - Basic health check (process alive)"
    echo "  readiness  - Full readiness (includes LLM provider)"
    echo "  ws-stats   - WebSocket connection stats (requires AOS_API_TOKEN)"
    exit 1
}

check_liveness() {
    curl -sf "$AOS_BASE_URL/health" | jq -e '.status == "ok"' >/dev/null
}

check_readiness() {
    curl -sf "$AOS_BASE_URL/health/ready" | jq -e '.status == "ok"' >/dev/null
}

check_ws_stats() {
    if [[ -z "$AOS_API_TOKEN" ]]; then
        echo "AOS_API_TOKEN not set"
        return 1
    fi
    curl -sf -H "Authorization: Bearer $AOS_API_TOKEN" "$AOS_BASE_URL/api/ws/stats" | jq -e '.connected >= 0' >/dev/null
}

case "${1:-}" in
    liveness)
        check_liveness && echo "OK" || exit 1
        ;;
    readiness)
        check_readiness && echo "OK" || exit 1
        ;;
    ws-stats)
        check_ws_stats && echo "OK" || exit 1
        ;;
    *)
        usage
        ;;
esac