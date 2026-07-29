from aos.morning_brief import generate_brief


def test_generate_brief_returns_string():
    brief = generate_brief(venture="netso")
    assert isinstance(brief, str)


def test_generate_brief_includes_date():
    brief = generate_brief(venture="netso")
    from datetime import date
    today = date.today().isoformat()
    assert today in brief


def test_generate_brief_includes_venture():
    brief = generate_brief(venture="netso")
    assert "NETSO" in brief


def test_generate_brief_has_sections():
    brief = generate_brief(venture="netso")
    assert "Cycles run" in brief
    assert "Approvals pending" in brief
    assert "Tokens used" in brief
    assert "Est. cost" in brief


def test_generate_brief_default_venture():
    brief = generate_brief()
    assert "NETSO" in brief
