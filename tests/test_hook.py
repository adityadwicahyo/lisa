import json

import pytest

from lisa.config import merge
from lisa.hook.transcript import classify_turn, final_reply
from lisa.install import is_lisa_hook, set_hooks


def write_transcript(path, entries):
    path.write_text("\n".join(json.dumps(entry) for entry in entries), encoding="utf-8")
    return str(path)


def prompt(text):
    return {"type": "user", "message": {"content": text}, "timestamp": "2026-09-17T08:00:00Z"}


def assistant(*content, timestamp="2026-09-17T08:00:05Z", sidechain=False):
    return {"type": "assistant", "isSidechain": sidechain, "message": {"content": list(content)},
            "timestamp": timestamp}


def tool_use(name, **tool_input):
    return {"type": "tool_use", "name": name, "input": tool_input}


def text(value):
    return {"type": "text", "text": value}


@pytest.mark.parametrize("entries, category", [
    ([prompt("go"), assistant(text("Which one do you want?"))], "question"),
    ([prompt("go"), assistant(tool_use("Bash", command="./gradlew test")), assistant(text("Done."))], "build"),
    ([prompt("go"), assistant(tool_use("Edit", file_path="a.kt")), assistant(text("Done."))], "edits"),
    ([prompt("go"), assistant(*[tool_use("Read", file_path="a.kt")] * 5), assistant(text("Found it."))], "research"),
    ([prompt("go"), assistant(text("Done."), timestamp="2026-09-17T08:05:00Z")], "long"),
    ([prompt("go"), assistant(text("Done."))], "quick"),
])
def test_classify_turn(tmp_path, config, entries, category):
    assert classify_turn(write_transcript(tmp_path / "t.jsonl", entries), config) == category


def test_classify_turn_only_looks_at_the_latest_prompt_and_main_thread(tmp_path, config):
    entries = [prompt("first"), assistant(tool_use("Edit", file_path="a.kt")),
               prompt("second"), assistant(tool_use("Edit", file_path="b.kt"), sidechain=True),
               assistant(text("Done."))]
    assert classify_turn(write_transcript(tmp_path / "t.jsonl", entries), config) == "quick"


def test_final_reply_is_the_last_assistant_text(tmp_path):
    path = write_transcript(tmp_path / "t.jsonl", [prompt("go"), assistant(text("Working.")),
                                                   assistant(text("All done."))])
    assert final_reply({"transcript_path": path}, max_wait_seconds=0) == "All done."


def test_merge_overrides_only_the_given_keys():
    merged = merge({"events": {"a": True, "b": True}, "x": 1}, {"events": {"b": False}})
    assert merged == {"events": {"a": True, "b": False}, "x": 1}


def test_install_keeps_other_hooks_and_replaces_old_lisa_hooks(tmp_path, monkeypatch, config):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({
        "theme": "dark",
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "python D:/old/lisa_hook.py"},
                                      {"type": "command", "command": "notify-me"}]}]},
    }), encoding="utf-8")
    monkeypatch.setenv("LISA_CLAUDE_SETTINGS", str(settings_file))

    set_hooks(config, install=True)
    settings = json.loads(settings_file.read_text(encoding="utf-8"))
    assert settings["theme"] == "dark"
    stop_commands = [hook["command"] for group in settings["hooks"]["Stop"] for hook in group["hooks"]]
    assert "notify-me" in stop_commands
    assert sum(is_lisa_hook({"command": command}) for command in stop_commands) == 1
    assert all("-m lisa.hook" in command for command in stop_commands if command != "notify-me")
    assert set(settings["hooks"]) == {"SessionStart", "UserPromptSubmit", "PreToolUse", "Notification", "Stop"}

    set_hooks(config, install=False)
    settings = json.loads(settings_file.read_text(encoding="utf-8"))
    assert settings["hooks"] == {"Stop": [{"hooks": [{"type": "command", "command": "notify-me"}]}]}


def test_broken_claude_settings_are_never_overwritten(tmp_path, monkeypatch, config):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{ not json", encoding="utf-8")
    monkeypatch.setenv("LISA_CLAUDE_SETTINGS", str(settings_file))
    with pytest.raises(json.JSONDecodeError):
        set_hooks(config, install=True)
    assert settings_file.read_text(encoding="utf-8") == "{ not json"
