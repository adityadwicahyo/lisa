import pytest

from lisa.text.describe import describe_action
from lisa.text.summarize import split_sentences, summarize_reply


@pytest.mark.parametrize("tool, tool_input, sentence", [
    ("Read", {"file_path": "C:/app/LoginViewModel.kt"}, "Reading Login View Model"),
    ("Bash", {"command": "gradlew test", "description": "Run unit tests"}, "Running unit tests"),
    ("Grep", {"pattern": "cardRead"}, "Searching for card Read"),
    ("Glob", {"pattern": "**/*.kt"}, "Looking for Kotlin files"),
    ("WebFetch", {"url": "https://www.example.com/docs"}, "Reading a web page from example.com"),
    ("TodoWrite", {}, None),
])
def test_describe_action(tool, tool_input, sentence):
    assert describe_action(tool, tool_input) == sentence


def test_summary_reads_first_paragraph_without_markdown():
    reply = ("Fixed. The bug was in `D:\\app\\play.py:42` where **the lock** wasn't released.\n\n"
             "```python\nx = 1\n```\n\nSecond paragraph.")
    assert summarize_reply(reply) == "Fixed. The bug was in play where the lock wasn't released."


def test_summary_sentences_mode_crosses_paragraphs():
    assert summarize_reply("One.\n\nTwo. Three.", mode="sentences", max_sentences=2) == "One. Two."


def test_summary_list_is_its_own_paragraph():
    assert summarize_reply("Lisa now does three things:\n- Reads replies\n- Cancels speech") == \
        "Lisa now does three things."


def test_summary_joins_wrapped_lines():
    assert summarize_reply("- Added `summarize.py`\n  which strips Markdown\n- Updated README") == \
        "Added summarize which strips Markdown. Updated README."


def test_summary_stops_at_sentence_boundary_before_word_limit():
    reply = " ".join(f"Sentence number {i} has a few words in it." for i in range(20))
    assert summarize_reply(reply, max_words=80).count("Sentence") == 8


def test_summary_of_code_only_reply_is_empty():
    assert summarize_reply("```\ncode only\n```") is None


def test_split_sentences_keeps_abbreviations():
    assert split_sentences("Done, e.g. version 1.5 works. Next one.") == ["Done, e.g. version 1.5 works.", "Next one."]
