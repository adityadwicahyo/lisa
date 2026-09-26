"""The Claude Code hook (`python -m lisa.hook`), run on every SessionStart, UserPromptSubmit, PreToolUse,
Notification and Stop event.

It must start fast and never break Claude Code, so it and everything it imports use only the standard library,
anything slow runs in a detached process, and every error is logged instead of raised.
"""
