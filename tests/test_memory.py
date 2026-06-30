"""Tests for TAZ OS memory system — layers, permissions, candidates, persistence."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tazos.memory import (
    AuditRecord,
    Decision,
    MemoryCandidate,
    MemoryEntry,
    MemoryStore,
    build_memory_from_manifest,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def permissions() -> dict[str, dict[str, list[str]]]:
    return {
        "AGT-EXEC-COO": {
            "read": ["dashboard", "weekly_plan", "backlog", "blockers", "lessons", "decision_log"],
            "write": ["dashboard", "blockers", "lessons"],
            "cannot_read": ["founder_personal_notes", "cap_table"],
        },
        "AGT-EXEC-CFO": {
            "read": ["ground_truth_constants", "financial_models", "decision_log", "dashboard"],
            "write": ["financial_models"],
            "cannot_read": ["founder_personal_notes"],
        },
        "AGT-EXEC-CEO": {
            "read": ["all_long_term", "all_episodic", "all_semantic"],
            "write": ["decision_log"],
            "cannot_read": ["founder_personal_notes"],
        },
    }


@pytest.fixture
def store(permissions: dict) -> MemoryStore:
    return MemoryStore(permissions=permissions)


@pytest.fixture
def manifest() -> dict:
    return {
        "id": "MEM-EXEC-001",
        "name": "Test Memory",
        "harness": "HAR-EXEC-001",
        "version": "1.0.0",
        "layers": {
            "long_term": {
                "company_facts": [
                    {"key": "legal_entity_name", "value": "Netso Energy", "classification": "internal"},
                    {"key": "primary_market", "value": "Bangladesh RMG", "classification": "internal"},
                ],
                "financial_ground_truth": {
                    "ref": "ground_truth_constants",
                    "description": "All financial numbers",
                    "classification": "confidential",
                },
            },
            "episodic": {
                "daily_dashboard": {
                    "ref": "dashboard",
                    "role": "Live state",
                    "write_access": ["AGT-EXEC-COO"],
                    "classification": "internal",
                },
            },
            "semantic": {
                "pricing_model": {
                    "description": "PPA rate methodology",
                    "classification": "confidential",
                },
            },
        },
        "permissions": {
            "AGT-EXEC-COO": {
                "read": ["dashboard", "lessons"],
                "write": ["dashboard", "lessons"],
                "cannot_read": ["founder_personal_notes"],
            },
            "AGT-EXEC-CEO": {
                "read": ["all_long_term", "all_episodic", "all_semantic"],
                "write": ["decision_log"],
                "cannot_read": ["founder_personal_notes"],
            },
        },
        "update_rules": {
            "agents_submit_memory_candidates": True,
            "purpose": "Prevent memory pollution",
        },
    }


# ---------------------------------------------------------------------------
# MemoryStore — seeding
# ---------------------------------------------------------------------------

class TestMemoryStoreSeeding:
    def test_seed_list_entries(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "company_facts", [
            {"key": "entity", "value": "Netso", "classification": "internal"},
        ])
        entries = store.layers["long_term"]["company_facts"]
        assert len(entries) == 1
        assert entries[0].key == "entity"
        assert entries[0].value == "Netso"

    def test_seed_dict_entry(self, store: MemoryStore) -> None:
        store.seed_from_dict("semantic", "pricing", {
            "description": "PPA methodology",
            "classification": "confidential",
        })
        entries = store.layers["semantic"]["pricing"]
        assert len(entries) == 1
        assert entries[0].content == "PPA methodology"
        assert entries[0].classification == "confidential"

    def test_seed_multiple_entries(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "facts", [
            {"key": "a", "value": "1"},
            {"key": "b", "value": "2"},
            {"key": "c", "value": "3"},
        ])
        assert len(store.layers["long_term"]["facts"]) == 3


# ---------------------------------------------------------------------------
# MemoryStore — permissions
# ---------------------------------------------------------------------------

class TestMemoryPermissions:
    def test_coo_can_read_dashboard(self, store: MemoryStore) -> None:
        assert store.can_read("AGT-EXEC-COO", "dashboard") is True

    def test_coo_cannot_read_founder_notes(self, store: MemoryStore) -> None:
        assert store.can_read("AGT-EXEC-COO", "founder_personal_notes") is False

    def test_cfo_can_read_financial_models(self, store: MemoryStore) -> None:
        assert store.can_read("AGT-EXEC-CFO", "financial_models") is True

    def test_cfo_cannot_read_founder_notes(self, store: MemoryStore) -> None:
        assert store.can_read("AGT-EXEC-CFO", "founder_personal_notes") is False

    def test_ceo_can_read_all_long_term(self, store: MemoryStore) -> None:
        # CEO has all_long_term pattern — should match any long_term domain
        store.seed_from_dict("long_term", "anything", [{"key": "x", "value": "y"}])
        assert store.can_read("AGT-EXEC-CEO", "anything") is True

    def test_unknown_agent_cannot_read(self, store: MemoryStore) -> None:
        assert store.can_read("AGT-UNKNOWN", "dashboard") is False

    def test_coo_can_write_dashboard(self, store: MemoryStore) -> None:
        assert store.can_write("AGT-EXEC-COO", "dashboard") is True

    def test_coo_cannot_write_financial_models(self, store: MemoryStore) -> None:
        assert store.can_write("AGT-EXEC-COO", "financial_models") is False


# ---------------------------------------------------------------------------
# MemoryStore — read operations
# ---------------------------------------------------------------------------

class TestMemoryRead:
    def test_read_returns_active_entries(self, store: MemoryStore) -> None:
        store.seed_from_dict("episodic", "dashboard", [
            {"key": "status", "value": "active"},
        ])
        entries = store.read("episodic", "dashboard", "AGT-EXEC-COO")
        assert len(entries) == 1

    def test_read_excludes_superseded(self, store: MemoryStore) -> None:
        store.seed_from_dict("episodic", "dashboard", [
            {"key": "status", "value": "old"},
        ])
        # Manually supersede
        entry = store.layers["episodic"]["dashboard"][0]
        entry.replaced_by = "MEM-FAKE"

        entries = store.read("episodic", "dashboard", "AGT-EXEC-COO")
        assert len(entries) == 0

    def test_read_denied_for_unauthorized_agent(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "financial_models", [
            {"key": "revenue", "value": "1M"},
        ])
        entries = store.read("long_term", "financial_models", "AGT-EXEC-COO")
        assert len(entries) == 0

    def test_read_all(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "facts", [{"key": "a", "value": "1"}])
        store.seed_from_dict("episodic", "dashboard", [{"key": "b", "value": "2"}])

        all_memory = store.read_all("AGT-EXEC-CEO")
        assert "long_term" in all_memory
        assert "episodic" in all_memory
        assert len(all_memory["long_term"]) > 0

    def test_search(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "facts", [
            {"key": "entity", "value": "Netso Energy"},
        ])
        results = store.search("Netso", "AGT-EXEC-CEO")
        assert len(results) == 1
        assert results[0].key == "entity"


# ---------------------------------------------------------------------------
# MemoryStore — retrieve_for_agent (prompt injection)
# ---------------------------------------------------------------------------

class TestMemoryRetrieval:
    def test_retrieve_returns_accessible_memory(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "company_facts", [
            {"key": "entity", "value": "Netso Energy"},
        ])
        context = store.retrieve_for_agent("AGT-EXEC-CEO", "company_facts")
        assert "Netso Energy" in context

    def test_retrieve_respects_permissions(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "financial_models", [
            {"key": "revenue", "value": "1M"},
        ])
        # COO cannot read financial_models
        context = store.retrieve_for_agent("AGT-EXEC-COO", "financial_models")
        assert "1M" not in context

    def test_retrieve_empty_for_unknown_agent(self, store: MemoryStore) -> None:
        context = store.retrieve_for_agent("AGT-UNKNOWN", "anything")
        assert context == ""

    def test_retrieve_formats_output(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "dashboard", [
            {"key": "status", "value": "on_track"},
        ])
        context = store.retrieve_for_agent("AGT-EXEC-COO", "dashboard")
        assert "on_track" in context
        assert isinstance(context, str)

    def test_retrieve_searches_all_layers(self, store: MemoryStore) -> None:
        store.seed_from_dict("semantic", "pricing_model", [
            {"key": "ppa_rate", "value": "10.00"},
        ])
        context = store.retrieve_for_agent("AGT-EXEC-CEO", "pricing")
        assert "10.00" in context

    def test_retrieve_no_hint_returns_all_accessible(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "company_facts", [
            {"key": "entity", "value": "Netso"},
        ])
        store.seed_from_dict("episodic", "dashboard", [
            {"key": "status", "value": "ok"},
        ])
        context = store.retrieve_for_agent("AGT-EXEC-CEO")
        assert "Netso" in context
        assert "ok" in context

    def test_retrieve_respects_max_chars(self, store: MemoryStore) -> None:
        store.seed_from_dict("long_term", "big_domain", [
            {"key": f"key_{i}", "value": "x" * 100} for i in range(50)
        ])
        context = store.retrieve_for_agent("AGT-EXEC-CEO", max_chars=200)
        assert len(context) < 500  # well under 50 * 120 chars


# ---------------------------------------------------------------------------
# MemoryStore — candidate submission and review
# ---------------------------------------------------------------------------

class TestMemoryCandidates:
    def test_submit_candidate(self, store: MemoryStore) -> None:
        candidate = store.submit_candidate(
            agent_id="AGT-EXEC-COO",
            layer="episodic",
            domain="dashboard",
            key="status",
            content="All systems operational",
        )
        assert candidate.id.startswith("CAND-")
        assert candidate.status == "pending"
        assert len(store.candidates) == 1

    def test_review_store_new(self, store: MemoryStore) -> None:
        candidate = store.submit_candidate(
            agent_id="AGT-EXEC-COO",
            layer="episodic",
            domain="dashboard",
            key="status",
            content="All systems operational",
        )
        entry = store.review_candidate(candidate.id, Decision.STORE, reason="Test")
        assert entry is not None
        assert entry.id.startswith("MEM-")
        assert entry.key == "status"
        assert entry.content == "All systems operational"
        assert candidate.status == "store"

    def test_review_version_existing(self, store: MemoryStore) -> None:
        # Seed existing entry
        store.seed_from_dict("episodic", "dashboard", [
            {"key": "status", "value": "old_status"},
        ])

        candidate = store.submit_candidate(
            agent_id="AGT-EXEC-COO",
            layer="episodic",
            domain="dashboard",
            key="status",
            content="new_status",
        )
        entry = store.review_candidate(candidate.id, Decision.VERSION, reason="Updated")
        assert entry is not None
        assert entry.version == 2

        # Old entry should be superseded
        old = store.layers["episodic"]["dashboard"][0]
        assert old.replaced_by == entry.id

    def test_review_reject(self, store: MemoryStore) -> None:
        candidate = store.submit_candidate(
            agent_id="AGT-EXEC-COO",
            layer="episodic",
            domain="dashboard",
            key="bad",
            content="bad data",
        )
        entry = store.review_candidate(candidate.id, Decision.REJECT, reason="Invalid")
        assert entry is None
        assert candidate.status == "reject"

    def test_review_unknown_candidate(self, store: MemoryStore) -> None:
        entry = store.review_candidate("CAND-999999", Decision.STORE)
        assert entry is None


# ---------------------------------------------------------------------------
# MemoryStore — auto-review
# ---------------------------------------------------------------------------

class TestAutoReview:
    def test_review_pending_stores(self, store: MemoryStore) -> None:
        store.submit_candidate(
            agent_id="AGT-EXEC-COO",
            layer="episodic",
            domain="dashboard",
            key="kpi",
            content="Revenue up 10%",
        )
        records = store.review_pending(auto_store=True)
        assert len(records) == 1
        assert records[0].operation == "store"

    def test_review_pending_dedup(self, store: MemoryStore) -> None:
        # Seed same content — both value and content must match the candidate
        store.seed_from_dict("episodic", "dashboard", [
            {"key": "kpi", "value": "Revenue up 10%", "description": "Revenue up 10%"},
        ])

        store.submit_candidate(
            agent_id="AGT-EXEC-COO",
            layer="episodic",
            domain="dashboard",
            key="kpi",
            value="Revenue up 10%",
            content="Revenue up 10%",
        )
        records = store.review_pending(auto_store=True)
        # Should be deduped — no new entries stored
        assert len(records) == 0


# ---------------------------------------------------------------------------
# MemoryStore — persistence
# ---------------------------------------------------------------------------

class TestPersistence:
    def test_persist_audit_log(self, store: MemoryStore) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Seed + submit + review
            store.seed_from_dict("long_term", "facts", [{"key": "a", "value": "1"}])
            store.submit_candidate(
                agent_id="AGT-EXEC-COO",
                layer="episodic",
                domain="dashboard",
                key="kpi",
                content="Test",
            )
            store.review_pending(auto_store=True)

            result = store.persist_to_disk(root, cycle_id="test-cycle")

            # Audit log should exist
            audit_path = root / "ai_system" / "System" / "TAZOS_AUDIT.log"
            assert audit_path.exists()
            lines = audit_path.read_text().strip().split("\n")
            assert len(lines) >= 1
            # Each line should be valid JSON
            for line in lines:
                json.loads(line)

    def test_persist_memory_snapshot(self, store: MemoryStore) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            store.seed_from_dict("long_term", "facts", [
                {"key": "entity", "value": "Netso"},
            ])

            result = store.persist_to_disk(root)

            memory_path = root / "ai_system" / "System" / "TAZOS_MEMORY.md"
            assert memory_path.exists()
            content = memory_path.read_text()
            assert "Netso" in content

    def test_persist_append_only(self, store: MemoryStore) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # First persist
            store.seed_from_dict("long_term", "facts", [{"key": "a", "value": "1"}])
            store.submit_candidate(
                agent_id="AGT-EXEC-COO",
                layer="episodic",
                domain="dashboard",
                key="k",
                content="v1",
            )
            store.review_pending(auto_store=True)
            store.persist_to_disk(root, cycle_id="cycle-1")

            # Second persist
            store.submit_candidate(
                agent_id="AGT-EXEC-COO",
                layer="episodic",
                domain="dashboard",
                key="k2",
                content="v2",
            )
            store.review_pending(auto_store=True)
            store.persist_to_disk(root, cycle_id="cycle-2")

            audit_path = root / "ai_system" / "System" / "TAZOS_AUDIT.log"
            lines = audit_path.read_text().strip().split("\n")
            assert len(lines) >= 2  # Both cycles recorded


# ---------------------------------------------------------------------------
# build_memory_from_manifest
# ---------------------------------------------------------------------------

class TestBuildFromManifest:
    def test_builds_store(self, manifest: dict) -> None:
        store = build_memory_from_manifest(manifest)
        assert store is not None
        assert len(store.layers["long_term"]) > 0
        assert len(store.layers["episodic"]) > 0
        assert len(store.layers["semantic"]) > 0

    def test_permissions_loaded(self, manifest: dict) -> None:
        store = build_memory_from_manifest(manifest)
        assert "AGT-EXEC-COO" in store.permissions

    def test_long_term_entries_seeded(self, manifest: dict) -> None:
        store = build_memory_from_manifest(manifest)
        entries = store.layers["long_term"]["company_facts"]
        assert len(entries) == 2
        keys = {e.key for e in entries}
        assert "legal_entity_name" in keys

    def test_search_after_build(self, manifest: dict) -> None:
        store = build_memory_from_manifest(manifest)
        results = store.search("Netso", "AGT-EXEC-CEO")
        assert len(results) >= 1

    def test_summary(self, manifest: dict) -> None:
        store = build_memory_from_manifest(manifest)
        s = store.summary()
        assert "Memory Store:" in s
        assert "long_term" in s
