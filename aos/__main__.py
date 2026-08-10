"""AOS CLI entry point.

Usage:
 python -m aos validate [--harness NAME] [--venture NAME] [--verbose]
 python -m aos status [--harness NAME] [--venture NAME]
 python -m aos run [--venture NAME] [--dry-run]
 python -m aos orchestrate [--one-liner TEXT] [plan_path] [--skip-spec] [--skip-plan] [--skip-review] [--gate spec,plan,review] [--dry-run]
 python -m aos orchestrate --autonomous [--roadmap-file PATH] [--dry-run]
 python -m aos ventures
 python -m aos approvals [list|approve-all|reject-all|approve ID|reject ID]
 python -m aos audit PATH [--type TYPE]
 python -m aos systems [list|show ID]
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
import sys
from pathlib import Path
from typing import Optional

from aos.orchestrate.gates import GateManager
from aos.orchestrate.pipeline import (
    OrchestratePipeline,
    PipelineContext,
)
from aos.registry import load_registry
from aos.validator import validate_all
from aos.discover import discover_ventures, find_venture

logger = logging.getLogger(__name__)


def find_project_root() -> Path:
    """Find the aos project root (where aos/ package lives)."""
    return Path(__file__).parent.parent


def _resolve_venture(venture_name: str | None) -> tuple[Path | None, str]:
    """Resolve venture name to path. Returns (path, display_name)."""
    if not venture_name:
        return None, "none"

    result = find_venture(venture_name)
    if result is None:
        return None, venture_name

    path, venture = result
    return path, venture.name


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate all manifests."""
    root = find_project_root()
    harness_dir = root / "aos" / "harnesses" / "executive"
    venture_path, venture_name = _resolve_venture(args.venture)

    if not harness_dir.exists():
        logger.error(f"Harness directory not found: {harness_dir}")
        return 1

    if args.harness:
        harness_dir = root / "aos" / "harnesses" / args.harness
        if not harness_dir.exists():
            logger.error(f"Harness not found: {args.harness}")
            return 1

    print(f"Validating manifests in: {harness_dir}")
    if venture_path and venture_path.exists():
        print(f"Venture: {venture_path}")

    result = validate_all(
        harness_dir=harness_dir,
        venture_path=venture_path if venture_path and venture_path.exists() else None,
        verbose=args.verbose,
    )

    print()
    print(result.summary())
    return 0 if result.ok else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show system status."""
    root = find_project_root()
    harness_dir = root / "aos" / "harnesses" / "executive"
    venture_path, venture_name = _resolve_venture(args.venture)

    if args.harness:
        harness_dir = root / "aos" / "harnesses" / args.harness

    if not harness_dir.exists():
        logger.error(f"Harness not found: {harness_dir}")
        print("Available harnesses:")
        for d in sorted((root / "aos" / "harnesses").iterdir()):
            if d.is_dir() and (d / "harness.yml").exists():
                print(f" - {d.name}")
        return 1

    registry = load_registry(
        harness_dir=harness_dir,
        venture_path=venture_path if venture_path and venture_path.exists() else None,
    )

    print(registry.summary())
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Execute the daily harness cycle."""
    from aos.graph import run_cycle_graph, format_state_summary
    from aos.registry import load_registry

    root = find_project_root()
    harness_name = args.harness or "executive"
    harness_dir = root / "aos" / "harnesses" / harness_name
    venture_path, venture_name = _resolve_venture(args.venture)

    # If venture was requested but not found, fail with clear error
    if args.venture and venture_path is None:
        logger.error(f"Venture '{args.venture}' not found.")
        print("Available ventures:")
        for path, v in discover_ventures(root / "aos" / "ventures"):
            print(f" - {v.name} ({v.id})")
        return 1

    if not harness_dir.exists():
        logger.error(f"Harness not found: {harness_dir}")
        print("Available harnesses:")
        for d in sorted((root / "aos" / "harnesses").iterdir()):
            if d.is_dir() and (d / "harness.yml").exists():
                print(f" - {d.name}")
        return 1

    print(f"Running harness cycle: {harness_dir.name}")
    if venture_path:
        print(f"Venture: {venture_path}")
    if args.dry_run:
        print("Mode: DRY RUN (no LLM calls)")
    elif args.prefer:
        print(f"Backend: {args.prefer}")
    else:
        print("Backend: auto-detect")
    print()

    vp = venture_path if venture_path and venture_path.exists() else None
    registry = load_registry(harness_dir, vp)

    if not registry.harnesses:
        logger.error("No harnesses found in registry")
        return 1

    # Load sibling harnesses for cross-harness dispatch (H4)
    harnesses_root = harness_dir.parent
    if harnesses_root.exists():
        for sibling in harnesses_root.iterdir():
            if (
                sibling.is_dir()
                and sibling != harness_dir
                and (sibling / "harness.yml").exists()
            ):
                sibling_registry = load_registry(sibling, vp)
                for hid, bundle in sibling_registry.harnesses.items():
                    if hid not in registry.harnesses:
                        registry.harnesses[hid] = bundle

    # Select the primary bundle by name
    bundle = registry.harnesses.get(
        next(iter(registry.harnesses.keys()))
        if harness_name not in registry.harnesses
        else harness_name
    )
    if not bundle:
        bundle = next(iter(registry.harnesses.values()))

    venture_id = registry.venture.id if registry.venture else "UNKNOWN"

    # Load resolved approval IDs from previous runs
    resolved_approval_ids: list[str] = []
    if not args.dry_run:
        try:
            from aos.services.approvals import get_resolved_ids
            resolved_approval_ids = get_resolved_ids()
            if resolved_approval_ids:
                print(f"Loaded {len(resolved_approval_ids)} resolved approval(s) from previous runs")
        except Exception as e:
            logger.warning("Failed to load resolved approvals: %s", e)

    # Resolve venture artifacts
    venture_artifacts: dict[str, Path] = {}
    if vp:
        venture_root = vp.parent.parent if vp else None
        if venture_root and registry.venture:
            for key, art in registry.venture.artifacts.items():
                art_path = venture_root / art.path
                if art_path.exists():
                    venture_artifacts[key] = art_path

    state = run_cycle_graph(
        bundle=bundle,
        venture_id=venture_id,
        venture_artifacts=venture_artifacts or None,
        venture=registry.venture,
        dry_run=args.dry_run,
        verbose=args.verbose,
        registry=registry,  # H4: cross-harness dispatch
        resolved_approval_ids=resolved_approval_ids,
    )

    print(format_state_summary(state))

    # Send notification if approvals pending (skip in dry-run)
    if not args.dry_run:
        try:
            from aos.notify import send_approval_notification, send_run_summary

            approvals_pending = state.get("approval_queue", [])
            errors = state.get("errors", [])
            steps = state.get("step_results", [])

            if approvals_pending:
                send_approval_notification(approvals_pending)

            send_run_summary(
                steps_completed=len([s for s in steps if s.get("status") == "success"]),
                total_steps=len(steps),
                errors=errors,
                approvals_pending=len(approvals_pending),
                venture=args.venture or "netso",
            )
        except Exception as e:
            logger.warning("Failed to send notification: %s", e)

    return 0


def cmd_orchestrate(args: argparse.Namespace) -> int:
    """Run the end-to-end pipeline: /spec → /autoplan → /implement → /reviewloop → /ship."""
    root = find_project_root()

    # Autonomous mode: delegate to AutonomousPipeline
    if getattr(args, "autonomous", False):
        from aos.orchestrate.autonomous import AutonomousPipeline

        roadmap_file = getattr(args, "roadmap_file", "ROADMAP.md")
        gate_timeout = getattr(args, "gate_timeout", 300.0)
        max_retries = getattr(args, "max_retries", 3)
        pipeline = AutonomousPipeline(
            roadmap_file=roadmap_file,
            dry_run=args.dry_run,
            auto=getattr(args, "auto", False),
            project_root=root,
            gate_timeout_s=gate_timeout,
            max_retries=max_retries,
        )
        return pipeline.run()

    # Resolve plan path
    plan_path: Optional[Path] = None
    if args.plan_path:
        p = Path(args.plan_path)
        plan_path = p if p.is_absolute() else root / p
    elif args.one_liner and not args.skip_spec:
        # /spec will create the plan
        plan_path = (
            root
            / ".gstack"
            / "plans"
            / f"orch-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
        )
    elif not args.skip_spec:
        logger.error(
            "Provide --one-liner or --plan-path (or use --skip-spec with existing plan)."
        )
        return 1

    # Parse gates
    gates: set[str] = set()
    if args.gate:
        for g in args.gate:
            gates.add(g.strip())

    queue_path = root / "aos" / "approvals.jsonl"
    log_path = root / "aos" / "decisions.jsonl"
    gate_manager = GateManager(
        persistence_path=queue_path,
        decision_log_path=log_path,
    )

    ctx = PipelineContext(
        one_liner=args.one_liner,
        plan_path=plan_path,
        skip_spec=args.skip_spec,
        skip_plan=args.skip_plan,
        skip_review=args.skip_review,
        gates=gates,
        project_root=root,
        dry_run=args.dry_run,
        auto=args.auto,
        max_review_iterations=args.max_review_iterations,
    )

    pipeline = OrchestratePipeline(ctx, gate_manager)
    return pipeline.run()


def cmd_ventures(args: argparse.Namespace) -> int:
    """List all discovered ventures."""
    root = find_project_root()
    ventures_dir = root / "aos" / "ventures"

    ventures = discover_ventures(ventures_dir)

    if not ventures:
        print("No ventures found.")
        print(f" Searched: {ventures_dir}")
        print(" Add a venture by creating: <ventures_dir>/<name>/venture.yml")
        return 1

    print(f"AOS Ventures ({len(ventures)} found):")
    print()
    for path, venture in ventures:
        status_icon = {"active": "🟢", "planning": "🟡", "inactive": "⚫"}.get(
            venture.status, "❓"
        )
        print(f" {status_icon} {venture.name} ({venture.id})")
        print(f" Status: {venture.status}")
        print(f" Path: {path.parent}")
        if venture.description:
            desc = (
                venture.description[:80] + "..."
                if len(venture.description) > 80
                else venture.description
            )
            print(f" Desc: {desc}")
        print()

    print("Usage:")
    print(" python -m aos run --venture netso # Run cycle for Netso")
    print(" python -m aos run --venture transitbd # Run cycle for TransitBD")
    print(" python -m aos status --venture netso # Show Netso status")
    return 0


def cmd_approvals(args: argparse.Namespace) -> int:
    """Manage the approval queue."""
    from aos.approval_queue import ApprovalQueue, ApprovalDecision

    root = find_project_root()
    queue_path = root / "aos" / "approvals.jsonl"
    log_path = root / "aos" / "decisions.jsonl"
    queue = ApprovalQueue(persistence_path=queue_path, decision_log_path=log_path)

    action = args.approvals_action

    if action == "list" or action is None:
        print(queue.summary())
        return 0

    if action == "approve-all":
        note = getattr(args, "note", None)
        results = queue.approve_all(founder_note=note)
        print(f"Approved {len(results)} items.")
        for r in results:
            print(f" [{r.item_id}] {r.decision}")
        return 0

    if action == "reject-all":
        note = getattr(args, "note", None)
        results = queue.reject_all(founder_note=note)
        print(f"Rejected {len(results)} items.")
        for r in results:
            print(f" [{r.item_id}] {r.decision}")
        return 0

    if action == "approve":
        item_id = args.item_id
        note = getattr(args, "note", None)
        result = queue.decide(item_id, ApprovalDecision.APPROVE, founder_note=note)
        if result:
            print(f"Approved [{item_id}]")
        else:
            print(f"Item {item_id} not found or already decided.")
            return 1
        return 0

    if action == "reject":
        item_id = args.item_id
        note = getattr(args, "note", None)
        result = queue.decide(item_id, ApprovalDecision.REJECT, founder_note=note)
        if result:
            print(f"Rejected [{item_id}]")
        else:
            print(f"Item {item_id} not found or already decided.")
            return 1
        return 0

    print(
        "Usage: python -m aos approvals [list|approve-all|reject-all|approve ID|reject ID]"
    )
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    """Run a structured audit over a local artifact."""
    from aos.audit import AuditEngine

    report = AuditEngine.default().audit_path(args.path, args.type)
    print(f"Audit: {report.target} ({report.target_type})")
    print(f"Status: {report.status}")
    print(f"Findings: {len(report.findings)}; blocking: {len(report.blocking_findings)}")
    for finding in report.findings:
        location = f" [{finding.location}]" if finding.location else ""
        print(f"- {finding.severity.value.upper()} {finding.finding_id}{location}: {finding.evidence}")
        print(f"  Fix: {finding.recommendation}")
    return 1 if report.status == "blocked" else 0


def cmd_systems(args: argparse.Namespace) -> int:
    """List or inspect declarative reusable systems."""
    from aos.reusable import ReusableSystemRegistry

    registry = ReusableSystemRegistry.load_dir(find_project_root() / "aos" / "systems")
    if args.systems_action in (None, "list"):
        for system in registry.list():
            print(f"{system.id}: {system.name} — {system.purpose}")
        return 0
    system = registry.get(args.system_id)
    print(yaml.safe_dump(system.to_dict(), sort_keys=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="aos",
        description="AOS — Governance-first, multi-venture agentic operating system",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate all manifests")
    validate_parser.add_argument("--harness", help="Validate specific harness only")
    validate_parser.add_argument(
        "--venture", "-v", help="Validate against specific venture"
    )
    validate_parser.add_argument(
        "--verbose", action="store_true", help="Detailed output"
    )

    # status command
    status_parser = subparsers.add_parser("status", help="Show system status")
    status_parser.add_argument("--harness", help="Show specific harness status")
    status_parser.add_argument("--venture", "-v", help="Show specific venture status")

    # run command
    run_parser = subparsers.add_parser("run", help="Execute the daily harness cycle")
    run_parser.add_argument("--harness", help="Run specific harness only")
    run_parser.add_argument("--venture", "-v", help="Run against specific venture")
    run_parser.add_argument(
        "--dry-run", action="store_true", help="Dry run — no LLM calls"
    )
    run_parser.add_argument(
        "--prefer", choices=["router", "anthropic"], help="Force specific LLM backend"
    )
    run_parser.add_argument(
        "--verbose", action="store_true", help="Show LLM backend selection"
    )

    # ventures command
    subparsers.add_parser("ventures", help="List all discovered ventures")

    # orchestrate command
    orch_parser = subparsers.add_parser(
        "orchestrate",
        help="Run end-to-end pipeline: /spec → /autoplan → /implement → /reviewloop → /ship",
    )
    orch_parser.add_argument(
        "plan_path", nargs="?", help="Path to plan document (or use --one-liner)"
    )
    orch_parser.add_argument(
        "--one-liner", help="One-line description (triggers /spec)"
    )
    orch_parser.add_argument(
        "--skip-spec", action="store_true", help="Skip /spec phase"
    )
    orch_parser.add_argument(
        "--skip-plan", action="store_true", help="Skip /autoplan phase"
    )
    orch_parser.add_argument(
        "--skip-review", action="store_true", help="Skip /reviewloop phase"
    )
    orch_parser.add_argument(
        "--gate",
        action="append",
        help="Enforce gate(s): spec, plan, review (repeatable, default: all)",
    )
    orch_parser.add_argument(
        "--auto",
        action="store_true",
        help="Fast-lane: auto-approve gates when exit criteria are met",
    )
    orch_parser.add_argument(
        "--dry-run", action="store_true", help="Log actions without executing"
    )
    orch_parser.add_argument(
        "--max-review-iterations",
        type=int,
        default=3,
        help="Max review-fix iterations (default: 3)",
    )
    orch_parser.add_argument(
        "--autonomous",
        action="store_true",
        help="Run autonomous milestone pipeline (discuss/plan/execute loop)",
    )
    orch_parser.add_argument(
        "--roadmap-file",
        default="ROADMAP.md",
        help="Path to roadmap file for autonomous mode (default: ROADMAP.md)",
    )
    orch_parser.add_argument(
        "--gate-timeout",
        type=float,
        default=300.0,
        help="Seconds to wait for founder decision on approval gates (default: 300)",
    )
    orch_parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Max rollback retries per phase before hard stop (default: 3)",
    )

    # approvals command
    approvals_parser = subparsers.add_parser("approvals", help="Manage approval queue")
    approvals_sub = approvals_parser.add_subparsers(
        dest="approvals_action", help="Approval actions"
    )
    approvals_sub.add_parser("list", help="List pending approvals")
    aa_parser = approvals_sub.add_parser(
        "approve-all", help="Approve all pending approvals"
    )
    aa_parser.add_argument("--note", help="Founder note for all approvals")
    ra_parser = approvals_sub.add_parser(
        "reject-all", help="Reject all pending approvals"
    )
    ra_parser.add_argument("--note", help="Founder note for all rejections")
    approve_one = approvals_sub.add_parser("approve", help="Approve a specific item")
    approve_one.add_argument("item_id", help="Approval item ID (e.g. APR-0001)")
    approve_one.add_argument("--note", help="Founder note")
    reject_one = approvals_sub.add_parser("reject", help="Reject a specific item")
    reject_one.add_argument("item_id", help="Approval item ID")
    reject_one.add_argument("--note", help="Founder note")

    audit_parser = subparsers.add_parser("audit", help="Audit a local artifact")
    audit_parser.add_argument("path", help="File to audit")
    audit_parser.add_argument("--type", default="artifact", help="Target type")

    systems_parser = subparsers.add_parser("systems", help="Manage reusable systems")
    systems_sub = systems_parser.add_subparsers(dest="systems_action")
    systems_sub.add_parser("list", help="List reusable systems")
    show_system = systems_sub.add_parser("show", help="Show a reusable system")
    show_system.add_argument("system_id")

    args = parser.parse_args()

    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "orchestrate":
        return cmd_orchestrate(args)
    if args.command == "ventures":
        return cmd_ventures(args)
    if args.command == "approvals":
        return cmd_approvals(args)
    if args.command == "audit":
        return cmd_audit(args)
    if args.command == "systems":
        return cmd_systems(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
