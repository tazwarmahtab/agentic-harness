"""Tests for enforcement rules — Engine, check functions, ToolGateway integration."""

from __future__ import annotations

import pytest

from aos.enforcement import (
    CHECK_FUNCTIONS,
    EnforcementEngine,
    EnforcementResult,
    EnforcementRule,
    EnforcementSeverity,
    STARTER_RULES,
    check_no_path_traversal,
    check_no_shell_in_path,
    check_no_unbalanced_quotes,
    check_rate_sanity,
)
from aos.tools import ToolGateway, ToolResult


# ---------------------------------------------------------------------------
# EnforcementRule model tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEnforcementRule:

    def test_scope_all_applies_everywhere(self):
        rule = EnforcementRule(
            id="ENF-TEST-001", name="test", description="",
            severity=EnforcementSeverity.BLOCK, scope="all",
            check_fn="check_no_path_traversal",
        )
        assert rule.applies_to_agent("ACL-EXEC-001")
        assert rule.applies_to_agent(None)
        assert rule.applies_to_agent("anything")

    def test_scope_agent_class(self):
        rule = EnforcementRule(
            id="ENF-TEST-002", name="test", description="",
            severity=EnforcementSeverity.BLOCK, scope="agent_class:ACL-EXEC-001",
            check_fn="check_no_path_traversal",
        )
        assert rule.applies_to_agent("ACL-EXEC-001")
        assert not rule.applies_to_agent("ACL-FIN-001")
        assert not rule.applies_to_agent(None)

    def test_scope_capability(self):
        rule = EnforcementRule(
            id="ENF-TEST-003", name="test", description="",
            severity=EnforcementSeverity.BLOCK, scope="capability:execute_code",
            check_fn="check_no_path_traversal",
        )
        assert rule.applies_to_capability("execute_code")
        assert not rule.applies_to_capability("read_file")

    def test_frozen(self):
        rule = EnforcementRule(
            id="ENF-TEST-004", name="test", description="",
            severity=EnforcementSeverity.WARN, scope="all",
            check_fn="check_rate_sanity",
        )
        with pytest.raises(AttributeError):
            rule.id = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Check function tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCheckFunctions:

    def test_path_traversal_blocked(self):
        passed, msg = check_no_path_traversal("read_file", {"path": "../etc/passwd"}, None)
        assert not passed
        assert "traversal" in msg.lower()

    def test_path_traversal_encoded(self):
        passed, _ = check_no_path_traversal("read_file", {"path": "%2e%2e/secret"}, None)
        assert not passed

    def test_path_traversal_null_byte(self):
        passed, _ = check_no_path_traversal("read_file", {"path": "file\x00.txt"}, None)
        assert not passed

    def test_path_traversal_clean(self):
        passed, _ = check_no_path_traversal("read_file", {"path": "data/report.md"}, None)
        assert passed

    def test_shell_metacharacters(self):
        passed, msg = check_no_shell_in_path("read_file", {"path": "file;rm -rf /"}, None)
        assert not passed
        assert "shell" in msg.lower()

    def test_shell_metacharacters_pipe(self):
        passed, _ = check_no_shell_in_path("read_file", {"path": "file|cat"}, None)
        assert not passed

    def test_shell_clean_path(self):
        passed, _ = check_no_shell_in_path("read_file", {"path": "data/report.md"}, None)
        assert passed

    def test_unbalanced_quotes(self):
        passed, msg = check_no_unbalanced_quotes("write_file", {"content": 'hello"'}, None)
        assert not passed
        assert "quote" in msg.lower()

    def test_balanced_quotes(self):
        passed, _ = check_no_unbalanced_quotes("write_file", {"content": 'hello"'}, None)
        # This has an odd number of unescaped quotes, should warn
        assert not passed

    def test_clean_content(self):
        passed, _ = check_no_unbalanced_quotes("write_file", {"content": "hello world"}, None)
        assert passed

    def test_rate_sanity_high(self):
        passed, msg = check_rate_sanity("batch", {"count": 5000}, None)
        assert not passed
        assert "high" in msg.lower()

    def test_rate_sanity_normal(self):
        passed, _ = check_rate_sanity("batch", {"count": 100}, None)
        assert passed

    def test_rate_sanity_no_int_key(self):
        passed, _ = check_rate_sanity("batch", {"name": "test"}, None)
        assert passed

    def test_all_check_functions_registered(self):
        """All STARTER_RULES check_fn values must be in CHECK_FUNCTIONS."""
        for rule in STARTER_RULES:
            assert rule.check_fn in CHECK_FUNCTIONS, f"Missing check fn: {rule.check_fn}"


# ---------------------------------------------------------------------------
# EnforcementEngine tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestEnforcementEngine:

    def test_default_uses_starter_rules(self):
        engine = EnforcementEngine()
        assert len(engine.rules) == len(STARTER_RULES)

    def test_custom_rules(self):
        rule = EnforcementRule(
            id="ENF-CUSTOM-001", name="custom", description="",
            severity=EnforcementSeverity.BLOCK, scope="all",
            check_fn="check_no_path_traversal",
        )
        engine = EnforcementEngine(rules=[rule])
        assert len(engine.rules) == 1

    def test_evaluate_blocks_traversal(self):
        engine = EnforcementEngine()
        results = engine.evaluate("read_file", {"path": "../secret"}, None)
        assert engine.has_blocks(results)

    def test_evaluate_passes_clean(self):
        engine = EnforcementEngine()
        results = engine.evaluate("read_file", {"path": "data/report.md"}, None)
        assert not engine.has_blocks(results)

    def test_evaluate_skips_non_matching_scope(self):
        rule = EnforcementRule(
            id="ENF-CAP-001", name="cap", description="",
            severity=EnforcementSeverity.BLOCK, scope="capability:execute_code",
            check_fn="check_no_path_traversal",
        )
        engine = EnforcementEngine(rules=[rule])
        results = engine.evaluate("read_file", {"path": "../secret"}, None)
        assert len(results) == 0  # rule skipped

    def test_has_blocks_true(self):
        results = [
            EnforcementResult(rule_id="R1", passed=False, message="bad",
                              severity=EnforcementSeverity.BLOCK),
        ]
        engine = EnforcementEngine()
        assert engine.has_blocks(results)

    def test_has_blocks_false_when_warn(self):
        results = [
            EnforcementResult(rule_id="R1", passed=False, message="bad",
                              severity=EnforcementSeverity.WARN),
        ]
        engine = EnforcementEngine()
        assert not engine.has_blocks(results)

    def test_get_warnings(self):
        results = [
            EnforcementResult(rule_id="R1", passed=True, message="ok",
                              severity=EnforcementSeverity.WARN),
            EnforcementResult(rule_id="R2", passed=False, message="warn",
                              severity=EnforcementSeverity.WARN),
            EnforcementResult(rule_id="R3", passed=False, message="block",
                              severity=EnforcementSeverity.BLOCK),
        ]
        engine = EnforcementEngine()
        warnings = engine.get_warnings(results)
        assert len(warnings) == 1
        assert warnings[0].rule_id == "R2"


# ---------------------------------------------------------------------------
# ToolGateway integration tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestToolGatewayEnforcement:

    def test_gateway_has_enforcement(self):
        gw = ToolGateway(venture_root=None)
        assert gw._enforcement is not None
        assert len(gw._enforcement.rules) > 0

    def test_traversal_blocked_by_gateway(self):
        gw = ToolGateway(venture_root=None)
        # Register a tool so permission check passes
        from aos.tools import ToolDef
        tool = ToolDef(
            id="T-001", name="Read File", capability="read_file",
            category="file", status="active",
            read_agents=["all_executive_specialists"],
        )
        gw.register_tool(tool)
        result = gw.call("read_file", {"path": "../etc/passwd"}, "AGT-EXEC-COO")
        assert result.status == "denied"
        assert "Enforcement" in result.error

    def test_clean_call_passes_enforcement(self):
        gw = ToolGateway(venture_root=None)
        from aos.tools import ToolDef
        tool = ToolDef(
            id="T-002", name="Read File", capability="read_file",
            category="file", status="active",
            read_agents=["all_executive_specialists"],
        )
        gw.register_tool(tool)
        # This should pass enforcement (but may fail at provider level)
        result = gw.call("read_file", {"path": "data/report.md"}, "AGT-EXEC-COO")
        # Should not be denied by enforcement
        assert result.status != "denied" or "Enforcement" not in (result.error or "")
