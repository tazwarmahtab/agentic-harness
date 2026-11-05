"""Restricted pilot entry must not expose legacy execution routes."""

import importlib.util

import pytest
from fastapi.testclient import TestClient


def pilot_client(monkeypatch, tmp_path):
    assert importlib.util.find_spec("aos.pilot") is not None, (
        "restricted pilot entry missing"
    )
    from aos.pilot import app

    monkeypatch.setenv("AOS_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("AOS_API_TOKEN", "synthetic-boundary-token")
    monkeypatch.delenv("TAZOS_API_TOKEN", raising=False)
    return TestClient(app)


@pytest.mark.parametrize(
    "path", ["/api/execute", "/api/harnesses", "/api/ws", "/docs", "/openapi.json"]
)
def test_legacy_and_schema_routes_are_absent(monkeypatch, tmp_path, path):
    client = pilot_client(monkeypatch, tmp_path)
    assert client.get(path).status_code == 404
    assert client.post(path, json={}).status_code == 404


def test_pilot_requires_configured_auth(monkeypatch, tmp_path):
    client = pilot_client(monkeypatch, tmp_path)
    params = {"venture": "infrastructure", "project": "pilot"}
    assert client.get("/api/prospects", params=params).status_code == 401
    assert (
        client.get(
            "/api/prospects", params=params, headers={"Authorization": "Bearer wrong"}
        ).status_code
        == 401
    )
    monkeypatch.delenv("AOS_API_TOKEN")
    assert client.get("/api/prospects", params=params).status_code == 503


def test_pilot_exposes_only_document_routes(monkeypatch, tmp_path):
    client = pilot_client(monkeypatch, tmp_path)
    assert all(
        path.startswith("/api/prospects") for path in client.app.openapi()["paths"]
    )
    response = client.get(
        "/api/prospects",
        params={"venture": "infrastructure", "project": "pilot"},
        headers={"Authorization": "Bearer synthetic-boundary-token"},
    )
    assert response.status_code == 200
    assert response.json() == []
