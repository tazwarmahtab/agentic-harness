from __future__ import annotations

import os
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
COMPANY = ROOT / "companies" / "netso-energy"


def test_paperclip_company_has_runtime_config() -> None:
    config = yaml.safe_load((COMPANY / ".paperclip.yaml").read_text())
    assert set(config["agents"]) == {"ceo", "cfo", "coo", "cro", "cto", "legal"}
    for slug, spec in config["agents"].items():
        adapter = spec["adapter"]
        assert adapter["type"] == "process"
        assert adapter["config"]["command"] == "python3"
        assert adapter["config"]["args"] == ["-m", "aos.paperclip_agent"]
        assert adapter["config"]["timeoutSec"] <= 900
        assert spec["budgetMonthlyCents"] > 0


def test_paperclip_agent_imports_without_runtime_side_effects() -> None:
    import aos.paperclip_agent as entrypoint

    assert entrypoint.AGENT_MAP["ceo"] == "AGT-EXEC-CEO"
    assert entrypoint.AGENT_MAP["cfo"] == "AGT-EXEC-CFO"


def test_task_input_prefers_stdin(monkeypatch) -> None:
    import aos.paperclip_agent as entrypoint

    monkeypatch.setenv("PAPERCLIP_TASK_PROMPT", "fallback")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert entrypoint._task_input() == "fallback"
