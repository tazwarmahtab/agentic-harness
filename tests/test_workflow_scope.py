"""Keep domain-specific GitHub Actions off unrelated Agent Harness changes."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOMAIN_FILES = {
    "companies/netso-energy/**",
    "scripts/validate_netso_company.py",
    "aos/integrations/paperclip.py",
    "aos/integrations/paperclip_runtime.py",
    "aos/paperclip_agent.py",
    "tests/test_paperclip_integration.py",
    "pyproject.toml",
    "uv.lock",
}


def test_netso_workflow_triggers_are_domain_scoped():
    for filename in ("netso-ai-company.yml", "netso-ai-company-smoke.yml"):
        data = yaml.load(
            (ROOT / ".github" / "workflows" / filename).read_text(),
            Loader=yaml.BaseLoader,
        )
        triggers = data["on"]
        assert "workflow_dispatch" in triggers, "retain manual verification path"
        for event in ("pull_request", "push"):
            if event not in triggers:
                continue
            event_config = triggers[event]
            paths = set(event_config.get("paths", []))
            assert DOMAIN_FILES.issubset(paths), f"missing relevant Netso paths in {filename}"
            assert "*" not in paths and "**" not in paths and "aos/**" not in paths
            assert "docs/**" not in paths
            assert f".github/workflows/{filename}" in paths
