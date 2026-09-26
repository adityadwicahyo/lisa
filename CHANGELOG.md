# Changelog

All notable changes to Lisa are listed here. Versions follow [semantic versioning](https://semver.org):
new features raise the middle number, fixes the last one. Releases are made automatically when `develop` is merged
into `main`.

## [0.2.0] - 2026-09-26

### Added
- Answer "keep it", "wait" or "I'll edit it" to "Shall I send it?" to leave the typed prompt for you to edit.
- A new "Lisa, …" replaces a prompt she left unsent, unless you edited or sent it yourself.
- `lisa status` shows ON or OFF for each part, what it means, and how much memory each part uses.
- `lisa version`.

### Changed
- Voice prompts start with a capital letter: "Lisa, do something" types "Do something".
- Silence or an unclear answer to "Shall I send it?" keeps the text instead of erasing it; only a "no" erases.
  She waits 4 seconds for an answer instead of 6.
- "Wait", "hold on" and "not yet" keep the text; the send, erase and keep word lists were tidied up.
- Clearer "Talking to Lisa" section in the README, and corrected memory figures.

### Fixed
- Short answers such as "Cancel that" and "Never mind" were often misheard and kept the text. Answers are now
  recognized by the `base.en` model with a short hint of the expected words.

## [0.1.0] - 2026-09-26

### Added
- First public version: Lisa greets you, says what Claude is doing, and reads the first paragraph of Claude's
  replies aloud, fully offline (Kokoro text-to-speech).
- Voice prompts: "Lisa, <prompt>" is typed into Claude Code, and she asks "Shall I send it?" before pressing Enter.
- Voice commands: "Lisa, never mind", "Lisa, stop listening" and "Lisa, off".
- Optional voiceprint (`lisa enroll`) so only your voice is accepted.
- The `lisa` command (`on`, `off`, `mic on`, `mic off`, `status`, `generate`, `voices`) and `lisa install`, which
  sets up the Claude Code hooks, the `/lisa` command and the PATH entry.

[0.2.0]: https://github.com/adityadwicahyo/lisa/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/adityadwicahyo/lisa/releases/tag/v0.1.0
