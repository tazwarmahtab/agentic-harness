#!/usr/bin/env bash
# aos-daily.sh — Daily dev hygiene pipeline for AOS
# Usage: ./ops/aos-daily.sh [--skip-commit]
# Run from repo root. Exits on first failure (set -e).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SKIP_COMMIT=0
for arg in "$@"; do
  case "$arg" in
    --skip-commit) SKIP_COMMIT=1 ;;
  esac
done

cd "$REPO_ROOT"

echo "=== AOS Daily Hygiene ==="
echo "Repo: $REPO_ROOT"
echo "Time: $(date -u '+%Y-%m-%d %H:%M UTC')"
echo ""

# ── Pre-flight ────────────────────────────────────────────────────────
if [[ ! -d .venv ]]; then
  echo "ERROR: .venv not found. Run: python -m venv .venv && source .venv/bin/activate && pip install -e .[dev]"
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Copy from .env.example and fill secrets."
  exit 1
fi

source .venv/bin/activate

# ── Step 1: Lint ──────────────────────────────────────────────────────
echo "── Step 1/4: Lint (ruff) ──"
ruff check aos/ odysseus/ tests/
ruff format --check aos/ odysseus/ tests/ || {
  echo "Auto-formatting..."
  ruff format aos/ odysseus/ tests/
}
echo ""

# ── Step 2: Tests + Coverage ─────────────────────────────────────────
echo "── Step 2/4: Tests + Coverage ──"
pytest --cov=aos --cov=odysseus --cov-report=term-missing -q
echo ""

# ── Step 3: De-sloppify ──────────────────────────────────────────────
echo "── Step 3/4: De-sloppify ──"
claude -p "Review all .py files in aos/ and odysseus/ that appear modified (check git diff). Remove: print() debugging, commented-out blocks, type-system trivia tests (e.g. testing that dicts or isinstance work), and overly defensive None checks for impossible states. Keep all business-logic tests, evaluator checks, and security-relevant code. After cleanup, run pytest -q to confirm nothing breaks."
echo ""

# ── Step 4: Validate ─────────────────────────────────────────────────
echo "── Step 4/4: Validate ──"
python -m aos validate --verbose
echo ""

# ── Approvals sanity check ───────────────────────────────────────────
echo "── Approval queue ──"
python -m aos approvals list || true
echo ""

# ── Commit ────────────────────────────────────────────────────────────
if [[ "$SKIP_COMMIT" -eq 1 ]]; then
  echo "── Skipping commit (--skip-commit) ──"
  exit 0
fi

echo "── Commit ──"
git add -A
if git diff --cached --quiet; then
  echo "Nothing to commit. Working tree clean."
  exit 0
fi

claude -p "Create a conventional commit for all staged changes.
Message format: 'type: short description'
Types: feat, fix, refactor, test, chore, docs, perf, ci.
Include a body line with test count and known coverage %.
Examples:
  fix: correct evaluator DSCR floor check (aos/evaluator.py:45)
  chore: lint + format + dependency bump
  refactor: extract shell-exec regex patterns into security.py

Run: git commit -m \"<message>\""

echo ""
echo "=== Daily hygiene complete ==="
git log -1 --oneline
