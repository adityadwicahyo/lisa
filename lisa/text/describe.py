"""Turn a Claude Code tool call into a short spoken sentence, e.g. "Reading Login View Model".

Standard library only, because it runs inside the hook on every tool call.
"""

import re
from pathlib import PurePath
from urllib.parse import urlparse

MAX_WORDS = 14

# Imperative verbs Claude typically starts a shell command description with ("Run unit tests").
VERBS = set("""
add analyze append apply build bump calculate call capture change check clean clear clone close commit compare
compile configure confirm connect convert copy count create debug delete deploy describe detect diff disable
display download edit enable ensure execute export extract fetch filter find fix format generate get grep
import inspect install kill launch lint list load locate look make measure merge migrate move open parse patch
ping play prepare print profile pull push query read rebase rebuild record refresh regenerate reinstall reload
remove rename render replace reproduce reset restart restore retry reveal review revert run save scan search
send set show sort start stash stop sync tail test trace try uninstall unzip update upgrade upload validate
verify view wait watch write zip
""".split())

DOUBLED_GERUNDS = {"run": "running", "get": "getting", "set": "setting", "stop": "stopping", "commit": "committing",
                   "debug": "debugging", "zip": "zipping", "unzip": "unzipping", "grep": "grepping"}

FILE_TYPES = {"kt": "Kotlin", "kts": "Gradle", "gradle": "Gradle", "java": "Java", "xml": "XML", "json": "JSON",
              "md": "Markdown", "py": "Python", "js": "JavaScript", "ts": "TypeScript", "yml": "YAML",
              "yaml": "YAML", "toml": "TOML", "properties": "properties", "pro": "ProGuard"}

CODE_EXTENSIONS = set(FILE_TYPES) | {"txt", "log", "html", "css", "sh", "ps1", "bat", "cfg", "ini", "csv"}


def gerund(verb):
    verb = verb.lower()
    if verb in DOUBLED_GERUNDS:
        result = DOUBLED_GERUNDS[verb]
    elif verb.endswith("ie"):
        result = verb[:-2] + "ying"
    elif verb.endswith("e") and not verb.endswith(("ee", "ye", "oe")):
        result = verb[:-1] + "ing"
    else:
        result = verb + "ing"
    return result.capitalize()


def to_progressive(sentence):
    """'Run unit tests' -> 'Running unit tests'. Sentences not starting with a known verb are kept as-is."""
    first, _, rest = sentence.strip().partition(" ")
    if first.lower() in VERBS:
        return f"{gerund(first)} {rest}".strip()
    return sentence.strip()


def speakable(text):
    """'LoginViewModel' -> 'Login View Model', 'card_read-log' -> 'card read log'."""
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    return re.sub(r"[_\-]+", " ", text).strip()


def file_name(path):
    name = PurePath(str(path).replace("\\", "/")).name
    parts = name.split(".")
    if len(parts) > 1 and parts[-1].lower() in CODE_EXTENSIONS:
        parts = parts[:-1]
    return speakable(" ".join(p for p in parts if p))


def limit_words(sentence):
    words = sentence.rstrip(" .").split()
    return " ".join(words[:MAX_WORDS]) if words else None


def describe_shell(tool_input):
    description = (tool_input.get("description") or "").strip()
    if description:
        return to_progressive(description)
    command = str(tool_input.get("command", ""))
    if "gradle" in command:
        tasks = [t.lstrip(":") for t in command.split() if re.fullmatch(r":?[\w:]+", t) and "gradle" not in t]
        return "Running Gradle " + " ".join(speakable(t.split(":")[-1]) for t in tasks[:3]) if tasks else "Running Gradle"
    return "Running a command"


def describe_search(tool_input):
    pattern = str(tool_input.get("pattern", ""))
    where = f" in {file_name(tool_input['path'])}" if tool_input.get("path") else ""
    if re.fullmatch(r"[\w .\-]{1,40}", pattern):
        return f"Searching for {speakable(pattern)}{where}"
    return f"Searching the code{where}"


def describe_glob(tool_input):
    match = re.search(r"\*\.(\w+)$", str(tool_input.get("pattern", "")))
    kind = FILE_TYPES.get(match.group(1).lower()) if match else None
    return f"Looking for {kind} files" if kind else "Looking for files"


def describe_agent(tool_input):
    description = (tool_input.get("description") or "").strip()
    if not description:
        return "Asking a helper agent"
    return f"Asking a helper agent to {description[0].lower()}{description[1:]}"


def describe_action(tool_name, tool_input):
    """Return a short sentence for the tool call, or None when it is not worth saying."""
    tool_input = tool_input or {}
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path")

    if tool_name in ("Bash", "PowerShell"):
        sentence = describe_shell(tool_input)
    elif tool_name == "Read":
        sentence = f"Reading {file_name(path)}" if path else "Reading a file"
    elif tool_name in ("Edit", "MultiEdit", "NotebookEdit"):
        sentence = f"Editing {file_name(path)}" if path else "Editing a file"
    elif tool_name == "Write":
        sentence = f"Writing {file_name(path)}" if path else "Writing a file"
    elif tool_name == "Grep":
        sentence = describe_search(tool_input)
    elif tool_name == "Glob":
        sentence = describe_glob(tool_input)
    elif tool_name == "LS":
        sentence = f"Listing {file_name(path)}" if path else "Listing files"
    elif tool_name == "WebFetch":
        domain = urlparse(str(tool_input.get("url", ""))).netloc.removeprefix("www.")
        sentence = f"Reading a web page from {domain}" if domain else "Reading a web page"
    elif tool_name == "WebSearch":
        sentence = f"Searching the web for {tool_input.get('query', '')}"
    elif tool_name in ("Task", "Agent"):
        sentence = describe_agent(tool_input)
    elif tool_name == "Skill":
        sentence = f"Using the {speakable(str(tool_input.get('skill', '')))} skill"
    elif tool_name in ("TodoWrite", "AskUserQuestion", "ToolSearch"):
        return None  # Bookkeeping, or already announced by the permission/question lines.
    elif tool_name.startswith("mcp__"):
        _, server, tool = (tool_name.split("__", 2) + ["", ""])[:3]
        sentence = f"Using {speakable(tool)} from {speakable(server)}"
    else:
        sentence = f"Using {speakable(tool_name)}"

    return limit_words(sentence)
