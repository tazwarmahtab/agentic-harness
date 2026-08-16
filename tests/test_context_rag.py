"""Tests for RAG injection in context.py build_prompt().

Verifies:
  - rag_context=None → no RAG block in output
  - rag_context supplied → RAG block appears after financial block
  - RAG block precedes memory_context block (Phase 11 layout)
  - RAG block precedes output format (stable-first ordering)
  - build_prompt remains backward-compatible (rag_context defaults to None)
"""

from __future__ import annotations

import pytest

from aos.context import build_prompt
from aos.schemas.agent import Agent, AgentCriticality, AgentStatus


@pytest.fixture()
def minimal_agent() -> Agent:
    """Minimal agent with no optional sections — isolates RAG injection."""
    from aos.schemas.agent import AllowedMemory

    return Agent(
        id="AGT-TEST-001",
        name="Test Agent",
        harness="HAR-TEST",
        status=AgentStatus.PRODUCTION,
        criticality=AgentCriticality.LOW,
        mission="Test mission.",
        allowed_memory=AllowedMemory(read=[], write=[], cannot_read=[]),
    )


@pytest.mark.unit
class TestRagInjection:
    def test_no_rag_when_not_provided(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent)
        assert "RELEVANT VENTURE DOCUMENTS" not in prompt

    def test_rag_block_present_when_provided(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, rag_context="PPA rate is 10 BDT/kWh")
        assert "RELEVANT VENTURE DOCUMENTS" in prompt
        assert "PPA rate is 10 BDT/kWh" in prompt

    def test_rag_content_verbatim(self, minimal_agent: Agent) -> None:
        content = "True variable rate: BDT 12.98/kWh\nBlended: BDT 14.81/kWh"
        prompt = build_prompt(minimal_agent, rag_context=content)
        assert content in prompt

    def test_rag_precedes_memory_context(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(
            minimal_agent,
            rag_context="rag content here",
            memory_context="memory content here",
        )
        rag_pos = prompt.index("RELEVANT VENTURE DOCUMENTS")
        mem_pos = prompt.index("RELEVANT MEMORY CONTEXT")
        assert rag_pos < mem_pos, "RAG block must appear before memory context"

    def test_rag_precedes_output_format(self, minimal_agent: Agent) -> None:
        prompt = build_prompt(minimal_agent, rag_context="some rag")
        rag_pos = prompt.index("RELEVANT VENTURE DOCUMENTS")
        fmt_pos = prompt.index("OUTPUT FORMAT")
        assert rag_pos < fmt_pos, "RAG block must appear before output format"

    def test_backward_compat_no_rag_param(self, minimal_agent: Agent) -> None:
        """build_prompt without rag_context must not crash — signature is backward compat."""
        prompt = build_prompt(minimal_agent, memory_context="some memory")
        assert "RELEVANT VENTURE DOCUMENTS" not in prompt
        assert "RELEVANT MEMORY CONTEXT" in prompt

    def test_empty_string_rag_not_injected(self, minimal_agent: Agent) -> None:
        """Falsy rag_context (empty string) must not emit the RAG block."""
        prompt = build_prompt(minimal_agent, rag_context="")
        assert "RELEVANT VENTURE DOCUMENTS" not in prompt

    def test_rag_after_financial_block(self) -> None:
        """RAG appears after financial constants for CFO agents."""
        from aos.schemas.agent import AgentCriticality, AgentStatus, AllowedMemory

        cfo = Agent(
            id="AGT-EXEC-CFO",
            name="CFO",
            harness="HAR-EXEC",
            status=AgentStatus.PRODUCTION,
            criticality=AgentCriticality.HIGH,
            mission="Financial health.",
            allowed_memory=AllowedMemory(read=[], write=[], cannot_read=[]),
            financial_rules={"hard_fails": []},
        )
        financial = {"true_variable_rate": "12.98 BDT/kWh"}
        prompt = build_prompt(
            cfo,
            netso_financial=financial,
            rag_context="doc chunk here",
        )
        fin_pos = prompt.index("FINANCIAL GROUND TRUTH")
        rag_pos = prompt.index("RELEVANT VENTURE DOCUMENTS")
        assert fin_pos < rag_pos, "Financial block must appear before RAG block"
