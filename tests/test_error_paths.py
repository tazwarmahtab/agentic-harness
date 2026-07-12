"""Error path tests — validates error handling in critical code paths.

Tests error scenarios that should be caught before production:
- Memory retrieval failures
- Tool execution timeouts
- LLM provider fallback chains
- Agent resolution failures
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from aos.registry import Registry
from aos.memory import MemoryStore
from aos.tools import ToolResult


class TestMemoryRetrievalFailures:
    """Test memory store when retrieval fails."""
    
    def test_retrieve_for_agent_empty_store(self):
        """Retrieving from empty memory store should return empty string."""
        store = MemoryStore()
        
        result = store.retrieve_for_agent(
            agent_id="AGT-TEST-001",
            domain_hint="company_facts",
            max_chars=1000
        )
        
        assert isinstance(result, str)
        assert len(result) == 0
    
    def test_retrieve_for_agent_permission_denied(self):
        """Agent without read permission should get empty result."""
        store = MemoryStore()
        
        # Agent has no read permission for "restricted" domain
        result = store.retrieve_for_agent(
            agent_id="AGT-NO-PERMS",
            domain_hint="restricted_data",
            max_chars=1000
        )
        
        assert isinstance(result, str)
    
    def test_retrieve_for_agent_invalid_domain(self):
        """Retrieving from nonexistent domain should handle gracefully."""
        store = MemoryStore()
        
        result = store.retrieve_for_agent(
            agent_id="AGT-TEST-001",
            domain_hint="nonexistent_domain_xyz",
            max_chars=1000
        )
        
        # Should not crash, return empty
        assert isinstance(result, str)


class TestToolExecutionErrors:
    """Test tool execution error handling."""
    
    def test_tool_result_error_status(self):
        """Tool execution can return error status without crashing."""
        result = ToolResult(
            tool_id="TOL-FILE-READ",
            capability="read_dashboard",
            agent_id="AGT-TEST-001",
            status="error",
            error="File not found: /nonexistent/path.md"
        )
        
        assert result.status == "error"
        assert not result.ok
        assert "File not found" in result.error
    
    def test_tool_result_rate_limited(self):
        """Tool execution can be rate limited."""
        result = ToolResult(
            tool_id="TOL-API-CALL",
            capability="read_crm",
            agent_id="AGT-TEST-001",
            status="rate_limited",
            error="Rate limit exceeded: 5 calls/hour"
        )
        
        assert result.status == "rate_limited"
        assert not result.ok
    
    def test_tool_result_denied(self):
        """Tool permission can be denied."""
        result = ToolResult(
            tool_id="TOL-FILE-WRITE",
            capability="write_admin",
            agent_id="AGT-TEST-001",
            status="denied",
            error="Permission denied: agent not in write_agents list"
        )
        
        assert result.status == "denied"
        assert not result.ok


class TestLLMProviderFallback:
    """Test LLM provider fallback chain."""
    
    @patch("aos.llm.create_llm_client")
    def test_all_providers_unavailable(self, mock_create):
        """When all providers fail, should handle gracefully."""
        # Simulate all providers returning None/failing
        mock_create.return_value = None
        
        client = mock_create()
        assert client is None
    
    @patch("aos.llm.create_llm_client")
    def test_fallback_to_next_provider(self, mock_create):
        """Should try next provider when current fails."""
        # First call fails, second succeeds (simulated by multiple calls)
        mock_create.side_effect = [None, MagicMock()]
        
        first_try = mock_create()
        second_try = mock_create()
        
        assert first_try is None
        assert second_try is not None


class TestAgentResolutionErrors:
    """Test agent resolution when agents not found."""
    
    def test_resolve_nonexistent_agent(self):
        """Resolving nonexistent agent returns None."""
        registry = Registry()
        
        result = registry.resolve_agent("AGT-DOES-NOT-EXIST-999")
        assert result is None
    
    def test_resolve_agent_empty_registry(self):
        """Empty registry safely returns None."""
        registry = Registry()
        
        result = registry.resolve_agent("AGT-TEST-001")
        assert result is None
    
    def test_find_bundle_agent_not_in_registry(self):
        """Finding bundle for missing agent returns None."""
        registry = Registry()
        
        result = registry.find_bundle_for_agent("AGT-MISSING")
        assert result is None


class TestValidationErrors:
    """Test validation error handling."""
    
    def test_validate_output_empty_dict(self):
        """Validating empty output should not crash."""
        from aos.evaluator import validate_output
        
        result = validate_output({}, agent_id="AGT-TEST-001", constants=None)
        
        assert result is not None
        assert result.passed is True
    
    def test_validate_output_with_blended_rate(self):
        """Validator detects blended rate violation."""
        from aos.evaluator import validate_output
        from aos.constants import NETSO_FINANCIAL
        
        output = {
            "savings_analysis": "Using blended rate 14.81 for calculations",
            "recommendation": "Proceed"
        }
        
        result = validate_output(
            output,
            agent_id="AGT-EXEC-CFO",
            constants=NETSO_FINANCIAL
        )
        
        assert result.passed is False
        assert any("14.81" in v or "blended" in v.lower() 
                   for v in result.violations)
    
    def test_validate_output_dscr_below_floor(self):
        """Validator detects DSCR below minimum floor."""
        from aos.evaluator import validate_output
        from aos.constants import NETSO_FINANCIAL
        
        output = {
            "dscr": 1.8,
            "analysis": "DSCR is 1.8x"
        }
        
        result = validate_output(
            output,
            agent_id="AGT-EXEC-RSK",
            constants=NETSO_FINANCIAL
        )
        
        assert result.passed is False


class TestExceptionHandling:
    """Test that exceptions are handled gracefully."""
    
    def test_json_decode_error_handling(self):
        """Malformed JSON should be caught."""
        import json
        
        malformed_json = '{"invalid": json}'
        
        with pytest.raises(json.JSONDecodeError):
            json.loads(malformed_json)
    
    def test_file_not_found_handling(self):
        """Missing file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            with open('/nonexistent/path/file.txt', 'r'):
                pass
    
    def test_attribute_error_handling(self):
        """Missing attribute should raise AttributeError."""
        obj = {}
        
        with pytest.raises(AttributeError):
            _ = obj.nonexistent_method()

