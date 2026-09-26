"""Plays one WAV clip, waiting for any other Lisa audio to finish first so voices never overlap.

All of Lisa's sound (clips, live speech) goes through `playback_lock`, a byte lock on .lisa/playback.lock.
Run as `python -m lisa.speech.player <file.wav>`; the hook starts it detached.
"""

import msvcrt
import sys
import time
import winsound
from contextlib import contextmanager

from lisa.paths import PLAYBACK_LOCK


@contextmanager
def playback_lock(max_wait_seconds=10):
    """Yield True once this process owns the speaker, or False if waiting took too long.

    :param max_wait_seconds: How long a clip may wait before it is too stale to play
    """
    PLAYBACK_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(PLAYBACK_LOCK, "a+b") as lock:
        deadline = time.monotonic() + max_wait_seconds
        while True:
            try:
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() > deadline:
                    yield False
                    return
                time.sleep(0.05)
        try:
            yield True
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def is_playing():
    """True while another Lisa process holds the speaker."""
    try:
        PLAYBACK_LOCK.parent.mkdir(parents=True, exist_ok=True)
        with open(PLAYBACK_LOCK, "a+b") as lock:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        return False
    except OSError:
        return True


def main():
    with playback_lock() as acquired:
        if acquired:  # Otherwise it is too stale to be useful; skip it.
            winsound.PlaySound(sys.argv[1], winsound.SND_FILENAME | winsound.SND_NODEFAULT)


if __name__ == "__main__":
    main()
