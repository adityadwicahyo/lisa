"""Listener entry point, started detached by the hook or the `lisa` command."""

import os
import traceback

from lisa.config import load_config
from lisa.listener.listener import Listener, log
from lisa.system import is_port_in_use


def main():
    try:
        listener = Listener(load_config())
        if listener.should_run():
            listener.run()
    except OSError as error:
        if not is_port_in_use(error):  # In use: a listener is already running, which is fine.
            log(f"Listener failed: {error!r}\n{traceback.format_exc()}")
    except Exception:
        log(f"Listener crashed:\n{traceback.format_exc()}")
    finally:
        os._exit(0)  # Don't wait for the audio and model threads.


if __name__ == "__main__":
    main()
