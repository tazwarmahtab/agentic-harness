"""Local founder CLI. File arguments are explicit operator-selected inputs."""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

from aos.prospects.models import Intake, Upload
from aos.prospects.routes import get_store


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "prospects", help="Source-linked prospect briefs (local, no model calls)"
    )
    actions = parser.add_subparsers(dest="prospect_action", required=True)
    for name in ("create", "generate", "show", "list", "review"):
        command = actions.add_parser(name)
        command.add_argument("--venture", required=True)
        command.add_argument("--project", required=True)
        if name in ("generate", "show", "review"):
            command.add_argument("--id", required=True)
        if name == "create":
            command.add_argument("--prospect", required=True)
            command.add_argument("--purpose", required=True)
            command.add_argument("--files", nargs="+", required=True)
        if name == "review":
            command.add_argument("--hash", required=True)
            command.add_argument(
                "--decision", choices=("approve", "reject", "defer"), required=True
            )


def run(args: argparse.Namespace) -> int:
    store = get_store()
    try:
        result: dict[str, Any] | list[dict[str, Any]]
        action = args.prospect_action
        if action == "create":
            docs = []
            for name in args.files:
                path = Path(name)
                if path.stat().st_size > 5 * 1024 * 1024:
                    raise ValueError("Document exceeds 5 MiB")
                docs.append(
                    {
                        "filename": path.name,
                        "content_b64": base64.b64encode(path.read_bytes()).decode(),
                    }
                )
            result = store.create(
                Intake(
                    venture=args.venture,
                    project=args.project,
                    prospect=args.prospect,
                    purpose=args.purpose,
                    documents=[Upload.model_validate(document) for document in docs],
                )
            )
        elif action == "list":
            result = store.list(args.venture, args.project)
        elif action == "review":
            result = store.review(
                args.id,
                args.venture,
                args.project,
                args.hash,
                args.decision,
                "local-founder",
            )
        elif action == "generate":
            result = store.generate(args.id, args.venture, args.project)
        else:
            result = store.get(args.id, args.venture, args.project)
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return 0
    except (ValueError, KeyError, OSError) as exc:
        sys.stderr.write(str(exc) + "\n")
        return 1
