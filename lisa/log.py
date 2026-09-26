"""One log file per process under .lisa/logs/ (hook.log, server.log, listener.log)."""

from datetime import datetime

from lisa.paths import LOG_DIR


def log(name, message):
    """Append a timestamped line. Never raises: logging must not break Claude Code or Lisa.

    :param name: Log file name without extension
    :param message: Text to append
    """
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / f"{name}.log", "a", encoding="utf-8") as file:
            file.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {message}\n")
    except OSError:
        pass
