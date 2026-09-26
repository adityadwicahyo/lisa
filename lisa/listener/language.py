"""Rules for what you said: addressed to Lisa? a command? a cancel? a yes or a no? Pure functions of text and settings."""

import re
from difflib import SequenceMatcher

# Trailing words ignored when matching a whole phrase ("Never mind then, sorry." / "Turn off now, please.").
CANCEL_FILLERS = {"then", "sorry", "please", "lisa", "thanks", "thank", "you", "actually", "oh", "ah", "uh"}
COMMAND_FILLERS = {"please", "now", "thanks", "thank", "you", "lisa"}

# What speech-to-text typically "hears" in noise or a lone breath.
STRAY_TEXTS = {"you", "thank you", "thanks", "thanks for watching", "thank you for watching", "bye", "okay", "so"}


def words_of(text):
    return re.findall(r"[a-z']+", text.lower())


def _without_trailing(words, fillers):
    words = list(words)
    while words and words[-1] in fillers:
        words.pop()
    return " ".join(words)


def match_wake(text, config):
    """The prompt after "Lisa", "" when only the name was said, or None when the sentence isn't addressed to Lisa.

    The name counts only at the start (after optional "hey"/"okay"), and near-misses such as "Liza" match too.

    :param text: Transcribed sentence
    :param config: Settings; uses `wake`
    """
    wake = config["wake"]
    prefixes = "|".join(map(re.escape, wake["prefix_words"]))
    match = re.match(rf"^\W*(?:(?:{prefixes})\b\W*)*([a-z']+)\b\W*", text, re.IGNORECASE)
    if not match:
        return None
    spoken = match.group(1).lower()
    if not any(SequenceMatcher(None, spoken, alias).ratio() >= 0.8 for alias in wake["aliases"]):
        return None
    return text[match.end():].strip()


def voice_command(prompt, config):
    """"off", "mic off", or None. Only the whole prompt counts, so "turn off the debug logging" is a normal prompt.

    :param prompt: Text after "Lisa"
    :param config: Settings; uses `commands`
    """
    spoken = _without_trailing(words_of(prompt), COMMAND_FILLERS)
    if spoken in config["commands"]["off_phrases"]:
        return "off"
    if spoken in config["commands"]["mic_off_phrases"]:
        return "mic off"
    return None


def is_cancel(prompt, config):
    """True when the prompt calls itself off: "never mind", "cancel", or "…, actually forget it" at the end.

    At the end of a longer prompt only unmistakable phrases count, so "add a button to cancel" is still a prompt.

    :param prompt: Text after "Lisa"
    :param config: Settings; uses `commands`
    """
    spoken = _without_trailing(words_of(prompt.lower().replace("nevermind", "never mind")), CANCEL_FILLERS)
    commands = config["commands"]
    if spoken in commands["cancel_phrases"]:
        return True
    return any(spoken.endswith(" " + phrase) for phrase in commands["cancel_phrases_at_end"])


def classify_answer(text, config):
    """"send", "cancel", "keep", or None for an answer to "Shall I send it?" that is none of these, or too long.

    Keep wins over cancel ("no, I'll edit it" leaves the text), and cancel over send ("no, don't send it").

    :param text: Transcribed answer
    :param config: Settings; uses `confirm`
    """
    words = words_of(text.lower().replace("nevermind", "never mind"))
    if not words or len(words) > config["confirm"]["max_words"]:
        return None
    spoken = f" {' '.join(words)} "
    if any(f" {word} " in spoken for word in config["confirm"]["keep_words"]):
        return "keep"
    if any(f" {word} " in spoken for word in config["confirm"]["cancel_words"]):
        return "cancel"
    if any(f" {word} " in spoken for word in config["confirm"]["send_words"]):
        return "send"
    return None


def is_stray(prompt, config):
    """True for text that isn't a real prompt: the name again, or a typical speech-to-text noise guess.

    :param prompt: Text after "Lisa"
    :param config: Settings; uses `wake`
    """
    spoken = " ".join(words_of(prompt))
    return (not spoken or spoken in STRAY_TEXTS
            or SequenceMatcher(None, spoken, config["wake"]["name"]).ratio() >= 0.6)
