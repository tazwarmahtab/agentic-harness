from __future__ import annotations

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

    assert entrypoint.AGENT_MAP == {
        "ceo": "AGT-EXEC-CEO",
        "cfo": "AGT-EXEC-CFO",
        "coo": "AGT-EXEC-COO",
        "cro": "AGT-EXEC-CRO",
        "cto": "AGT-EXEC-CTO",
        "legal": "AGT-EXEC-LEG",
    }

    source = (ROOT / "aos" / "paperclip_agent.py").read_text()
    assert "GovernedToolGateway" in source
    assert "from aos.tools import ToolGateway" not in source


def test_task_input_prefers_environment_when_not_interactive(monkeypatch) -> None:
    import aos.paperclip_agent as entrypoint

    monkeypatch.setenv("PAPERCLIP_TASK_PROMPT", "fallback")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    assert entrypoint._task_input() == "fallback"


def test_declared_tool_calls_use_governed_gateway():
    import aos.paperclip_agent as entrypoint

    class FakeResult:
        def __init__(self, status: str):
            self.status = status
            self.output = {"status": status}
            self.error = "blocked" if status == "denied" else None
            self.approval_required = status == "denied"
            self.approval_id = None

    class FakeGateway:
        def __init__(self):
            self.calls = []

        def call(self, capability, inputs, agent_id):
            self.calls.append((capability, inputs, agent_id))
            return FakeResult(
                "denied"
                if inputs.get("_action_class") == "money_movement"
                else "success"
            )

    gateway = FakeGateway()
    result = entrypoint.execute_declared_tool_calls(
        gateway,
        {
            "tool_calls": [
                {
                    "capability": "internal_task",
                    "inputs": {"_action_class": "money_movement"},
                },
                {
                    "capability": "internal_task",
                    "inputs": {"note": "safe internal work"},
                },
            ]
        },
        agent_id="AGT-EXEC-CEO",
    )

    assert len(gateway.calls) == 2
    assert result[0]["status"] == "denied"
    assert result[1]["status"] == "success"
