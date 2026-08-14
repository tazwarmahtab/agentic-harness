"""Small, dependency-free Paperclip control-plane client.

This module deliberately does not embed Paperclip business logic. It provides
only the minimum outbound contract needed by AOS to publish work outcomes and
create control-plane work items. Authentication is bearer-token based and no
secret is ever logged.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class PaperclipError(RuntimeError):
    """Raised when a Paperclip request cannot be completed safely."""


@dataclass(frozen=True)
class PaperclipConfig:
    base_url: str
    api_key: str
    company_id: str
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> "PaperclipConfig":
        base_url = os.getenv("PAPERCLIP_API_URL", "").rstrip("/")
        api_key = os.getenv("PAPERCLIP_API_KEY", "")
        company_id = os.getenv("PAPERCLIP_COMPANY_ID", "")
        missing = [
            name
            for name, value in (
                ("PAPERCLIP_API_URL", base_url),
                ("PAPERCLIP_API_KEY", api_key),
                ("PAPERCLIP_COMPANY_ID", company_id),
            )
            if not value
        ]
        if missing:
            raise PaperclipError(f"Missing Paperclip configuration: {', '.join(missing)}")
        return cls(base_url=base_url, api_key=api_key, company_id=company_id)


class PaperclipClient:
    """Minimal Paperclip API client for governed AOS integration."""

    def __init__(self, config: PaperclipConfig):
        self.config = config

    def _request(
        self,
        method: str,
        path: str,
        payload: dict | None = None,
        *,
        run_id: str | None = None,
    ) -> dict:
        url = f"{self.config.base_url}{path}"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Accept": "application/json",
        }
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        if run_id:
            headers["X-Paperclip-Run-Id"] = run_id

        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            # Never expose headers or secrets in the exception text.
            raise PaperclipError(f"Paperclip {method} {path} failed: HTTP {exc.code}") from exc
        except URLError as exc:
            raise PaperclipError(f"Paperclip {method} {path} failed: network error") from exc

        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise PaperclipError(f"Paperclip returned non-JSON data for {method} {path}") from exc
        if not isinstance(data, dict):
            raise PaperclipError(f"Paperclip returned unexpected JSON for {method} {path}")
        return data

    def list_issues(self, *, status: str | None = None) -> dict:
        path = f"/api/companies/{self.config.company_id}/issues"
        if status:
            path = f"{path}?status={status}"
        return self._request("GET", path)

    def create_issue(
        self,
        *,
        title: str,
        description: str,
        priority: str = "medium",
        assignee_agent_id: str | None = None,
        project_id: str | None = None,
        goal_id: str | None = None,
        parent_id: str | None = None,
    ) -> dict:
        payload = {
            "title": title,
            "description": description,
            "status": "todo",
            "priority": priority,
        }
        optional_fields = {
            "assigneeAgentId": assignee_agent_id,
            "projectId": project_id,
            "goalId": goal_id,
            "parentId": parent_id,
        }
        payload.update({k: v for k, v in optional_fields.items() if v})
        return self._request(
            "POST",
            f"/api/companies/{self.config.company_id}/issues",
            payload,
        )

    def update_issue(
        self,
        issue_id: str,
        *,
        status: str | None = None,
        comment: str | None = None,
        run_id: str | None = None,
    ) -> dict:
        payload = {k: v for k, v in {"status": status, "comment": comment}.items() if v is not None}
        return self._request("PATCH", f"/api/issues/{issue_id}", payload, run_id=run_id)


def build_client_from_env() -> PaperclipClient:
    """Build a client from environment variables; fail closed if incomplete."""
    return PaperclipClient(PaperclipConfig.from_env())
