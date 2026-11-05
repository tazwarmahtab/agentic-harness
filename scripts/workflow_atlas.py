"""Render the source-linked atlas, or check whether its evidence has changed.

Run from any directory. --check never refreshes fingerprints or writes files.
Default rendering refuses stale evidence; --refresh requires human source review.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/architecture/workflow-atlas.json"
OUTPUT = ROOT / "docs/architecture/workflow-atlas.html"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    data = json.loads(MANIFEST.read_text())
    identifiers = [step["id"] for step in data["steps"]]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate step IDs")
    current = {}
    for step in data["steps"]:
        if step["status"] not in {"implemented", "gap", "proposed"}:
            raise ValueError("Unknown status")
        for ref in step["sources"]:
            target = (ROOT / ref["path"]).resolve()
            if not target.is_relative_to(ROOT) or not target.is_file():
                raise ValueError(f"Missing or unsafe source: {ref['path']}")
            raw = target.read_bytes()
            if ref["anchor"] not in raw.decode():
                raise ValueError(f"Missing source anchor: {ref}")
            current[ref["path"]] = hashlib.sha256(raw).hexdigest()
    stale = current != data.get("fingerprints", {})
    if stale and not args.refresh:
        print("STALE: review source changes, update the atlas, then use --refresh")
        return 1
    if args.check:
        print(
            f"PASS: {len(identifiers)} steps; {len(current)} source fingerprints and anchors match"
        )
        print(
            "This checks evidence freshness, not completeness or runtime correctness."
        )
        return 0
    if args.refresh:
        data["fingerprints"] = current
        MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    esc = html.escape
    cards = []
    for step in data["steps"]:
        refs = "".join(
            '<li><a href="../../'
            + esc(ref["path"], quote=True)
            + '">'
            + esc(ref["path"])
            + "</a> · <code>"
            + esc(ref["anchor"])
            + "</code></li>"
            for ref in step["sources"]
        )
        body = "".join(
            "<dt>" + esc(label) + "</dt><dd>" + esc(step[key]) + "</dd>"
            for key, label in [
                ("owner", "Owner"),
                ("input", "Input / trigger"),
                ("output", "Output / completion"),
                ("failure", "Exception / recovery"),
                ("check", "Evidence / acceptance"),
            ]
        )
        cards.append(
            '<article data-status="'
            + step["status"]
            + '"><small>'
            + esc(step["id"])
            + " · "
            + step["status"].upper()
            + "</small><h2>"
            + esc(step["title"])
            + "</h2><p>"
            + esc(step["summary"])
            + "</p><details><summary>Inspect step and sources</summary><dl>"
            + body
            + "</dl><ul>"
            + refs
            + "</ul></details></article>"
        )
    page = (
        """<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Founder OS — Workflow Atlas</title>
<style>
:root{color-scheme:dark;font:16px/1.55 system-ui;background:#101816;color:#e8f0eb}
body{max-width:1150px;margin:auto;padding:24px}h1{font-size:clamp(28px,5vw,46px);line-height:1.15}
a{color:#9ee2bb}header p{max-width:82ch}nav{display:flex;gap:10px;flex-wrap:wrap;margin:24px 0}
button{font:inherit;padding:10px 16px;border:1px solid #658071;background:#1b2c23;color:inherit;border-radius:8px;cursor:pointer}
button[aria-pressed=true]{background:#365b45}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,330px),1fr));gap:16px}
article{padding:20px;border:1px solid #52685b;border-top:4px solid #88d5a7;border-radius:10px;overflow-wrap:anywhere}
article[data-status=gap]{border-top-color:#efbb6c}article[data-status=proposed]{border-top-color:#a9b5f2}
article[hidden]{display:none}h2{font-size:21px;margin:8px 0}small{letter-spacing:.05em}summary{cursor:pointer;color:#b6dec4}
dt{font-weight:700;margin-top:12px}dd{margin:0}ul{padding-left:20px}code{font-size:13px}.notice{padding:14px;border:1px solid #a58b5a;border-radius:8px}
:focus-visible{outline:3px solid #ffe0a6;outline-offset:4px}footer{margin-top:32px}
</style><header><p>FOUNDER OS / AOS / NETSO OS · 31 OCTOBER 2026</p>
<h1>Work, evidence, decisions.</h1>
<p>A working atlas of the prospect slice and proposed shared services. Read in numbered order, expand a step, or filter by status. This is not an exhaustive map of every legacy module.</p>
<p class="notice">Implemented = present in inspected source. Historical test results are recorded in the delivery ledger; they have not been rerun for this documentation update. Proposed services are not enabled. Run the freshness check before relying on this snapshot.</p>
<p><a href="founder-os-next-design.md">Decisions and priority backlog</a> · <a href="workflow-atlas.json">Structured inventory</a></p></header>
<nav aria-label="Filter steps"><button data-filter="all" aria-pressed="true">All steps</button><button data-filter="implemented" aria-pressed="false">Implemented</button><button data-filter="gap" aria-pressed="false">Gaps</button><button data-filter="proposed" aria-pressed="false">Proposed</button></nav>
<p id="count" aria-live="polite"></p><main>"""
        + "\n".join(cards)
        + """</main>
<footer>Source links open repository files when used in a checkout. A standalone downloaded HTML retains all descriptions but may not resolve those relative links. No network requests, analytics, credentials, or third-party assets.</footer>
<script>
const cards=[...document.querySelectorAll('article')];
function filter(value){let count=0;for(const card of cards){card.hidden=value!=='all'&&card.dataset.status!==value;if(!card.hidden)count++}
document.querySelector('#count').textContent=count+' steps shown';
for(const b of document.querySelectorAll('button'))b.setAttribute('aria-pressed',String(b.dataset.filter===value));}
for(const b of document.querySelectorAll('button'))b.addEventListener('click',()=>filter(b.dataset.filter));filter('all');
</script></html>"""
    )
    OUTPUT.write_text(page)
    print(f"Rendered {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
