"""The `lisa` command (lisa.cmd in a terminal, /lisa in Claude Code).

    lisa status              what is on and running
    lisa on | off            Lisa as a whole (off frees her memory, CPU and the microphone)
    lisa mic on | mic off    only the microphone listener
    lisa enroll              teach Lisa your voice, so she ignores other people (in a terminal)
    lisa enroll add          add a voiceprint, e.g. with a headset
    lisa enroll short        add a voiceprint of short answers ("yes", "no")
    lisa generate [category] re-render her voice clips after changing the voice or phrases
    lisa voices              hear every voice of the configured engine
    lisa install | uninstall connect Lisa to Claude Code and Windows, or undo it
"""

import sys
import time

from lisa.config import load_config
from lisa.hook import loading_words
from lisa.paths import NEXT_LOADING_WORD_FILE, VOICEPRINT_FILE
from lisa.speech import client
from lisa.state import load_state, save_state
from lisa.system import claude_code_running, is_running, on_ac_power, send_message, spawn


def start_listener(config):
    # Without Claude Code it would exit at once; the next Claude Code session starts it instead.
    if claude_code_running(config) and not is_running(config["listener"]["port"]):
        spawn("lisa.listener")


def stop_listener(config):
    send_message(config["listener"]["port"], {"shutdown": True})


def turn_off(config):
    """`lisa off`, also said as "Lisa, off": everything stops, and Claude Code gets its own loading words back.

    :param config: Settings
    """
    save_state(enabled=False)
    stop_listener(config)
    client.stop_server(config)
    if NEXT_LOADING_WORD_FILE.exists():  # Only undo what Lisa set, never your own spinner settings.
        try:
            loading_words.restore(config)
        except Exception as error:
            print(f"Could not restore Claude Code's loading words: {error}")


def turn_mic_off(config):
    """`lisa mic off`, also said as "Lisa, stop listening".

    :param config: Settings
    """
    save_state(listening=False)
    stop_listener(config)


def status_text(config):
    state = load_state()
    lines = [f"Lisa:            {'on' if state['enabled'] else 'off'}",
             f"Microphone:      {'on' if state['listening'] else 'off'}"]
    if state["enabled"]:
        server = "running" if is_running(config["server"]["port"]) else "not running (starts when needed)"
        lines.append(f"Speech server:   {server}")
    if state["enabled"] and state["listening"]:
        if not is_running(config["listener"]["port"]):
            listener = "not running" if claude_code_running(config) else "waiting for Claude Code to open"
        elif not (on_ac_power() or config["listener"]["enabled_on_battery"]):
            listener = "paused (on battery, microphone released)"
        else:
            listener = f"listening for sentences starting with \"{config['wake']['name'].capitalize()}\""
        lines.append(f"Listener:        {listener}")
        if not config["voice_check"]["enabled"]:
            voice = "off"
        elif VOICEPRINT_FILE.exists():
            voice = "on, only your voice is accepted"
        else:
            voice = "not set up, anyone's voice is accepted (run `lisa enroll`)"
        lines.append(f"Voice check:     {voice}")
    return "\n".join(lines)


def restart_listener_after(config, action):
    """Run an interactive recording with the listener paused, so it doesn't react to what you record."""
    stop_listener(config)
    try:
        return action()
    finally:
        state = load_state()
        if state["enabled"] and state["listening"]:
            start_listener(config)


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    config = load_config()
    command = " ".join(args).lower().strip()

    if command in ("", "status"):
        pass
    elif command == "on":
        if save_state(enabled=True)["listening"]:
            start_listener(config)
        time.sleep(1)  # Let the listener bind its port, so the status below is accurate.
    elif command == "off":
        turn_off(config)
    elif command == "mic on":
        if save_state(listening=True)["enabled"]:
            start_listener(config)
        time.sleep(1)
    elif command == "mic off":
        turn_mic_off(config)
    elif command in ("enroll", "enroll add", "enroll short"):
        from lisa.listener import voiceprint

        if command == "enroll short":
            code = restart_listener_after(config, lambda: voiceprint.enroll_short(config))
        else:
            code = restart_listener_after(config, lambda: voiceprint.enroll(config, add=command == "enroll add"))
        if code:
            return code
    elif args[0].lower() == "generate":
        from lisa.speech.generate import generate

        generate(config, categories=args[1:] or None)
        return 0
    elif command == "voices":
        from lisa.speech.generate import preview

        preview(config)
        return 0
    elif command in ("install", "uninstall"):
        from lisa import install

        return install.install(config) if command == "install" else install.uninstall(config)
    else:
        print(__doc__.strip())
        return 1

    print(status_text(config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
