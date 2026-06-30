"""TAZ OS CLI entry point.

Usage:
    python -m tazos validate [--harness NAME] [--venture NAME] [--verbose]
    python -m tazos status [--harness NAME] [--venture NAME]
    python -m tazos run [--venture NAME] [--dry-run]
    python -m tazos ventures
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tazos.registry import load_registry
from tazos.validator import validate_all
from tazos.discover import discover_ventures, find_venture


def find_project_root() -> Path:
    """Find the tazos project root (where tazos/ package lives)."""
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
    harness_dir = root / "tazos" / "harnesses" / "executive"
    venture_path, venture_name = _resolve_venture(args.venture)

    if not harness_dir.exists():
        print(f"ERROR: Harness directory not found: {harness_dir}")
        return 1

    if args.harness:
        harness_dir = root / "tazos" / "harnesses" / args.harness
        if not harness_dir.exists():
            print(f"ERROR: Harness not found: {args.harness}")
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
    harness_dir = root / "tazos" / "harnesses" / "executive"
    venture_path, venture_name = _resolve_venture(args.venture)

    if args.harness:
        harness_dir = root / "tazos" / "harnesses" / args.harness

    if not harness_dir.exists():
        print(f"ERROR: Harness directory not found: {harness_dir}")
        return 1

    registry = load_registry(
        harness_dir=harness_dir,
        venture_path=venture_path if venture_path and venture_path.exists() else None,
    )

    print(registry.summary())
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Execute the daily harness cycle."""
    from tazos.runtime import run_from_path

    root = find_project_root()
    harness_dir = root / "tazos" / "harnesses" / "executive"
    venture_path, venture_name = _resolve_venture(args.venture)

    # If venture was requested but not found, fail with clear error
    if args.venture and venture_path is None:
        print(f"ERROR: Venture '{args.venture}' not found.")
        print("Available ventures:")
        for path, v in discover_ventures(root / "tazos" / "ventures"):
            print(f"  - {v.name} ({v.id})")
        return 1

    if args.harness:
        harness_dir = root / "tazos" / "harnesses" / args.harness
        if not harness_dir.exists():
            print(f"ERROR: Harness not found: {args.harness}")
            return 1

    if not harness_dir.exists():
        print(f"ERROR: Harness directory not found: {harness_dir}")
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

    ctx = run_from_path(
        harness_dir=harness_dir,
        venture_path=venture_path if venture_path and venture_path.exists() else None,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    print(ctx.summary())
    return 0 if ctx.ok else 1


def cmd_ventures(args: argparse.Namespace) -> int:
    """List all discovered ventures."""
    root = find_project_root()
    ventures_dir = root / "tazos" / "ventures"

    ventures = discover_ventures(ventures_dir)

    if not ventures:
        print("No ventures found.")
        print(f"  Searched: {ventures_dir}")
        print("  Add a venture by creating: <ventures_dir>/<name>/venture.yml")
        return 1

    print(f"TAZ OS Ventures ({len(ventures)} found):")
    print()
    for path, venture in ventures:
        status_icon = {"active": "🟢", "planning": "🟡", "inactive": "⚫"}.get(venture.status, "❓")
        print(f"  {status_icon} {venture.name} ({venture.id})")
        print(f"     Status: {venture.status}")
        print(f"     Path:   {path.parent}")
        if venture.description:
            desc = venture.description[:80] + "..." if len(venture.description) > 80 else venture.description
            print(f"     Desc:   {desc}")
        print()

    print("Usage:")
    print("  python -m tazos run --venture netso       # Run cycle for Netso")
    print("  python -m tazos run --venture transitbd    # Run cycle for TransitBD")
    print("  python -m tazos status --venture netso     # Show Netso status")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="tazos",
        description="TAZ OS — Governance-first, multi-venture agentic operating system",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # validate command
    validate_parser = subparsers.add_parser("validate", help="Validate all manifests")
    validate_parser.add_argument("--harness", help="Validate specific harness only")
    validate_parser.add_argument("--venture", "-v", help="Validate against specific venture")
    validate_parser.add_argument("--verbose", action="store_true", help="Detailed output")

    # status command
    status_parser = subparsers.add_parser("status", help="Show system status")
    status_parser.add_argument("--harness", help="Show specific harness status")
    status_parser.add_argument("--venture", "-v", help="Show specific venture status")

    # run command
    run_parser = subparsers.add_parser("run", help="Execute the daily harness cycle")
    run_parser.add_argument("--harness", help="Run specific harness only")
    run_parser.add_argument("--venture", "-v", help="Run against specific venture")
    run_parser.add_argument("--dry-run", action="store_true", help="Dry run — no LLM calls")
    run_parser.add_argument("--prefer", choices=["router", "anthropic"], help="Force specific LLM backend")
    run_parser.add_argument("--verbose", action="store_true", help="Show LLM backend selection")

    # ventures command
    subparsers.add_parser("ventures", help="List all discovered ventures")

    args = parser.parse_args()

    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "run":
        return cmd_run(args)
    if args.command == "ventures":
        return cmd_ventures(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
