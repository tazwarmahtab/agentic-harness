"""Tests for Mission Control Dashboard Phase 1 endpoints."""

from __future__ import annotations

from starlette.testclient import TestClient

from aos.api import app


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
        client = TestClient(app)
        response = client.post("/api/approvals/test-123/approve")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "test-123"
        assert body["status"] == "approved"

    def test_reject_returns_success(self) -> None:
        """POST /api/approvals/{id}/reject should reject request."""
        client = TestClient(app)
        response = client.post("/api/approvals/test-456/reject?reason=no+reason")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == "test-456"
        assert body["status"] == "rejected"


class TestMemoryEndpoints:
    """Tests for memory summary endpoint."""

    def test_memory_summary_returns_dict(self) -> None:
        """GET /api/memory/summary should return memory summary."""
        client = TestClient(app)
        response = client.get("/api/memory/summary")
        assert response.status_code == 200
        body = response.json()
        assert "total_domains" in body
        assert "total_entries" in body
        assert "domains" in body
        assert isinstance(body["total_domains"], int)
        assert isinstance(body["domains"], list)


class TestSalesEndpoints:
    """Tests for sales status endpoint."""

    def test_sales_status_returns_dict(self) -> None:
        """GET /api/sales/status should return sales status."""
        client = TestClient(app)
        response = client.get("/api/sales/status")
        assert response.status_code == 200
        body = response.json()
        assert "total_customers" in body
        assert "active_deals" in body
        assert "pipeline_value" in body
        assert isinstance(body["total_customers"], int)
        assert isinstance(body["pipeline_value"], float)


class TestSystemEndpoints:
    """Tests for system status endpoint."""

    def test_system_status_returns_dict(self) -> None:
        """GET /api/system/status should return system status."""
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


class TestAgentEndpoints:
    """Tests for agents status endpoint."""

    def test_agents_status_returns_dict(self) -> None:
        """GET /api/agents should return agents status."""
        client = TestClient(app)
        response = client.get("/api/agents")
        assert response.status_code == 200
        body = response.json()
        assert "total_agents" in body
        assert "active_agents" in body
        assert "agents" in body
        assert isinstance(body["total_agents"], int)
        assert isinstance(body["agents"], list)


class TestDashboardAggregate:
    """Tests for dashboard aggregate endpoint."""

    def test_dashboard_returns_all_kpis(self) -> None:
        """GET /api/dashboard should return all KPIs."""
        client = TestClient(app)
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        body = response.json()

        # Check all required fields
        assert "harnesses" in body
        assert "tests" in body
        assert "memory_domains" in body
        assert "entity_count" in body
        assert "event_count" in body
        assert "pipeline" in body
        assert "approval_count" in body
        assert "ws_connections" in body
        assert "health_score" in body

        # Check types
        assert isinstance(body["harnesses"], int)
        assert isinstance(body["tests"], int)
        assert isinstance(body["memory_domains"], int)
        assert isinstance(body["entity_count"], int)
        assert isinstance(body["event_count"], int)
        assert isinstance(body["pipeline"], dict)
        assert isinstance(body["approval_count"], int)
        assert isinstance(body["ws_connections"], dict)
        assert isinstance(body["health_score"], float)

        # Check pipeline structure
        pipeline = body["pipeline"]
        assert "active" in pipeline
        assert "progress" in pipeline

        # Check ws_connections structure
        ws = body["ws_connections"]
        assert "active_connections" in ws
        assert "max_connections" in ws

    def test_dashboard_harness_count_positive(self) -> None:
        """Dashboard should report positive harness count."""
        client = TestClient(app)
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        body = response.json()
        assert body["harnesses"] > 0

    def test_dashboard_test_count_positive(self) -> None:
        """Dashboard should report positive test count."""
        client = TestClient(app)
        response = client.get("/api/dashboard")
        assert response.status_code == 200
        body = response.json()
        assert body["tests"] > 0
