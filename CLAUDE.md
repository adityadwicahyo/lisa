# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Lisa is an offline voice assistant for Claude Code on Windows: Claude Code hooks that speak (Kokoro TTS),
plus a microphone listener that types "Lisa, <prompt>" into Claude Code (faster-whisper). Windows-only
(`winsound`, `msvcrt`, `ctypes` Win32 calls). User docs: README.md; design: docs/architecture.md; every
setting: docs/configuration.md.

## Commands

Use the venv interpreter; the package is installed editable (`pip install -e ".[voice-check,piper,dev]"`).

```powershell
.\.venv\Scripts\python.exe -m pytest                      # all tests
.\.venv\Scripts\python.exe -m pytest tests\test_language.py -k cancel   # one area
.\lisa.cmd status                                         # or: python -m lisa.cli <command>
.\lisa.cmd generate [category]                            # re-render clips after voice/phrase changes

# Run the hook by hand (LISA_CLAUDE_SETTINGS keeps it away from your real Claude settings)
'{"hook_event_name":"PreToolUse","tool_name":"Read","tool_input":{"file_path":"C:/x/LoginViewModel.kt"}}' | .\.venv\Scripts\python.exe -m lisa.hook
```

Logs: `.lisa/logs/hook.log`, `server.log`, `listener.log`.

## Architecture in brief

- `lisa.hook` runs on every Claude Code event. It and everything it imports (`text`, `speech.clips`,
  `speech.client`, `state`, `system`, `config`, `paths`, `log`) must stay **standard-library only** and fast;
  heavy work goes to detached processes via `system.spawn`. It must never fail Claude Code: `handle()` wraps
  each reaction and logs errors; the process always exits 0.
- `lisa.speech.server` (live TTS) and `lisa.listener` (microphone) are single-instance background processes:
  the bound port is the lock, and they take one-shot JSON messages (`system.send_message`).
- All audio from any process holds `speech.player.playback_lock`; the listener ignores the mic while it's held.
- Settings: `config.load_config()` merges `config.default.json` with the user's `config.json`. Defaults live
  only in `config.default.json`; code reads `config[section][key]` without fallbacks, and every new key must
  be added there and to docs/configuration.md.
- Word rules for the listener are pure functions in `listener/language.py`; add tests in
  `tests/test_language.py` when changing them.

## Releasing

Work happens on `develop`; never commit to `main` directly. Merging `develop` into `main` and pushing is a release:
the Release workflow runs `scripts/release.py`, which picks the version from the commit **headers** since the last
tag (any `feat` -> minor, else `fix`/`perf` -> patch, else no release; bodies are ignored because they always start
with "BREAKING CHANGES:"), writes `lisa/__init__.py` and a CHANGELOG.md section, commits
`chore(release): release X.Y.Z` to main, tags `vX.Y.Z`, publishes the GitHub Release and fast-forwards `develop`.
After a release, `git pull` on both branches. For a bigger jump (1.0.0) or hand-written notes, set `__version__`
and/or write the CHANGELOG section on `develop` before merging; the script uses them. The Tests workflow runs
pytest on Windows for pushes to both branches.

```powershell
git checkout main; git pull; git merge develop; git push; git checkout develop   # release
.\.venv\Scripts\python.exe scripts\release.py --dry-run                         # preview what would be released
```

## Gotchas

- A running server or listener keeps its old code: after editing them, restart (`lisa off`/`lisa on`, or
  `lisa mic off`/`lisa mic on`).
- Claude Code reads hook commands at session start, so a session started before `lisa install` still runs
  the old command until restarted.
- Audio tests without a microphone: synthesize speech with `speech.engines.create_engine`, resample to 16 kHz
  and feed 1280-sample chunks to `Listener.collect_sentence` (example in docs/architecture.md). Stub
  `Listener.say`, not `sounds.say`, or queued answer audio is cleared.
