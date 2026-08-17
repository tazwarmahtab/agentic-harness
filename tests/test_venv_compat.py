def test_venv_compat_hermes_paths_excluded():
    import sys
    from aos._venv_compat import clean_sys_path
    original = sys.path.copy()
    sys.path.insert(0, "/Users/tazwarmahtab/.hermes/hermes-agent/venv/lib/python3.11/site-packages")
    clean_sys_path()
    hermes_paths = [p for p in sys.path if "hermes-agent/venv" in p]
    assert len(hermes_paths) == 0, f"Hermes paths still in sys.path: {hermes_paths}"
    sys.path = original

def test_venv_compat_preserves_aos_paths():
    import sys
    from aos._venv_compat import clean_sys_path
    original = sys.path.copy()
    sys.path.insert(0, "/Users/tazwarmahtab/.hermes/hermes-agent/venv/lib/python3.11/site-packages")
    clean_sys_path()
    # Check that our project path (orca/agentic-harness) is preserved
    aos_paths = [p for p in sys.path if "orca/agentic-harness" in p or "10-Projects/Agentic Harness" in p or "uv" in p.lower()]
    assert len(aos_paths) > 0, "AOS project paths removed by clean_sys_path"
    sys.path = original
