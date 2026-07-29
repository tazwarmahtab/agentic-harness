"""Sys-path cleanup utility for environments where hermes-agent venv leaks into sys.path."""
from __future__ import annotations
import sys

def clean_sys_path() -> None:
    """Remove hermes-agent venv site-packages from sys.path if present."""
    sys.path[:] = [p for p in sys.path if "hermes-agent/venv" not in p]

# Auto-clean on import if hermes paths are detected
if any("hermes-agent/venv" in p for p in sys.path):
    clean_sys_path()
