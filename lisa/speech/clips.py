"""Pre-recorded clips in audio/<category>/, generated from phrases.json and loading_words.json by `lisa generate`.

Standard library only (used by the hook).
"""

import random
import re

from lisa.paths import AUDIO_DIR, LAST_CLIP_FILE

LOADING_WORDS_CATEGORY = "loading_words"


def loading_word_clip(word):
    """Clip path for a loading word; the name must match between generation and playback.

    :param word: Loading word, e.g. "Zigzagging"
    """
    return AUDIO_DIR / LOADING_WORDS_CATEGORY / (re.sub(r"[^A-Za-z0-9-]", "_", word) + ".wav")


def random_clip(category):
    """A random clip of the category, avoiding the one played last, or None if none was generated.

    :param category: Phrase category from phrases.json, e.g. "greeting"
    """
    clips = sorted((AUDIO_DIR / category).glob("*.wav"))
    if not clips:
        return None
    try:
        last = LAST_CLIP_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        last = ""
    clip = random.choice([clip for clip in clips if str(clip) != last] or clips)
    try:
        LAST_CLIP_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_CLIP_FILE.write_text(str(clip), encoding="utf-8")
    except OSError:
        pass
    return clip
