"""Tests for aos._venv_compat.clean_sys_path.

The utility's contract is narrow: remove sys.path entries containing
"hermes-agent/venv" and preserve everything else. These tests insert
controlled sentinel entries and assert exactly that, so they hold on
any machine. The previous preserves test instead asserted that the
ambient sys.path contained the author's own checkout fragments
("orca/agentic-harness", "10-Projects/Agentic Harness", "uv"), so it
failed on every other machine even though the code was correct.
"""

import sys

import pytest

from aos._venv_compat import clean_sys_path

HERMES_PATH = (
    "/Users/tazwarmahtab/.hermes/hermes-agent/venv/lib/python3.11/site-packages"
)


@pytest.fixture
def restored_sys_path():
    original = sys.path.copy()
    yield
    sys.path = original


def test_venv_compat_hermes_paths_excluded(restored_sys_path):
    sys.path.insert(0, HERMES_PATH)
    clean_sys_path()
    hermes_paths = [p for p in sys.path if "hermes-agent/venv" in p]
    assert hermes_paths == []


def test_venv_compat_preserves_aos_paths(restored_sys_path):
    # Sentinels stand in for the paths the original test hoped to find
    # in the ambient sys.path: a project checkout, a venv, and a
    # uv-managed interpreter path. Inserted explicitly, they test the
    # preservation half of the contract deterministically.
    sentinels = [
        "/srv/agentic-harness",
        "/home/dev/.venv/lib/python3.12/site-packages",
        "/home/dev/.local/share/uv/python/cpython-3.12/lib/python3.12",
    ]
    sys.path.insert(0, HERMES_PATH)
    for sentinel in sentinels:
        sys.path.insert(0, sentinel)
    clean_sys_path()
    for sentinel in sentinels:
        assert sentinel in sys.path
    assert HERMES_PATH not in sys.path
