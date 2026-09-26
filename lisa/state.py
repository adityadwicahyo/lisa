"""Lisa's on/off switches, kept in .lisa/state.json so they survive restarts.

    enabled    Lisa as a whole: hooks, speech server and listener
    listening  the microphone listener only
"""

import json
import os

from lisa.paths import STATE_FILE

DEFAULT_STATE = {"enabled": True, "listening": True}


def load_state():
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        state = {}
    return {**DEFAULT_STATE, **state}


def save_state(**changes):
    """Update and return the state; written atomically because the hook may read it at the same moment.

    :param changes: Switches to set, e.g. `enabled=False`
    """
    state = {**load_state(), **changes}
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_path = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
    temp_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_path, STATE_FILE)
    return state
