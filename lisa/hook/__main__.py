"""Hook entry point: reads the event from stdin and decides what Lisa says. Always exits 0."""

import json
import sys
import time

from lisa.config import load_config
from lisa.hook import loading_words
from lisa.hook.transcript import classify_turn, final_reply
from lisa.log import log
from lisa.paths import LAST_TOOL_SPOKEN_FILE
from lisa.speech import client
from lisa.speech.clips import loading_word_clip, random_clip
from lisa.state import load_state
from lisa.system import is_running, spawn
from lisa.text.describe import describe_action
from lisa.text.summarize import summarize_reply


def clip_category(payload, config):
    """Which pre-recorded phrase fits this event, if any.

    :param payload: Hook payload
    :param config: Settings
    """
    events = config["events"]
    event = payload.get("hook_event_name")
    if event == "SessionStart":
        if events["session_start"] and payload.get("source") in ("startup", "resume"):
            return "greeting"
    elif event == "UserPromptSubmit":
        if events["prompt_submit"]:
            return "acknowledge"
    elif event == "Notification":
        # Idle reminders arrive after the Stop line already spoke, so only permission requests are voiced.
        if events["permission"] and "permission" in payload.get("message", "").lower():
            return "permission"
    elif event == "Stop":
        if events["stop"] and not payload.get("stop_hook_active"):
            return classify_turn(payload.get("transcript_path", ""), config)
    return None


def reads_replies(config):
    return config["reply"]["read"] in ("paragraph", "sentences")


def speak_reply(payload, config):
    """Read the start of Claude's final message aloud. False when there is nothing to say.

    :param payload: Stop hook payload
    :param config: Settings
    """
    reply = config["reply"]
    summary = summarize_reply(final_reply(payload), mode=reply["read"], max_sentences=reply["max_sentences"],
                              max_words=reply["max_words"])
    if not summary:
        return False
    client.speak(summary, config, kind="response", max_delay=reply["max_delay_seconds"])
    return True


def speak_tool_use(payload, config):
    """Say what Claude is doing ("Reading Login View Model"), at most once per `tool_use.min_gap_seconds`.

    :param payload: PreToolUse hook payload
    :param config: Settings
    """
    try:
        last = float(LAST_TOOL_SPOKEN_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        last = 0.0
    if time.time() - last < config["tool_use"]["min_gap_seconds"]:
        return
    sentence = describe_action(payload.get("tool_name", ""), payload.get("tool_input"))
    if sentence:
        client.speak(sentence, config)
        LAST_TOOL_SPOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_TOOL_SPOKEN_FILE.write_text(str(time.time()), encoding="utf-8")


def handle(payload, config, state):
    """Run each reaction independently, so one failing part doesn't silence the others.

    :param payload: Hook payload
    :param config: Settings
    :param state: On/off switches
    """
    events = config["events"]
    event = payload.get("hook_event_name")

    def attempt(action, *args):
        try:
            action(*args)
        except Exception as error:
            log("hook", f"{event}: {error!r}")

    def speak_or_play():
        if event == "UserPromptSubmit" and reads_replies(config):
            client.cancel_reply(config)  # Stop reading the previous reply (the current sentence still finishes).
        if event == "UserPromptSubmit" and events["loading_word"] and loading_words.next_word():
            clip = loading_word_clip(loading_words.next_word())
            if clip.exists():
                client.play_clip(clip)
                return
        category = clip_category(payload, config)
        # The reply summary replaces the end-of-task phrase, which stays as the fallback for replies with no prose.
        if category and event == "Stop" and reads_replies(config) and speak_reply(payload, config):
            return
        clip = random_clip(category) if category else None
        if clip:
            client.play_clip(clip)

    attempt(speak_or_play)

    if event == "PreToolUse" and events["tool_use"]:
        attempt(speak_tool_use, payload, config)

    if event == "SessionStart":
        if events["tool_use"] or reads_replies(config):
            attempt(spawn, "lisa.speech.server")  # Load the voice early; exits at once if already running.
        if state["listening"] and not is_running(config["listener"]["port"]):
            attempt(spawn, "lisa.listener")

    if events["loading_word"] and event in ("SessionStart", "Stop"):
        attempt(loading_words.queue_next_word, config)


def main():
    try:
        state = load_state()
        if state["enabled"]:  # Turned off with `lisa off`: do nothing at all.
            payload = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
            handle(payload, load_config(), state)
    except Exception as error:
        log("hook", repr(error))
    sys.exit(0)


if __name__ == "__main__":
    main()
