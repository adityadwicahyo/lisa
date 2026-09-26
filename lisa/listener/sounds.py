"""Short chimes and spoken clips the listener plays itself (synchronously, so it knows when she stopped talking)."""

import io
import math
import wave
import winsound

from lisa.speech.clips import random_clip

SAMPLE_RATE = 16000


def tone(frequencies, seconds=0.12, volume=0.5):
    """A chime (one tone per frequency, in sequence) as in-memory WAV bytes.

    :param frequencies: Tones in Hz
    :param seconds: Length of each tone
    :param volume: 0-1
    """
    frames = bytearray()
    for frequency in frequencies:
        count = int(SAMPLE_RATE * seconds)
        for i in range(count):
            fade = min(1.0, i / 200, (count - i) / 200)
            sample = int(32767 * volume * fade * math.sin(2 * math.pi * frequency * i / SAMPLE_RATE))
            frames += sample.to_bytes(2, "little", signed=True)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(bytes(frames))
    return buffer.getvalue()


LISTENING = tone([660, 880])  # rising
DONE = tone([880, 1175])  # higher rising
CANCELLED = tone([440, 330])  # falling


def play(chime):
    winsound.PlaySound(chime, winsound.SND_MEMORY | winsound.SND_NODEFAULT)


def say(category, fallback):
    """Play a random clip of a phrase category and wait until it ends; the chime if none was generated.

    :param category: Phrase category, e.g. "confirm"
    :param fallback: Chime to play instead
    """
    clip = random_clip(category)
    if clip:
        winsound.PlaySound(str(clip), winsound.SND_FILENAME | winsound.SND_NODEFAULT)
    else:
        play(fallback)
