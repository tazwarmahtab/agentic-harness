from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from aos.integrations.paperclip import PaperclipClient, PaperclipConfig, PaperclipError


def test_config_requires_all_environment_values(monkeypatch):
    monkeypatch.delenv("PAPERCLIP_API_URL", raising=False)
    monkeypatch.delenv("PAPERCLIP_API_KEY", raising=False)
    monkeypatch.delenv("PAPERCLIP_COMPANY_ID", raising=False)

    with pytest.raises(PaperclipError, match="Missing Paperclip configuration"):
        PaperclipConfig.from_env()


def test_create_issue_sends_governed_payload_without_secret_logging():
    config = PaperclipConfig(
        base_url="https://paperclip.example",
        api_key="secret-token",
        company_id="company-1",
    )
    client = PaperclipClient(config)

    response = MagicMock()
    response.read.return_value = json.dumps({"id": "issue-1"}).encode()
    response.__enter__.return_value = response
    response.__exit__.return_value = None

    with patch("aos.integrations.paperclip.urlopen", return_value=response) as mocked:
        result = client.create_issue(
            title="Review CGS financing readiness",
            description="Validate current evidence and prepare founder decision.",
            priority="high",
            assignee_agent_id="cfo",
        )

    assert result == {"id": "issue-1"}
    request = mocked.call_args.args[0]
    assert request.method == "POST"
    assert request.full_url.endswith("/api/companies/company-1/issues")
    assert request.get_header("Authorization") == "Bearer secret-token"
    payload = json.loads(request.data.decode())
    assert payload == {
        "title": "Review CGS financing readiness",
        "description": "Validate current evidence and prepare founder decision.",
        "status": "todo",
        "priority": "high",
        "assigneeAgentId": "cfo",
    }


def test_update_issue_can_send_run_identity():
    config = PaperclipConfig(
        base_url="https://paperclip.example",
        api_key="secret-token",
        company_id="company-1",
    )
    client = PaperclipClient(config)

    response = MagicMock()
    response.read.return_value = b'{"id":"issue-1","status":"done"}'
    response.__enter__.return_value = response
    response.__exit__.return_value = None

    with patch("aos.integrations.paperclip.urlopen", return_value=response) as mocked:
        result = client.update_issue(
            "issue-1",
            status="done",
            comment="Evidence verified; work complete.",
            run_id="run-42",
        )

    assert result["status"] == "done"
    request = mocked.call_args.args[0]
    assert request.method == "PATCH"
    assert request.get_header("X-paperclip-run-id") == "run-42"
    payload = json.loads(request.data.decode())
    assert payload == {
        "status": "done",
        "comment": "Evidence verified; work complete.",
    }
