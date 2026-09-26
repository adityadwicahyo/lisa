import pytest

from lisa import __version__, cli

MB = 2 ** 20


@pytest.fixture
def machine(monkeypatch):
    """A fake machine: which processes run, whether Claude Code is open, whether it's plugged in, memory in use."""
    facts = {"listener": True, "claude": True, "plugged_in": True, "enrolled": False,
             "memory": (400 * MB, 100 * MB, 0)}
    monkeypatch.setattr(cli, "is_running", lambda port: facts["listener"])
    monkeypatch.setattr(cli, "claude_code_running", lambda config: facts["claude"])
    monkeypatch.setattr(cli, "on_ac_power", lambda: facts["plugged_in"])
    monkeypatch.setattr(cli, "VOICEPRINT_FILE", type("File", (), {"exists": lambda self: facts["enrolled"]})())
    monkeypatch.setattr(cli, "memory_by_part", lambda config: facts["memory"])
    return facts


def status(monkeypatch, config, enabled=True, listening=True):
    monkeypatch.setattr(cli, "load_state", lambda: {"enabled": enabled, "listening": listening})
    return cli.status_text(config)


def row(text, name):
    return " ".join(next(line for line in text.splitlines() if line.strip().startswith(name)).split())


def test_on(monkeypatch, config, machine):
    text = status(monkeypatch, config)
    assert text.splitlines()[0].split() == ["Lisa", __version__, "is", "ON", "Memory"]
    assert row(text, "Speaking") == "Speaking ON Reads Claude's replies and says what Claude is doing 400 MB"
    assert row(text, "Microphone") == 'Microphone ON Say "Lisa, ..." 100 MB'
    assert row(text, "Voice check") == ("Voice check OFF Anyone's voice is accepted; set it up with `lisa enroll` -")
    assert row(text, "Total") == "Total 500 MB"
    assert "Other" not in text


def test_off_shows_everything_off_and_how_to_get_it_back(monkeypatch, config, machine):
    machine["memory"] = (0, 0, 0)
    text = status(monkeypatch, config, enabled=False)
    assert text.startswith(f"Lisa {__version__} is OFF")
    assert row(text, "Speaking") == "Speaking OFF Turn on with `lisa on` 0 MB"
    assert row(text, "Microphone") == "Microphone OFF Comes back on with `lisa on` 0 MB"
    assert row(text, "Total") == "Total 0 MB"


def test_leftover_processes_are_counted(monkeypatch, config, machine):
    machine["memory"] = (0, 0, 30 * MB)
    text = status(monkeypatch, config, enabled=False)
    assert row(text, "Other").endswith("30 MB")
    assert row(text, "Total") == "Total 30 MB"


def test_mic_switched_off(monkeypatch, config, machine):
    assert "Microphone OFF Turn on with `lisa mic on`" in row(status(monkeypatch, config, listening=False),
                                                                "Microphone")


@pytest.mark.parametrize("facts, expected", [
    ({"plugged_in": False}, "Microphone OFF Paused on battery; listens again when plugged in"),
    ({"listener": False, "claude": False}, "Microphone OFF Starts when Claude Code opens"),
    ({"listener": False}, "Microphone OFF Not running; start it with `lisa mic on`"),
    ({"enrolled": True}, "Voice check ON Only your voice is accepted"),
])
def test_each_line_says_on_or_off_and_why(monkeypatch, config, machine, facts, expected):
    machine.update(facts)
    text = status(monkeypatch, config)
    assert row(text, expected.split(" ON ")[0].split(" OFF ")[0]).startswith(expected)
