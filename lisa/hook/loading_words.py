"""Loading-word sync (`events.loading_word`, off by default): Lisa says the word Claude Code shows while working.

Claude Code picks its loading word ("Zigzagging…") from the `spinnerVerbs` setting when a turn starts, and hooks
can't see which one. So after each turn Lisa picks the next word herself, pins it as the only spinner verb in
~/.claude/settings.json, and plays that word's clip when you send your next prompt.
"""

import json
import os
import random
import time
from pathlib import Path

from lisa.paths import LOADING_WORDS_FILE, NEXT_LOADING_WORD_FILE


def claude_settings_path(config):
    path = os.environ.get("LISA_CLAUDE_SETTINGS") or config["claude_settings_path"]
    return Path(path).expanduser()


def update_claude_settings(config, change):
    """Apply `change(settings) -> bool` to Claude Code's settings file, writing only when it returns True.

    A settings file that isn't valid JSON raises before anything is written, so it is never overwritten.

    :param config: Settings; uses `claude_settings_path`
    :param change: Edits the parsed settings in place and says whether anything changed
    """
    path = claude_settings_path(config)
    settings = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    if not change(settings):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(path.name + ".lisa-tmp")
    temp_path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for attempt in range(5):
        try:
            os.replace(temp_path, path)
            return
        except PermissionError:  # Claude Code may be reading the file at this moment.
            if attempt == 4:
                raise
            time.sleep(0.05)


def next_word():
    try:
        return NEXT_LOADING_WORD_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def queue_next_word(config):
    """Pick the loading word for the next turn and pin it as Claude Code's only spinner verb.

    :param config: Settings
    """
    words = json.loads(LOADING_WORDS_FILE.read_text(encoding="utf-8"))
    current = next_word()
    word = random.choice([w for w in words if w != current] or words)

    def pin(settings):
        settings["spinnerVerbs"] = {"mode": "replace", "verbs": [word]}
        return True

    update_claude_settings(config, pin)
    NEXT_LOADING_WORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    NEXT_LOADING_WORD_FILE.write_text(word, encoding="utf-8")


def restore(config):
    """Give Claude Code its own loading words back (`lisa off`, `lisa uninstall`).

    :param config: Settings
    """
    update_claude_settings(config, lambda settings: settings.pop("spinnerVerbs", None) is not None)
    NEXT_LOADING_WORD_FILE.unlink(missing_ok=True)
