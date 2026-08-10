#!/usr/bin/env bash
# approve.sh — Interactive approval review for AOS
# Usage: bash ops/approve.sh [approve-all|reject-all|list]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"
source .venv/bin/activate

ACTION="${1:-list}"

echo "=== AOS Approval Review ==="
echo ""

case "$ACTION" in
    list)
        python -m aos approvals list
        ;;
    approve-all)
        echo "Approving all pending approvals..."
        read -p "Add a note? (optional): " NOTE
        if [[ -n "$NOTE" ]]; then
            python -m aos approvals approve-all --note "$NOTE"
        else
            python -m aos approvals approve-all
        fi
        echo ""
        echo "✅ All approvals processed"
        ;;
    reject-all)
        echo "Rejecting all pending approvals..."
        read -p "Rejection reason: " REASON
        if [[ -n "$REASON" ]]; then
            python -m aos approvals reject-all --note "$REASON"
        else
            python -m aos approvals reject-all
        fi
        echo ""
        echo "❌ All approvals rejected"
        ;;
    approve)
        read -p "Approval ID (e.g., APR-0001): " ITEM_ID
        read -p "Add a note? (optional): " NOTE
        if [[ -n "$NOTE" ]]; then
            python -m aos approvals approve "$ITEM_ID" --note "$NOTE"
        else
            python -m aos approvals approve "$ITEM_ID"
        fi
        ;;
    reject)
        read -p "Approval ID (e.g., APR-0001): " ITEM_ID
        read -p "Rejection reason: " REASON
        if [[ -n "$REASON" ]]; then
            python -m aos approvals reject "$ITEM_ID" --note "$REASON"
        else
            python -m aos approvals reject "$ITEM_ID"
        fi
        ;;
    *)
        echo "Usage: bash ops/approve.sh [list|approve-all|reject-all|approve|reject]"
        echo ""
        echo "Commands:"
        echo "   list         Show pending approvals (default)"
        echo "   approve-all  Approve all pending approvals"
        echo "   reject-all   Reject all pending approvals"
        echo "   approve      Approve a specific item by ID"
        echo "   reject       Reject a specific item by ID"
        exit 1
        ;;
esac
