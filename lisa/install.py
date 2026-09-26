"""`lisa install` / `lisa uninstall`: connect Lisa to Claude Code and Windows, using wherever this folder is.

Install: downloads the voice model, generates the clips, adds the hooks to ~/.claude/settings.json (keeping
everything else), creates the /lisa command and puts `lisa` on your PATH. Uninstall reverses all of it.
"""

import ctypes
import json
import subprocess
import sys
import winreg
from pathlib import Path

from lisa.download import download
from lisa.hook.loading_words import update_claude_settings
from lisa.paths import AUDIO_DIR, KOKORO_DIR, PHRASES_FILE, ROOT
from lisa.speech.engines import KOKORO_FILES

HOOK_EVENTS = ["SessionStart", "UserPromptSubmit", "PreToolUse", "Notification", "Stop"]
COMMAND_FILE = Path.home() / ".claude" / "commands" / "lisa.md"


def python_path():
    return Path(sys.executable).as_posix()


def hook_command():
    return f'"{python_path()}" -m lisa.hook'


def is_lisa_hook(hook):
    command = str(hook.get("command", ""))
    return "-m lisa.hook" in command or "lisa_hook.py" in command  # lisa_hook.py: installs before version 0.1


def set_hooks(config, install):
    """Add (or remove) Lisa's hook for each event, leaving your other hooks and settings untouched.

    :param config: Settings; uses `claude_settings_path`
    :param install: False removes them
    """
    def change(settings):
        hooks = settings.setdefault("hooks", {})
        for event in HOOK_EVENTS:
            groups = []
            for group in hooks.get(event, []):
                kept = [hook for hook in group.get("hooks", []) if not is_lisa_hook(hook)]
                if kept:
                    groups.append({**group, "hooks": kept})
            if install:
                group = {"hooks": [{"type": "command", "command": hook_command(), "timeout": 10}]}
                groups.append({"matcher": "", **group} if event == "PreToolUse" else group)
            if groups:
                hooks[event] = groups
            else:
                hooks.pop(event, None)
        if not hooks:
            settings.pop("hooks")
        return True

    update_claude_settings(config, change)


def write_command_file():
    """The /lisa command for Claude Code: runs `lisa <arguments>` and reports the status."""
    COMMAND_FILE.parent.mkdir(parents=True, exist_ok=True)
    command = f"{python_path()} -m lisa.cli"
    COMMAND_FILE.write_text(f"""---
description: Turn Lisa on or off (on, off, mic on, mic off, status)
argument-hint: on | off | mic on | mic off | status
allowed-tools: Bash({command}:*)
---

!`{command} $ARGUMENTS`

Lisa's switch was run with the arguments "$ARGUMENTS" and printed the status above. Reply with that status in one short line and do nothing else.
""", encoding="utf-8")


def set_user_path(install):
    """Add (or remove) this folder on the user PATH, so `lisa` works in new terminals.

    :param install: False removes it
    """
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            value, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            value, kind = "", winreg.REG_EXPAND_SZ
        entries = [entry for entry in value.split(";") if entry and entry.rstrip("\\") != str(ROOT)]
        if install:
            entries.append(str(ROOT))
        winreg.SetValueEx(key, "Path", 0, kind, ";".join(entries))
    # Tell Explorer the environment changed, so terminals opened from now on see it.
    result = ctypes.c_ulong()
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x1A, 0, "Environment", 0x2, 3000, ctypes.byref(result))


def package_importable_anywhere():
    """The hooks run from other folders, so the package must be installed (`pip install -e .`), not just present."""
    check = subprocess.run([sys.executable, "-c", "import lisa"], cwd=Path.home(), capture_output=True)
    return check.returncode == 0


def install(config):
    if not package_importable_anywhere():
        print("Run `pip install -e .` in this folder first (inside the virtual environment), then `lisa install`.")
        return 1

    if config["voice"]["engine"] == "kokoro":
        for name, url in KOKORO_FILES.items():
            download(url, KOKORO_DIR / name)

    phrases = json.loads(PHRASES_FILE.read_text(encoding="utf-8"))
    if any(not (AUDIO_DIR / category).exists() for category in phrases):
        from lisa.speech.generate import generate

        print("Generating Lisa's voice clips (a few minutes)...")
        generate(config)

    set_hooks(config, install=True)
    write_command_file()
    set_user_path(install=True)
    print(f"\nInstalled. Lisa's hooks are in {config['claude_settings_path']}, /lisa works in Claude Code, and")
    print("`lisa` works in new terminals. Restart Claude Code to start using her.")
    return 0


def uninstall(config):
    from lisa import cli

    cli.turn_off(config)
    set_hooks(config, install=False)
    if COMMAND_FILE.exists() and "lisa.cli" in COMMAND_FILE.read_text(encoding="utf-8"):
        COMMAND_FILE.unlink()
    set_user_path(install=False)
    print("Uninstalled: hooks, /lisa and the PATH entry are removed. Delete this folder to remove Lisa completely.")
    return 0
