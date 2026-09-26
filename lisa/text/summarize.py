"""Turn Claude's final Markdown reply into a short spoken summary: its first paragraph or sentences as plain text.

Standard library only, because it runs inside the Stop hook.
"""

import re
from urllib.parse import urlparse

from lisa.text.describe import file_name

SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[\"'(\[]?[A-Z0-9])")


def split_sentences(text):
    return [s.strip() for s in SENTENCE_END.split(text) if s.strip()]


def speak_code(match):
    """Inline code: file paths become their file name, short snippets are kept, anything longer becomes "that"."""
    code = match.group(1).strip()
    if re.search(r"[\\/]", code) or re.fullmatch(r"[\w\-]+\.\w{1,10}(:\d+)?", code):
        return file_name(re.sub(r":\d+$", "", code))
    if re.fullmatch(r"[\w.\- ]{1,40}", code) and len(code.split()) <= 4:
        return code
    return "that"


def plain_text(line):
    line = re.sub(r"</?[a-zA-Z][^>]*>", "", line)  # HTML-like tags
    line = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", line)  # images
    line = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line)  # links keep their text
    line = re.sub(r"https?://\S+", lambda m: urlparse(m.group(0)).netloc.removeprefix("www."), line)
    line = re.sub(r"`([^`]*)`", speak_code, line)
    line = re.sub(r"(\*\*|__|~~)(.+?)\1", r"\2", line)
    line = re.sub(r"(?<!\w)[*_](\S.*?)[*_](?!\w)", r"\1", line)
    line = re.sub(r"\b[\w\-]+\.\w{1,10}:\d+\b", lambda m: file_name(m.group(0).rsplit(":", 1)[0]), line)
    line = re.sub(r"\s*(→|->|=>)\s*", ", then ", line)
    line = re.sub(r"\s+", " ", line).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", line)


def reply_lines(markdown):
    """Yield the reply's prose lines as plain text, skipping code blocks, tables, headings and rules.

    Yields (text, continues_previous_line), or None for a paragraph break.
    A list is a paragraph of its own, even without a blank line before it.
    """
    in_code = in_list = False
    for raw in markdown.splitlines():
        stripped = raw.strip()
        if stripped.startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code or not stripped or stripped.startswith(("|", "#", ">")) or re.fullmatch(r"[-*_=]{3,}", stripped):
            in_list = False
            yield None
            continue
        item = re.sub(r"^([-*+]|\d+[.)])\s+", "", stripped)
        is_item = item != stripped
        continues_item = in_list and not is_item and raw[:1] in " \t"  # An indented line inside a list item.
        if is_item != in_list and not continues_item:
            in_list = is_item
            yield None
        text = plain_text(item)
        if text:
            # Also a wrapped sentence: a non-item line starting in lowercase.
            yield text, continues_item or (not is_item and text[0].islower())


def paragraphs_of(markdown):
    paragraphs, lines = [], []

    def end_paragraph():
        if lines:
            # Lines without end punctuation (list items, labels) become sentences of their own.
            paragraphs.append(" ".join(line if line[-1] in ".!?:" else line + "." for line in lines))
            lines.clear()

    for line in reply_lines(markdown or ""):
        if line is None:
            end_paragraph()
        elif line[1] and lines:
            lines[-1] += " " + line[0]
        else:
            lines.append(line[0])
    end_paragraph()
    return paragraphs


def summarize_reply(markdown, mode="paragraph", max_sentences=2, max_words=80):
    """Return the part of the reply to speak, or None when there is nothing to say.

    mode "paragraph": the first paragraph; "sentences": the first `max_sentences` sentences.
    Both stop at a sentence boundary before `max_words` (only a first sentence longer than that is cut).
    """
    paragraphs = paragraphs_of(markdown or "")
    if mode == "paragraph":
        paragraphs, max_sentences = paragraphs[:1], float("inf")

    sentences, words = [], 0
    for sentence in (s for paragraph in paragraphs for s in split_sentences(paragraph)):
        count = len(sentence.split())
        if sentences and (len(sentences) >= max_sentences or words + count > max_words):
            break
        if not sentences and count > max_words:
            sentence = " ".join(sentence.split()[:max_words])
        if sentence.endswith(":"):
            sentence = sentence[:-1] + "."
        sentences.append(sentence)
        words += count
    return " ".join(sentences) or None
