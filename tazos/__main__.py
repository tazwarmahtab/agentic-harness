"""TAZ OS CLI entry point.

Usage:
    python -m tazos validate [--harness NAME] [--verbose]
    python -m tazos status [--harness NAME]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tazos.registry import load_registry
from tazos.validator import validate_all


def find_project_root() -> Path:
    """Find the tazos project root (where tazos/ package lives)."""
    return Path(__file__).parent.parent


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate all manifests."""
    root = find_project_root()
    harness_dir = root / "tazos" / "harnesses" / "executive"
    venture_path = root / "tazos" / "ventures" / "netso" / "venture.yml"

    if not harness_dir.exists():
        print(f"ERROR: Harness directory not found: {harness_dir}")
        return 1

    # If specific harness requested, use that path
    if args.harness:
        harness_dir = root / "tazos" / "harnesses" / args.harness
        if not harness_dir.exists():
            print(f"ERROR: Harness not found: {args.harness}")
            return 1

    print(f"Validating manifests in: {harness_dir}")
    if venture_path.exists():
        print(f"Venture: {venture_path}")

    result = validate_all(
        harness_dir=harness_dir,
        venture_path=venture_path if venture_path.exists() else None,
        verbose=args.verbose,
    )

    print()
    print(result.summary())
    return 0 if result.ok else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show system status."""
    root = find_project_root()
    harness_dir = root / "tazos" / "harnesses" / "executive"
    venture_path = root / "tazos" / "ventures" / "netso" / "venture.yml"

    if args.harness:
        harness_dir = root / "tazos" / "harnesses" / args.harness

    if not harness_dir.exists():
        print(f"ERROR: Harness directory not found: {harness_dir}")
        return 1

    registry = load_registry(
        harness_dir=harness_dir,
        venture_path=venture_path if venture_path.exists() else None,
    )

    print(registry.summary())
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
    validate_parser.add_argument("--verbose", "-v", action="store_true", help="Detailed output")

    # status command
    status_parser = subparsers.add_parser("status", help="Show system status")
    status_parser.add_argument("--harness", help="Show specific harness status")

    args = parser.parse_args()

    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "status":
        return cmd_status(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
