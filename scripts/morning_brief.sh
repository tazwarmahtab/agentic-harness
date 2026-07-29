#!/bin/bash
# scripts/morning_brief.sh — Run morning brief and send via Telegram
cd "$(dirname "$0")/.."
source .venv/bin/activate
export PYTHONPATH="."
.venv/bin/python -c "
import sys
sys.path[:] = [p for p in sys.path if 'hermes-agent/venv' not in p]
from aos.morning_brief import generate_brief, send_brief_telegram
brief = generate_brief(venture='netso')
print(brief)
send_brief_telegram(brief)
"
