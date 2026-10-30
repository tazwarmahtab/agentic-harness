import base64

import pytest
from fastapi.testclient import TestClient

from aos.api import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AOS_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("AOS_API_TOKEN", "synthetic-test-token")
    return TestClient(app, headers={"Authorization": "Bearer synthetic-test-token"})


def payload():
    return {
        "venture": "netso",
        "project": "demo",
        "prospect": "Synthetic Factory",
        "purpose": "Discovery",
        "documents": [
            {
                "filename": "notes.txt",
                "content_b64": base64.b64encode(
                    b"Buyer: Synthetic Person\n<script>alert(1)</script>"
                ).decode(),
            }
        ],
    }


def test_full_http_workflow(client):
    created = client.post("/api/prospects", json=payload())
    assert created.status_code == 201
    job = created.json()
    url = "/api/prospects/" + job["id"]
    params = {"venture": "netso", "project": "demo"}
    result = client.post(url + "/generate", params=params, json={})
    assert result.status_code == 200
    output = result.json()
    assert output["output"]["facts"][0]["quote"] == "Buyer: Synthetic Person"
    source = client.get(url + "/sources/" + job["sources"][0]["id"], params=params)
    assert source.status_code == 200
    assert source.content == b"Buyer: Synthetic Person\n<script>alert(1)</script>"
    review = client.post(
        url + "/review",
        params=params,
        json={"output_hash": output["output_hash"], "decision": "approve"},
    )
    assert review.status_code == 200
    assert review.json()["send_authorized"] is False
    assert client.get(url, params=params).json()["status"] == "approved"
    assert len(client.get(url + "/events", params=params).json()) == 4


def test_strict_auth_even_when_legacy_local_dev_is_open(client, monkeypatch):
    monkeypatch.delenv("AOS_API_TOKEN")
    monkeypatch.delenv("TAZOS_API_TOKEN", raising=False)
    assert (
        client.get(
            "/api/prospects", params={"venture": "netso", "project": "demo"}
        ).status_code
        == 503
    )


def test_source_and_jobs_require_token_and_matching_scope(client):
    job = client.post("/api/prospects", json=payload()).json()
    url = "/api/prospects/" + job["id"]
    assert (
        client.get(url, params={"venture": "wrong", "project": "demo"}).status_code
        == 404
    )
    assert (
        client.get(
            url,
            params={"venture": "netso", "project": "demo"},
            headers={"Authorization": "Bearer bad"},
        ).status_code
        == 401
    )
    assert (
        client.get(
            url + "/sources/" + job["sources"][0]["id"],
            params={"venture": "wrong", "project": "demo"},
        ).status_code
        == 404
    )


def test_model_disclosure_requires_both_gates(client, monkeypatch):
    job = client.post("/api/prospects", json=payload()).json()
    url = "/api/prospects/" + job["id"] + "/generate?venture=netso&project=demo"
    assert (
        client.post(
            url, json={"use_model": True, "allow_model_disclosure": True}
        ).status_code
        == 403
    )
    monkeypatch.setenv("AOS_PROSPECT_MODEL_ENABLED", "1")
    assert client.post(url, json={"use_model": True}).status_code == 403


def test_bad_data_and_stale_review_return_controlled_errors(client):
    bad = payload()
    bad["documents"][0]["content_b64"] = "!bad!"
    assert client.post("/api/prospects", json=bad).status_code == 422
    job = client.post("/api/prospects", json=payload()).json()
    url = "/api/prospects/" + job["id"]
    params = {"venture": "netso", "project": "demo"}
    assert (
        client.post(
            url + "/review",
            params=params,
            json={"output_hash": "stale", "decision": "approve"},
        ).status_code
        == 409
    )


def test_actual_dashboard_assets_and_live_entrypoint():
    from odysseus.server import app as dashboard

    c = TestClient(dashboard)
    html = c.get("/")
    assert html.status_code == 200
    assert "/static/" in html.text
    assert "preview-api.js" not in html.text
    assert c.get("/static/pages/prospects.js").status_code == 200


def test_edit_and_versions_http(client):
    job = client.post("/api/prospects", json=payload()).json()
    url = "/api/prospects/" + job["id"]
    params = {"venture": "netso", "project": "demo"}
    generated = client.post(url + "/generate", params=params, json={}).json()
    changed = client.patch(
        url + "/draft",
        params=params,
        json={"output_hash": generated["output_hash"], "text": "Human draft"},
    ).json()
    assert changed["status"] == "needs_review"
    assert len(client.get(url + "/versions", params=params).json()) == 2


def test_body_size_limit_including_chunked(client):
    response = client.post(
        "/api/prospects",
        content=(b"x" * (1024 * 1024) for _ in range(16)),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_dashboard_proxy_rejects_oversized_body_before_upstream():
    from odysseus.server import app as dashboard

    c = TestClient(dashboard)
    response = c.post(
        "/api/prospects", content=(b"x" * (1024 * 1024) for _ in range(16))
    )
    assert response.status_code == 413


def test_enabled_model_selects_exact_evidence_without_real_provider(
    client, monkeypatch
):
    import json

    from aos.llm import LLMResponse

    class FakeModel:
        def complete(self, **kwargs):
            sources = json.loads(kwargs["messages"][0]["content"])
            source = sources[0]
            return LLMResponse(
                content=json.dumps(
                    {
                        "facts": [
                            {
                                "source_id": source["source_id"],
                                "page": source["page"],
                                "quote": source["text"],
                                "topic": "buyer",
                            }
                        ]
                    }
                ),
                model="test-only",
            )

    monkeypatch.setenv("AOS_PROSPECT_MODEL_ENABLED", "1")
    monkeypatch.setattr("aos.llm.create_llm_client", lambda: FakeModel())
    job = client.post("/api/prospects", json=payload()).json()
    response = client.post(
        "/api/prospects/" + job["id"] + "/generate?venture=netso&project=demo",
        json={"use_model": True, "allow_model_disclosure": True},
    )
    assert response.status_code == 200
    assert response.json()["mode"] == "model_selected"
    assert response.json()["output"]["facts"][0]["topic"] == "buyer"
