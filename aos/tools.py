"""Tool gateway — capability-based tool resolution with permission checks.

Agents request capabilities (e.g. 'read_dashboard', 'write_handoff'),
not vendor APIs. The gateway resolves to actual providers and enforces
permissions, approval gates, and rate limits.

Built-in providers:
  - file_read / file_write — markdown file operations
  - approval_queue — approval request management
  - escalation_alert — alert routing

External providers (stubs):
  - email, calendar, crm, finance — registered but not wired
"""

from __future__ import annotations

import logging
import re
import shlex
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol


# ---------------------------------------------------------------------------
# Tool execution result
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Result of a tool execution."""
    tool_id: str
    capability: str
    agent_id: str
    status: str  # success, denied, gated, error, rate_limited
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    approval_required: bool = False
    approval_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "success"

    def __str__(self) -> str:
        if self.ok:
            return f"[OK] {self.capability}"
        if self.approval_required:
            return f"[GATED] {self.capability} → approval {self.approval_id}"
        return f"[{self.status.upper()}] {self.capability}: {self.error}"


# ---------------------------------------------------------------------------
# Tool definition (from tools.yml)
# ---------------------------------------------------------------------------

@dataclass
class ToolDef:
    """Parsed tool definition from the registry."""
    id: str
    name: str
    capability: str
    category: str
    status: str
    read_agents: list[str] = field(default_factory=list)
    write_agents: list[str] = field(default_factory=list)
    execute_agents: list[str] = field(default_factory=list)
    execute_gated: bool = False
    required_inputs: list[str] = field(default_factory=list)
    optional_inputs: list[str] = field(default_factory=list)
    approval_gate: str | None = None
    validation: dict[str, str] = field(default_factory=dict)
    rate_limit: int | None = None


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------

class ToolProvider(Protocol):
    """Protocol for tool backends."""

    def execute(
        self,
        capability: str,
        inputs: dict[str, Any],
        agent_id: str,
    ) -> dict[str, Any]:
        """Execute a tool capability. Returns output dict."""
        ...


# ---------------------------------------------------------------------------
# Built-in providers
# ---------------------------------------------------------------------------

class FileProvider:
    """File-based tool provider for markdown artifacts.

    Handles read/write of venture artifacts, handoffs, memory, dashboards.
    """

    def __init__(self, venture_root: Path | None = None, memory_store: Any | None = None):
        self.venture_root = venture_root
        self.memory_store = memory_store

    def execute(
        self,
        capability: str,
        inputs: dict[str, Any],
        agent_id: str,
    ) -> dict[str, Any]:
        if capability in ("read_dashboard", "read_file", "read_any_data"):
            return self._read_file(inputs, agent_id)
        if capability in ("write_dashboard", "write_file"):
            return self._write_file(inputs)
        if capability == "write_handoff":
            return self._write_handoff(inputs, agent_id)
        if capability == "write_memory":
            return self._write_memory(inputs, agent_id)
        if capability == "generate_brief":
            return self._generate_brief(inputs, agent_id)
        if capability == "generate_document":
            return self._generate_document(inputs)
        if capability == "generate_report":
            return self._generate_report(inputs)
        raise ValueError(f"FileProvider: unknown capability: {capability}")

    def _read_file(self, inputs: dict[str, Any], agent_id: str) -> dict[str, Any]:
        path_str = inputs.get("path") or inputs.get("file_path") or ""
        ref = inputs.get("ref", "")

        # If we have a memory store, check memory permission first
        if self.memory_store and ref:
            if not self.memory_store.can_read(agent_id, ref):
                return {"content": "", "error": f"Permission denied: Agent {agent_id} cannot read memory domain {ref}"}
            # Try to read from memory store first
            for layer in ["long_term", "episodic", "semantic"]:
                entries = self.memory_store.read(layer, ref, agent_id)
                if entries:
                    # Return combined contents
                    content = "\n\n".join(e.content for e in entries if e.content)
                    return {"content": content, "path": f"memory://{layer}/{ref}", "size": len(content)}

        if not path_str and self.venture_root and ref:
            path_str = ref

        if not path_str:
            return {"content": "", "error": "No path specified"}

        path = Path(path_str)
        if not path.is_absolute() and self.venture_root:
            path = self.venture_root / path_str

        if not path.exists():
            return {"content": "", "error": f"File not found: {path}"}

        try:
            content = path.read_text()
            return {"content": content, "path": str(path), "size": len(content)}
        except Exception as e:
            return {"content": "", "error": str(e)}

    def _write_file(self, inputs: dict[str, Any]) -> dict[str, Any]:
        path_str = inputs.get("path") or inputs.get("file_path") or ""
        content = inputs.get("content", "")

        if not path_str:
            return {"status": "error", "error": "No path specified"}

        path = Path(path_str)
        if not path.is_absolute() and self.venture_root:
            path = self.venture_root / path_str

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            return {"status": "success", "path": str(path), "size": len(content)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _write_handoff(self, inputs: dict[str, Any], agent_id: str) -> dict[str, Any]:
        """Write a handoff file to Nexus/logs/handoffs/."""
        from_agent = inputs.get("from", agent_id)
        to_agent = inputs.get("to", "unknown")
        task = inputs.get("task", "")
        priority = inputs.get("priority", "P2")
        deadline = inputs.get("deadline", "")
        success_criteria = inputs.get("success_criteria", "")

        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"{from_agent}-to-{to_agent}-{today}.md"

        content = f"""# Handoff: {from_agent} → {to_agent}
**Date:** {today}
**Priority:** {priority}
**Deadline:** {deadline}

## Task
{task}

## Success Criteria
{success_criteria}
"""

        # Write to handoffs directory
        handoffs_dir = self.venture_root / "ai_system" / "Nexus" / "logs" / "handoffs" if self.venture_root else Path("handoffs")
        handoffs_dir.mkdir(parents=True, exist_ok=True)
        path = handoffs_dir / filename
        path.write_text(content)

        return {
            "status": "success",
            "handoff_path": str(path),
            "filename": filename,
            "from": from_agent,
            "to": to_agent,
        }

    def _write_memory(self, inputs: dict[str, Any], agent_id: str) -> dict[str, Any]:
        """Submit a memory candidate or write directly if authorized."""
        key = inputs.get("memory_key", "")
        content = inputs.get("content", "")
        classification = inputs.get("classification", "internal")
        layer = inputs.get("layer", "long_term")
        domain = inputs.get("domain", "")

        if self.memory_store:
            # Check if agent has write permission for this domain
            if not self.memory_store.can_write(agent_id, domain):
                return {
                    "status": "denied",
                    "error": f"Permission denied: Agent {agent_id} cannot write to memory domain {domain}",
                }

            # Submit candidate
            candidate = self.memory_store.submit_candidate(
                agent_id=agent_id,
                layer=layer,
                domain=domain,
                key=key,
                content=content,
                classification=classification,
            )
            return {
                "status": "submitted",
                "candidate_id": candidate.id,
                "message": f"Memory candidate {candidate.id} submitted. Reflection engine will decide.",
            }

        candidate = {
            "agent_id": agent_id,
            "key": key,
            "content": content,
            "classification": classification,
            "submitted_at": datetime.now().isoformat(),
            "status": "candidate",
        }

        return {
            "status": "submitted",
            "message": "Memory candidate submitted. Reflection engine will decide: store/reject/summarize/merge/version.",
            "candidate": candidate,
        }

    def _generate_brief(self, inputs: dict[str, Any], agent_id: str) -> dict[str, Any]:
        """Generate a daily brief from inputs."""
        brief_type = inputs.get("brief_type", "daily")
        brief_content = inputs.get("content", inputs.get("inputs", ""))

        return {
            "status": "success",
            "brief_type": brief_type,
            "content": brief_content,
            "estimated_founder_workload_minutes": inputs.get("workload_minutes", 15),
        }

    def _generate_document(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Generate a document from template + content."""
        template = inputs.get("template", "default")
        content = inputs.get("content", "")
        output_path = inputs.get("output_path", f"output/{template}.md")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

        return {
            "status": "success",
            "document_path": str(path),
            "template": template,
            "size": len(content),
        }

    def _generate_report(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Generate a report."""
        report_type = inputs.get("report_type", "weekly")
        content = inputs.get("content", inputs.get("summary", ""))

        return {
            "status": "success",
            "report_type": report_type,
            "content": content,
        }


class ApprovalProvider:
    """Approval queue management — bundled decisions for founder."""

    def __init__(self):
        self.queue: list[dict[str, Any]] = []
        self._counter = 0

    def execute(
        self,
        capability: str,
        inputs: dict[str, Any],
        agent_id: str,
    ) -> dict[str, Any]:
        if capability == "request_approval":
            return self._request_approval(inputs, agent_id)
        if capability == "send_escalation_alert":
            return self._escalation_alert(inputs, agent_id)
        raise ValueError(f"ApprovalProvider: unknown capability: {capability}")

    def _request_approval(self, inputs: dict[str, Any], agent_id: str) -> dict[str, Any]:
        self._counter += 1
        approval_id = f"APR-{self._counter:04d}"
        action = inputs.get("action", "")
        rationale = inputs.get("rationale", "")
        risk = inputs.get("risk_assessment", "")
        deadline = inputs.get("deadline", "72h")

        entry = {
            "id": approval_id,
            "agent_id": agent_id,
            "action": action,
            "rationale": rationale,
            "risk_assessment": risk,
            "deadline": deadline,
            "status": "pending",
            "submitted_at": datetime.now().isoformat(),
        }
        self.queue.append(entry)

        return {
            "approval_id": approval_id,
            "status": "queued",
            "queue_position": len(self.queue),
            "message": f"Approval request {approval_id} added to founder queue.",
        }

    def _escalation_alert(self, inputs: dict[str, Any], agent_id: str) -> dict[str, Any]:
        alert_type = inputs.get("alert_type", "general")
        severity = inputs.get("severity", "normal")
        target = inputs.get("target", "founder")
        description = inputs.get("description", "")

        return {
            "alert_id": f"ESC-{datetime.now().strftime('%Y%m%d')}-{alert_type.upper()}",
            "status": "delivered",
            "target": target,
            "severity": severity,
            "description": description,
        }

    def get_pending(self) -> list[dict[str, Any]]:
        return [e for e in self.queue if e["status"] == "pending"]

    def get_all(self) -> list[dict[str, Any]]:
        return list(self.queue)


# ---------------------------------------------------------------------------
# Tool Gateway — main entry point
# ---------------------------------------------------------------------------

class ToolGateway:
    """Capability-based tool gateway with permission checks and providers.

    Usage:
        gateway = ToolGateway(venture_root=Path("~/Netso_HQ"))
        result = gateway.call("read_dashboard", {}, agent_id="AGT-EXEC-COO")
    """

    def __init__(
        self,
        venture_root: Path | None = None,
        memory_store: Any | None = None,
        providers: dict[str, ToolProvider] | None = None,
    ):
        self.venture_root = venture_root
        self.memory_store = memory_store
        self.tools: dict[str, ToolDef] = {}
        self.providers: dict[str, ToolProvider] = providers or {}
        self._rate_counters: dict[str, list[datetime]] = {}
        self._approval_provider: ApprovalProvider | None = None

        # Default providers
        if "file" not in self.providers:
            self.providers["file"] = FileProvider(venture_root, memory_store)
        if "approval" not in self.providers:
            self._approval_provider = ApprovalProvider()
            self.providers["approval"] = self._approval_provider

    def register_tool(self, tool: ToolDef) -> None:
        """Register a tool definition."""
        self.tools[tool.capability] = tool

    def register_tools_from_dict(self, tools_data: list[dict[str, Any]]) -> None:
        """Register tools from parsed YAML dict (tools.yml)."""
        for t in tools_data:
            tool = ToolDef(
                id=t.get("id", ""),
                name=t.get("name", ""),
                capability=t.get("capability", ""),
                category=t.get("category", ""),
                status=t.get("status", "registered"),
                read_agents=t.get("permissions", {}).get("read", []),
                write_agents=t.get("permissions", {}).get("write", []),
                execute_agents=t.get("permissions", {}).get("execute", []) if isinstance(t.get("permissions", {}).get("execute"), list) else [],
                execute_gated=t.get("permissions", {}).get("execute") == "gated",
                required_inputs=t.get("inputs", {}).get("required", []),
                optional_inputs=t.get("inputs", {}).get("optional", []),
                approval_gate=t.get("approval_gate"),
                validation=t.get("validation", {}),
                rate_limit=(t.get("rate_limits") or {}).get("max_per_hour"),
            )
            if tool.capability:
                self.tools[tool.capability] = tool

    def check_permission(self, capability: str, agent_id: str, mode: str = "read") -> bool:
        """Check if an agent has permission for a tool capability."""
        tool = self.tools.get(capability)
        if not tool:
            return False

        if mode == "read":
            return agent_id in tool.read_agents or "all_executive_specialists" in tool.read_agents
        if mode == "write":
            return agent_id in tool.write_agents or "all_executive_specialists" in tool.write_agents
        if mode == "execute":
            return agent_id in tool.execute_agents or "all_executive_specialists" in tool.execute_agents
        return False

    def check_rate_limit(self, capability: str, limit: int | None = None) -> bool:
        """Check if tool is within rate limits."""
        tool = self.tools.get(capability)
        if not tool or not tool.rate_limit:
            return True

        now = datetime.now()
        hour_ago = now.timestamp() - 3600
        key = capability
        if key not in self._rate_counters:
            self._rate_counters[key] = []

        # Prune old entries
        self._rate_counters[key] = [
            t for t in self._rate_counters[key]
            if t.timestamp() > hour_ago
        ]

        return len(self._rate_counters[key]) < tool.rate_limit

    def call(
        self,
        capability: str,
        inputs: dict[str, Any],
        agent_id: str,
    ) -> ToolResult:
        """Execute a tool capability with permission and approval checks."""
        tool = self.tools.get(capability)
        if not tool:
            return ToolResult(
                tool_id="",
                capability=capability,
                agent_id=agent_id,
                status="error",
                error=f"Unknown capability: {capability}",
            )

        # Permission check
        if not self.check_permission(capability, agent_id, "read") and \
           not self.check_permission(capability, agent_id, "write") and \
           not self.check_permission(capability, agent_id, "execute"):
            return ToolResult(
                tool_id=tool.id,
                capability=capability,
                agent_id=agent_id,
                status="denied",
                error=f"Agent {agent_id} not authorized for {capability}",
            )

        # Rate limit check
        if not self.check_rate_limit(capability):
            return ToolResult(
                tool_id=tool.id,
                capability=capability,
                agent_id=agent_id,
                status="rate_limited",
                error=f"Rate limit exceeded for {capability} ({tool.rate_limit}/hour)",
            )

        # Approval gate check
        if tool.execute_gated or tool.approval_gate:
            if self._approval_provider:
                approval_result = self._approval_provider._request_approval({
                    "action": capability,
                    "rationale": tool.approval_gate or f"Gated tool: {capability}",
                    "risk_assessment": "auto-gated by tool gateway",
                }, agent_id)
                return ToolResult(
                    tool_id=tool.id,
                    capability=capability,
                    agent_id=agent_id,
                    status="gated",
                    approval_required=True,
                    approval_id=approval_result["approval_id"],
                )

        # Resolve provider
        provider = self._resolve_provider(capability)
        if not provider:
            return ToolResult(
                tool_id=tool.id,
                capability=capability,
                agent_id=agent_id,
                status="error",
                error=f"No provider for capability: {capability}",
            )

        # Execute
        try:
            output = provider.execute(capability, inputs, agent_id)
            # Record rate limit usage
            if tool.rate_limit:
                if capability not in self._rate_counters:
                    self._rate_counters[capability] = []
                self._rate_counters[capability].append(datetime.now())

            return ToolResult(
                tool_id=tool.id,
                capability=capability,
                agent_id=agent_id,
                status="success",
                output=output,
            )
        except Exception as e:
            return ToolResult(
                tool_id=tool.id,
                capability=capability,
                agent_id=agent_id,
                status="error",
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Action executor — used by runtime.step_execute for real execution
    # ------------------------------------------------------------------

    _logger = logging.getLogger("aos.tools")

    _BLOCKED_PATTERNS = [
        (re.compile(r"rm\s+(-[a-zA-Z]*\s+)*(--?\w+\s+)*\/"), "rm on root path"),
        (re.compile(r"mkfs\b"), "filesystem formatting"),
        (re.compile(r">\s*\/dev\/"), "write to /dev/"),
        (re.compile(r":\(\)\s*\{"), "fork bomb"),
        (re.compile(r"dd\s+if="), "dd disk operations"),
        (re.compile(r"mv\s+.*\/\s"), "mv to root path"),
        (re.compile(r"curl\s.*\|\s*(ba)?sh"), "curl pipe to shell"),
        (re.compile(r"wget\s.*\|\s*(ba)?sh"), "wget pipe to shell"),
        (re.compile(r"python[23]?\s+-c"), "python -c execution"),
        (re.compile(r"chmod\s+(-[a-zA-Z]*\s+)*\/"), "chmod on root path"),
        (re.compile(r"chown\s+(-[a-zA-Z]*\s+)*\/"), "chown on root path"),
        (re.compile(r">\s*\/etc\/"), "write to /etc/"),
        (re.compile(r"eval\s*\("), "eval() execution"),
        (re.compile(r"exec\s*\("), "exec() execution"),
    ]

    def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        """Execute a concrete action dict and return real results.

        Supported action types:
          - ``shell``: run a subprocess command (with blocklist guard)
          - ``file_write``: write content to a file path

        Parameters
        ----------
        action:
            Must contain an ``"action_type"`` key.  Additional keys depend
            on the type — see the individual handlers below.

        Returns
        -------
        dict with at least ``{"ok": bool}`` plus type-specific fields.
        """
        action_type = action.get("action_type", "")
        handler = getattr(self, f"_exec_{action_type}", None)
        if handler is None:
            return {"ok": False, "error": f"Unknown action_type: {action_type}"}
        try:
            return handler(action)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def _exec_shell(self, action: dict[str, Any]) -> dict[str, Any]:
        """Run a shell command via subprocess with regex-based safety blocklist."""
        command = action.get("command", "")
        if not command:
            return {"ok": False, "error": "No command provided"}

        # Validate shell syntax is parseable
        try:
            shlex.split(command)
        except ValueError:
            return {"ok": False, "error": "Command contains unparseable shell syntax"}

        # Check against blocked patterns
        cmd_lower = command.lower().strip()
        for pattern, desc in self._BLOCKED_PATTERNS:
            if pattern.search(cmd_lower):
                self._logger.warning(
                    "Shell command blocked (%s): %s", desc, command[:80]
                )
                return {"ok": False, "error": f"Blocked dangerous command: {desc}"}

        timeout = action.get("timeout", 30)
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "ok": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": f"Command timed out after {timeout}s"}

    def _exec_file_write(self, action: dict[str, Any]) -> dict[str, Any]:
        """Write content to a file, resolving relative paths against venture_root."""
        path_str = action.get("path", "")
        content = action.get("content", "")

        if not path_str:
            return {"ok": False, "error": "No path provided"}

        path = Path(path_str)
        if not path.is_absolute() and self.venture_root:
            path = self.venture_root / path_str

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return {"ok": True, "path": str(path), "bytes_written": len(content.encode())}

    def _resolve_provider(self, capability: str) -> ToolProvider | None:
        """Resolve a capability to its provider."""
        tool = self.tools.get(capability)
        if not tool:
            return None

        # Category → provider mapping
        category_map = {
            "communication": "email",
            "productivity": "file",
            "finance": "finance",
            "crm": "crm",
            "internal": "file",
            "knowledge": "knowledge",
            "governance": "approval",
        }

        provider_name = category_map.get(tool.category, "file")

        # Specific capability overrides
        if capability in ("request_approval", "send_escalation_alert"):
            provider_name = "approval"
        elif capability.startswith("read_") or capability.startswith("write_") or capability.startswith("generate_"):
            provider_name = "file"

        return self.providers.get(provider_name)

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get all pending approval requests."""
        if self._approval_provider:
            return self._approval_provider.get_pending()
        return []

    def summary(self) -> str:
        """Return a summary of registered tools."""
        lines = [f"Tool Gateway: {len(self.tools)} tools registered"]
        by_category: dict[str, int] = {}
        for tool in self.tools.values():
            by_category[tool.category] = by_category.get(tool.category, 0) + 1
        for cat, count in sorted(by_category.items()):
            lines.append(f"  {cat}: {count}")
        pending = len(self.get_pending_approvals())
        if pending:
            lines.append(f"  Pending approvals: {pending}")
        return "\n".join(lines)
