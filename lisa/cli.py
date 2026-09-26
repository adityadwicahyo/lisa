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
    lisa version             which version of Lisa this is
"""

import os
import sys
import time

from lisa import __version__
from lisa.config import load_config
from lisa.hook import loading_words
from lisa.paths import NEXT_LOADING_WORD_FILE, VOICEPRINT_FILE
from lisa.speech import client
from lisa.state import load_state, save_state
from lisa.system import (claude_code_running, is_running, lisa_processes, memory_in_use, on_ac_power, port_owner,
                         processes, send_message, spawn)


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


def speaking_status(config, state):
    """(is on, what it means) for Lisa's voice."""
    if not state["enabled"]:
        return False, "Turn on with `lisa on`"
    parts = []
    if config["events"]["stop"] and config["reply"]["read"] != "off":
        parts.append("reads Claude's replies")
    if config["events"]["tool_use"]:
        parts.append("says what Claude is doing")
    text = " and ".join(parts)
    return True, text[:1].upper() + text[1:] if text else "Short alerts only"


def microphone_status(config, state):
    """(is listening, why or why not). Reflects what really happens, not just the switch: it only listens while
    Lisa is on, Claude Code is open and (by default) the laptop is plugged in."""
    if not state["listening"]:
        return False, "Turn on with `lisa mic on`"
    if not state["enabled"]:
        return False, "Comes back on with `lisa on`"
    if not is_running(config["listener"]["port"]):
        if not claude_code_running(config):
            return False, "Starts when Claude Code opens"
        return False, "Not running; start it with `lisa mic on`"
    if not (on_ac_power() or config["listener"]["enabled_on_battery"]):
        return False, "Paused on battery; listens again when plugged in"
    return True, f"Say \"{config['wake']['name'].capitalize()}, ...\""


def voice_check_status(config):
    """(is on, what it means) for the only-your-voice check."""
    if not config["voice_check"]["enabled"]:
        return False, "Anyone's voice is accepted"
    if VOICEPRINT_FILE.exists():
        return True, "Only your voice is accepted"
    return False, "Anyone's voice is accepted; set it up with `lisa enroll`"


def memory_by_part(config):
    """Bytes of RAM in use by (speech server, listener, any other Lisa process), each with its launcher.

    "Other" catches everything else started from Lisa's folder (a clip playing, a hook running, a process that
    failed to exit), so the total is the real footprint rather than just the two known processes.

    :param config: Settings; uses the server and listener ports
    """
    table = processes()
    lisa = lisa_processes(exclude={os.getpid(), os.getppid()})  # Not this `lisa status` command itself.

    def with_launcher(pid):
        return {pid, table[pid][0]} & lisa if pid in lisa else set()

    speaking = with_launcher(port_owner(config["server"]["port"]))
    microphone = with_launcher(port_owner(config["listener"]["port"]))
    other = lisa - speaking - microphone
    return tuple(sum(memory_in_use(pid) for pid in part) for part in (speaking, microphone, other))


def megabytes(size):
    return f"{size / 2 ** 20:,.0f} MB"


def status_text(config):
    state = load_state()
    speaking_memory, microphone_memory, other_memory = memory_by_part(config)
    rows = [("Speaking", *speaking_status(config, state), megabytes(speaking_memory)),
            ("Microphone", *microphone_status(config, state), megabytes(microphone_memory)),
            ("Voice check", *voice_check_status(config), "-")]  # Runs inside the microphone listener.
    lines = [f"  {name:<12} {'ON ' if on else 'OFF'}  {info}" for name, on, info, _ in rows]
    if other_memory:
        lines.append("  Other             Clips playing, a hook running or a process starting")
        rows.append(("", False, "", megabytes(other_memory)))
    width = max(map(len, lines)) + 3
    lines = [line.ljust(width) + memory.rjust(9) for line, (*_, memory) in zip(lines, rows)]
    total = megabytes(speaking_memory + microphone_memory + other_memory)
    header = f"Lisa {__version__} is {'ON' if state['enabled'] else 'OFF'}".ljust(width) + "Memory".rjust(9)
    return "\n".join([header, "", *lines, "", "Total".rjust(width - 1) + " " + total.rjust(9)])


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
    elif command == "version":
        print(f"Lisa {__version__}")
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
