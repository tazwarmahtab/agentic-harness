"""Tests for Mission Control Dashboard Phase 1 endpoints."""

from __future__ import annotations

import os
from pathlib import Path

from starlette.testclient import TestClient

# Patch env before importing app so auth is disabled
# This must happen before the module is imported
os.environ["AOS_API_TOKEN"] = ""
os.environ["TAZOS_API_TOKEN"] = ""

from aos.api import app  # noqa: E402


def _seed_approval_queue() -> str:
    """Seed the approval queue with a test item. Returns the item ID."""
    from aos.approval_queue import ApprovalQueue

    queue_path = Path(__file__).resolve().parent.parent / "aos" / "approvals.jsonl"
    queue = ApprovalQueue(persistence_path=queue_path)
    item = queue.add(
        agent_id="AGT-EXEC-CEO",
        action="test approval for dashboard tests",
        rationale="Seeded for testing",
        risk_assessment="low",
    )
    return item.id


class TestPipelineEndpoints:
    """Tests for pipeline status endpoints."""

    def test_pipeline_status_returns_dict(self) -> None:
        """GET /api/pipeline/status should return pipeline status."""
        client = TestClient(app)
        response = client.get("/api/pipeline/status")
        assert response.status_code == 200
        body = response.json()
        assert "active" in body
        assert "current_step" in body
        assert "progress" in body
        assert "total_steps" in body
        assert "completed_steps" in body
        assert isinstance(body["active"], bool)
        assert isinstance(body["progress"], float)

    def test_pipeline_history_returns_list(self) -> None:
        """GET /api/pipeline/history should return history list."""
        client = TestClient(app)
        response = client.get("/api/pipeline/history")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)


class TestApprovalEndpoints:
    """Tests for approval endpoints."""

    def test_list_approvals_returns_list(self) -> None:
        """GET /api/approvals should return list of approvals."""
        client = TestClient(app)
        response = client.get("/api/approvals")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)

    def test_approve_returns_success(self) -> None:
        """POST /api/approvals/{id}/approve should approve request."""
        item_id = _seed_approval_queue()
        client = TestClient(app)
        response = client.post(f"/api/approvals/{item_id}/approve")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == item_id
        assert body["status"] == "approved"

    def test_reject_returns_success(self) -> None:
        """POST /api/approvals/{id}/reject should reject request."""
        item_id = _seed_approval_queue()
        client = TestClient(app)
        response = client.post(f"/api/approvals/{item_id}/reject")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == item_id
        assert body["status"] == "rejected"


class TestSystemStatusEndpoint:
    """Tests for system status endpoint."""

    def test_system_status_returns_health_score(self) -> None:
        """GET /api/system/status should return system health."""
        client = TestClient(app)
        response = client.get("/api/system/status")
        assert response.status_code == 200
        body = response.json()
        assert "health_score" in body
        assert "uptime" in body
        assert "memory_usage_mb" in body
        assert "cpu_usage_percent" in body
        assert "components" in body
        assert isinstance(body["health_score"], float)
        assert isinstance(body["components"], list)

    def test_system_status_components_structure(self) -> None:
        """System status components should have expected structure."""
        client = TestClient(app)
        response = client.get("/api/system/status")
        body = response.json()
        for comp in body["components"]:
            assert "name" in comp
            assert "status" in comp
            assert "details" in comp


class TestAgentsStatusEndpoint:
    """Tests for agents status endpoint."""

    def test_agents_status_returns_list(self) -> None:
        """GET /api/agents should return agents list."""
        client = TestClient(app)
        response = client.get("/api/agents")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, dict)
        assert "total_agents" in body
        assert "active_agents" in body
        assert "agents" in body
        assert isinstance(body["agents"], list)
        if body["agents"]:
            agent = body["agents"][0]
            assert "id" in agent
            assert "name" in agent
            assert "status" in agent


class TestSalesStatusEndpoint:
    """Tests for sales status endpoint."""

    def test_sales_status_returns_data(self) -> None:
        """GET /api/sales/status should return sales data."""
        client = TestClient(app)
        response = client.get("/api/sales/status")
        assert response.status_code == 200
        body = response.json()
        assert "total_customers" in body
        assert "active_deals" in body
        assert "pipeline_value" in body


class TestMemorySummaryEndpoint:
    """Tests for memory summary endpoint."""

    def test_memory_summary_returns_dict(self) -> None:
        """GET /api/memory/summary should return memory stats."""
        client = TestClient(app)
        response = client.get("/api/memory/summary")
        assert response.status_code == 200
        body = response.json()
        assert "total_domains" in body
        assert "total_entries" in body
        assert "domains" in body


class TestDashboardSummaryEndpoint:
    """Tests for dashboard summary endpoint."""

    def test_dashboard_summary_returns_kpis(self) -> None:
        """GET /api/dashboard should return all KPIs."""
        client = TestClient(app)
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        body = response.json()
        assert "harnesses" in body
        assert "pipeline" in body
        assert "memory_domains" in body
        assert "entity_count" in body