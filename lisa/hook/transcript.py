"""Reads the Claude Code transcript (JSONL) to see what happened in the turn that just ended."""

import json
import time
from datetime import datetime

RESEARCH_TOOLS = {"Read", "Grep", "Glob", "LS", "WebFetch", "WebSearch", "Task", "Agent"}
EDIT_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}


def read_last_turn(transcript_path):
    """Main-thread transcript entries since your latest prompt (subagent entries are skipped).

    :param transcript_path: Path from the hook payload
    """
    try:
        with open(transcript_path, encoding="utf-8") as file:
            lines = file.readlines()
    except OSError:
        return []

    turn = []
    for line in lines:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("isSidechain") or entry.get("type") not in ("user", "assistant"):
            continue
        if entry["type"] == "user" and not entry.get("isMeta") and is_prompt(entry):
            turn = []
        turn.append(entry)
    return turn


def is_prompt(entry):
    """True for a user entry you typed, as opposed to a tool result Claude Code sends back as a user entry."""
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        types = {item.get("type") for item in content if isinstance(item, dict)}
        return "tool_result" not in types and "text" in types
    return False


def content_items(entry, item_type):
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return []
    return [item for item in content if isinstance(item, dict) and item.get("type") == item_type]


def final_text(turn):
    for entry in reversed(turn):
        texts = content_items(entry, "text") if entry["type"] == "assistant" else []
        if texts:
            return texts[-1].get("text", "").strip()
    return ""


def final_reply(payload, max_wait_seconds=1.5):
    """Claude's final message of the turn.

    The Stop hook can fire just before that message reaches the transcript, so re-read briefly until the turn
    ends with assistant text rather than a tool result.

    :param payload: Stop hook payload
    :param max_wait_seconds: How long to wait for the transcript to catch up
    """
    text = payload.get("last_assistant_message")
    if isinstance(text, str) and text.strip():
        return text.strip()

    deadline = time.monotonic() + max_wait_seconds
    while True:
        turn = read_last_turn(payload.get("transcript_path", ""))
        ends_with_text = bool(turn) and turn[-1]["type"] == "assistant" and content_items(turn[-1], "text")
        if ends_with_text or time.monotonic() > deadline:
            return final_text(turn)
        time.sleep(0.1)


def _parse_time(value):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def classify_turn(transcript_path, config):
    """Phrase category for the finished turn: question, build, edits, research, long or quick (first match wins).

    :param transcript_path: Path from the hook payload
    :param config: Settings; uses the `task_done` thresholds
    """
    turn = read_last_turn(transcript_path)
    if not turn:
        return "quick"

    settings = config["task_done"]
    tool_uses = [tool for entry in turn if entry["type"] == "assistant" for tool in content_items(entry, "tool_use")]
    names = [tool.get("name") for tool in tool_uses]
    keywords = [keyword.lower() for keyword in settings["build_command_keywords"]]
    ran_build = any(tool.get("name") in SHELL_TOOLS
                    and any(keyword in str((tool.get("input") or {}).get("command", "")).lower() for keyword in keywords)
                    for tool in tool_uses)
    start, end = _parse_time(turn[0].get("timestamp")), _parse_time(turn[-1].get("timestamp"))
    duration = (end - start).total_seconds() if start and end else 0

    if final_text(turn).endswith("?"):
        return "question"
    if ran_build:
        return "build"
    if any(name in EDIT_TOOLS for name in names):
        return "edits"
    if sum(name in RESEARCH_TOOLS for name in names) >= settings["research_tool_threshold"]:
        return "research"
    if duration >= settings["long_task_seconds"]:
        return "long"
    return "quick"
