"""Validate the portable Netso Agent Companies package without network access."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "companies" / "netso-energy"
EXPECTED_AGENTS = {
    "ceo": None,
    "coo": "ceo",
    "cfo": "ceo",
    "cro": "ceo",
    "cto": "ceo",
    "legal": "ceo",
}
REQUIRED_SKILLS = {
    "founder-governance",
    "source-of-truth",
    "project-development",
    "financial-controls",
    "sales-qualification",
}


def frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise AssertionError("missing YAML frontmatter")
    data: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith(" "):
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip("'\"")
    return data


def main() -> None:
    company = ROOT / "COMPANY.md"
    assert company.exists(), "COMPANY.md is missing"
    company_meta = frontmatter(company.read_text())
    assert company_meta.get("schema") == "agentcompanies/v1"
    assert company_meta.get("slug") == "netso-energy"

    skills_dir = ROOT / "skills"
    available_skills = {p.name for p in skills_dir.iterdir() if p.is_dir()}
    assert REQUIRED_SKILLS <= available_skills, (
        f"missing skills: {sorted(REQUIRED_SKILLS - available_skills)}"
    )

    for slug, reports_to in EXPECTED_AGENTS.items():
        path = ROOT / "agents" / slug / "AGENTS.md"
        assert path.exists(), f"missing agent file: {path}"
        meta = frontmatter(path.read_text())
        assert meta.get("schema") == "agentcompanies/v1", slug
        assert meta.get("kind") == "agent", slug
        assert meta.get("slug") == slug, slug
        assert meta.get("reportsTo") == (reports_to or "null"), (slug, meta)

    print("Netso Agent Companies package: OK")


if __name__ == "__main__":
    main()
