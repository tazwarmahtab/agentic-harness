#!/bin/bash
# scripts/morning_brief.sh — Run morning brief and send via Telegram
# Handles .env loading, path cleanup, and error reporting.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
ENV_FILE="$PROJECT_DIR/.env"
LOG_FILE="$HOME/aos-brief.log"

# Validate prerequisites
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Python venv not found at $VENV_PYTHON" >> "$LOG_FILE"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: .env file not found at $ENV_FILE" >> "$LOG_FILE"
    exit 1
fi

# Run the morning brief
cd "$PROJECT_DIR"
"$VENV_PYTHON" -c "
import sys, os

# Remove hermes venv paths that cause pydantic conflicts
sys.path[:] = [p for p in sys.path if 'hermes-agent/venv' not in p]

# Load .env file
env_file = '$ENV_FILE'
with open(env_file) as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            key, val = line.split('=', 1)
            os.environ[key.strip()] = val.strip()

from aos.morning_brief import generate_brief, send_brief_telegram
brief = generate_brief('netso')
print(brief)
send_brief_telegram(brief)
"
