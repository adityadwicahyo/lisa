"""How the hook and the listener make Lisa speak. Standard library only (used by the hook).

Messages to the speech server (see server.py): {"text", "sent_at", ["kind", "max_delay"]}, {"cancel": "response"},
{"shutdown": true}.
"""

import json
import time

from lisa.system import send_message, spawn


def speak(text, config, **extra):
    """Say `text` live, starting the speech server (with this sentence) if it isn't running.

    :param text: One or more sentences
    :param config: Settings
    :param extra: Extra message fields, e.g. `kind="response", max_delay=60`
    """
    message = {"text": text, "sent_at": time.time(), **extra}
    if not send_message(config["server"]["port"], message):
        spawn("lisa.speech.server", json.dumps(message))


def cancel_reply(config):
    """Drop reply sentences not spoken yet (a new prompt was sent). Never starts the server.

    :param config: Settings
    """
    send_message(config["server"]["port"], {"cancel": "response", "sent_at": time.time()})


def stop_server(config):
    send_message(config["server"]["port"], {"shutdown": True})


def play_clip(clip):
    """Play a clip in a detached process, queued behind any other Lisa audio.

    :param clip: WAV file path
    """
    spawn("lisa.speech.player", clip)
