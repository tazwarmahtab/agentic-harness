#!/usr/bin/env bash
# install-service.sh — Install AOS daily service via launchd
# Usage: bash ops/install-service.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PLIST_SRC="$SCRIPT_DIR/com.aos.daily.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.aos.daily.plist"
LOGS_DIR="$REPO_ROOT/logs"

echo "=== AOS Service Installer ==="
echo ""

# Create logs directory
mkdir -p "$LOGS_DIR"
echo "Created logs directory: $LOGS_DIR"

# Unload existing service if running
if launchctl list | grep -q "com.aos.daily"; then
    echo "Unloading existing service..."
    launchctl unload "$PLIST_DST" 2>/dev/null || true
fi

# Copy plist
cp "$PLIST_SRC" "$PLIST_DST"
echo "Installed plist to: $PLIST_DST"

# Load service
launchctl load "$PLIST_DST"
echo "Loaded service: com.aos.daily"

# Verify
if launchctl list | grep -q "com.aos.daily"; then
    echo ""
    echo "✅ Service installed and running"
    echo "   Schedule: Daily at 09:00 BDT"
    echo "   Logs: $LOGS_DIR/"
    echo ""
    echo "Commands:"
    echo "   Check status: launchctl list | grep aos"
    echo "   Stop service: launchctl unload $PLIST_DST"
    echo "   Start service: launchctl load $PLIST_DST"
    echo "   View logs: tail -f $LOGS_DIR/aos-stdout.log"
else
    echo ""
    echo "⚠️  Service installed but may not be running"
    echo "   Check: launchctl list | grep aos"
fi
