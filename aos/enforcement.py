"""Enforcement rules — guardrails that block or warn on dangerous agent actions.

Modeled after TheAgency's Hookify rules but rebuilt natively in Python.
Rules are evaluated at the ToolGateway.call() chokepoint before execution.

Each rule defines:
  - A check function (what to validate)
  - A severity (block = hard stop, warn = log and continue)
  - A scope (which agent classes or capabilities it applies to)
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enforcement rule model
# ---------------------------------------------------------------------------


class EnforcementSeverity(str, Enum):
    BLOCK = "block"
    WARN = "warn"


@dataclass(frozen=True)
class EnforcementRule:
    """A single enforcement rule evaluated before tool execution."""

    id: str
    name: str
    description: str
    severity: EnforcementSeverity
    scope: str  # "all" or "agent_class:<id>" or "capability:<name>"
    check_fn: str  # Name of the check function to call

    def applies_to_agent(self, agent_class_id: str | None) -> bool:
        """Check if this rule applies to the given agent class."""
        if self.scope == "all":
            return True
        if self.scope.startswith("agent_class:") and agent_class_id:
            return self.scope == f"agent_class:{agent_class_id}"
        return False

    def applies_to_capability(self, capability: str) -> bool:
        """Check if this rule applies to the given capability."""
        if self.scope == "all":
            return True
        if self.scope.startswith("capability:"):
            return self.scope == f"capability:{capability}"
        return False


@dataclass(frozen=True)
class EnforcementResult:
    """Result of an enforcement check."""

    rule_id: str
    passed: bool
    message: str
    severity: EnforcementSeverity


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

# Pre-compiled regexes (CRITICAL: avoids ReDoS on every call)
_PATH_TRAVERSAL_RE = re.compile(r"\.\.|%2e%2e|%2E%2E|\x00")
_UNBALANCED_QUOTE_RE = re.compile(r"""(?:^|[^\\])(?:\\\\)*["']$""")
_SHELL_META_RE = re.compile(r"[;&|`$(){}]")


def check_no_path_traversal(
    capability: str,
    inputs: dict[str, Any],
    agent_class_id: str | None,
) -> tuple[bool, str]:
    """Block tool calls with path traversal in file-path inputs."""
    path_keys = ["path", "file_path", "target", "source", "directory"]
    for key in path_keys:
        value = inputs.get(key, "")
        if isinstance(value, str) and _PATH_TRAVERSAL_RE.search(value):
            return False, f"Path traversal detected in '{key}': {value}"
    return True, ""


def check_no_shell_in_path(
    capability: str,
    inputs: dict[str, Any],
    agent_class_id: str | None,
) -> tuple[bool, str]:
    """Block tool calls with shell metacharacters in path inputs."""
    path_keys = ["path", "file_path", "target", "source"]
    for key in path_keys:
        value = inputs.get(key, "")
        if isinstance(value, str) and _SHELL_META_RE.search(value):
            return False, f"Shell metacharacters in '{key}': {value}"
    return True, ""


def check_no_unbalanced_quotes(
    capability: str,
    inputs: dict[str, Any],
    agent_class_id: str | None,
) -> tuple[bool, str]:
    """Warn on unbalanced quotes in string inputs (potential injection)."""
    for key, value in inputs.items():
        if isinstance(value, str) and _UNBALANCED_QUOTE_RE.search(value):
            return False, f"Unbalanced quote in '{key}': {value}"
    return True, ""


def check_rate_sanity(
    capability: str,
    inputs: dict[str, Any],
    agent_class_id: str | None,
) -> tuple[bool, str]:
    """Warn on suspiciously high rate/limit values."""
    for key in ["count", "limit", "batch_size", "max_results"]:
        value = inputs.get(key)
        if isinstance(value, (int, float)) and value > 1000:
            return False, f"Suspiciously high value for '{key}': {value}"
    return True, ""


def check_no_denied_actions(
    capability: str,
    inputs: dict[str, Any],
    agent_class_id: str | None,
) -> tuple[bool, str]:
    """Placeholder for agent-class-specific denied action checks.

    This rule is activated dynamically when an AgentClass has denied_actions.
    The enforcement engine handles this separately from the static check functions.
    """
    return True, ""


# Registry of check functions by name
CHECK_FUNCTIONS: dict[str, Callable[..., tuple[bool, str]]] = {
    "check_no_path_traversal": check_no_path_traversal,
    "check_no_shell_in_path": check_no_shell_in_path,
    "check_no_unbalanced_quotes": check_no_unbalanced_quotes,
    "check_rate_sanity": check_rate_sanity,
    "check_no_denied_actions": check_no_denied_actions,
}


# ---------------------------------------------------------------------------
# Starter enforcement rules
# ---------------------------------------------------------------------------

STARTER_RULES: list[EnforcementRule] = [
    EnforcementRule(
        id="ENF-NO-TRAVERSAL-001",
        name="No path traversal",
        description="Block tool calls with path traversal in file-path inputs",
        severity=EnforcementSeverity.BLOCK,
        scope="all",
        check_fn="check_no_path_traversal",
    ),
    EnforcementRule(
        id="ENF-NO-SHELL-META-001",
        name="No shell metacharacters in paths",
        description="Block tool calls with shell metacharacters in path inputs",
        severity=EnforcementSeverity.BLOCK,
        scope="all",
        check_fn="check_no_shell_in_path",
    ),
    EnforcementRule(
        id="ENF-NO-UNBALANCED-001",
        name="No unbalanced quotes",
        description="Warn on unbalanced quotes in string inputs",
        severity=EnforcementSeverity.WARN,
        scope="all",
        check_fn="check_no_unbalanced_quotes",
    ),
    EnforcementRule(
        id="ENF-RATE-SANITY-001",
        name="Rate sanity check",
        description="Warn on suspiciously high rate/limit values",
        severity=EnforcementSeverity.WARN,
        scope="all",
        check_fn="check_rate_sanity",
    ),
    EnforcementRule(
        id="ENF-NO-DENIED-001",
        name="Denied actions check",
        description="Block actions explicitly denied by agent class",
        severity=EnforcementSeverity.BLOCK,
        scope="all",
        check_fn="check_no_denied_actions",
    ),
]


# ---------------------------------------------------------------------------
# Enforcement engine
# ---------------------------------------------------------------------------


class EnforcementEngine:
    """Evaluates enforcement rules against tool call inputs.

    Rules can be loaded from AgentClass manifests or use the starter set.
    """

    def __init__(self, rules: list[EnforcementRule] | None = None) -> None:
        self.rules: list[EnforcementRule] = rules or list(STARTER_RULES)

    def evaluate(
        self,
        capability: str,
        inputs: dict[str, Any],
        agent_class_id: str | None = None,
    ) -> list[EnforcementResult]:
        """Evaluate all applicable rules against a tool call.

        Returns list of results. Empty list means all rules passed.
        """
        results: list[EnforcementResult] = []

        for rule in self.rules:
            # Check scope
            if not rule.applies_to_capability(capability):
                continue
            if not rule.applies_to_agent(agent_class_id):
                continue

            # Resolve check function
            check_fn = CHECK_FUNCTIONS.get(rule.check_fn)
            if not check_fn:
                logger.warning("Unknown check function: %s", rule.check_fn)
                continue

            passed, message = check_fn(capability, inputs, agent_class_id)
            results.append(
                EnforcementResult(
                    rule_id=rule.id,
                    passed=passed,
                    message=message,
                    severity=rule.severity,
                )
            )

        return results

    def has_blocks(self, results: list[EnforcementResult]) -> bool:
        """Check if any results are BLOCK severity and failed."""
        return any(
            not r.passed and r.severity == EnforcementSeverity.BLOCK
            for r in results
        )

    def get_warnings(self, results: list[EnforcementResult]) -> list[EnforcementResult]:
        """Get all WARN-severity results that failed."""
        return [
            r for r in results
            if not r.passed and r.severity == EnforcementSeverity.WARN
        ]
