"""Renders phrases.json and loading_words.json into audio/ (`lisa generate`), and previews voices (`lisa voices`).

Clips are pre-recorded so the hook can play them instantly; rerun after changing the voice, address or phrases.
"""

import json
import shutil
import winsound

from lisa.paths import AUDIO_DIR, LOADING_WORDS_FILE, PHRASES_FILE, ROOT
from lisa.speech.clips import LOADING_WORDS_CATEGORY, loading_word_clip
from lisa.speech.engines import create_engine, wav_bytes

STAGING_DIR = ROOT / "audio_staging"


def format_line(template, address):
    """Fill in the form of address and capitalize, e.g. "{address}, I need…" -> "Sir, I need…".

    :param template: Phrase with an optional `{address}`
    :param address: How Lisa addresses you, e.g. "sir"
    """
    line = template.format(address=address)
    return line[0].upper() + line[1:]


def render(engine, voice, text, path):
    """Synthesize `text` into a WAV file.

    :param engine: Engine from `create_engine`
    :param voice: Voice name
    :param text: What to say
    :param path: Output file
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(wav_bytes(*engine.synthesize(voice, text)))


def generate(config, categories=None):
    """Render every phrase (and the loading words), or only the given phrase categories.

    Everything is rendered into a staging folder first, so Lisa keeps her old voice if generation fails.

    :param config: Settings
    :param categories: Phrase categories to render; all (including loading words) when None
    """
    engine = create_engine(config)
    voice, address = config["voice"]["name"], config["voice"]["address"]
    phrases = json.loads(PHRASES_FILE.read_text(encoding="utf-8"))
    selected = {name: lines for name, lines in phrases.items() if categories is None or name in categories}

    shutil.rmtree(STAGING_DIR, ignore_errors=True)
    for category, templates in selected.items():
        for i, template in enumerate(templates):
            text = format_line(template, address)
            render(engine, voice, text, STAGING_DIR / category / f"{i:02d}.wav")
            print(f"[{category}] {text}")

    finished = list(selected)
    if categories is None:
        words = json.loads(LOADING_WORDS_FILE.read_text(encoding="utf-8"))
        for i, word in enumerate(words, start=1):
            render(engine, voice, f"{word}...", STAGING_DIR / loading_word_clip(word).relative_to(AUDIO_DIR))
            print(f"\r[{LOADING_WORDS_CATEGORY}] {i}/{len(words)}", end="", flush=True)
        print()
        finished.append(LOADING_WORDS_CATEGORY)

    for category in finished:
        target = AUDIO_DIR / category
        shutil.rmtree(target, ignore_errors=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(STAGING_DIR / category), str(target))
    shutil.rmtree(STAGING_DIR, ignore_errors=True)
    print(f"\nGenerated with {config['voice']['engine']} voice '{voice}' into {AUDIO_DIR}")


def preview(config):
    """Play a sample of every voice of the configured engine.

    :param config: Settings
    """
    engine = create_engine(config)
    sample = format_line("Hello, {address}. I'm Lisa. After a deep dive into the code, here is the result.",
                         config["voice"]["address"])
    for voice in engine.voices():
        print(f"Playing voice: {voice}")
        winsound.PlaySound(wav_bytes(*engine.synthesize(voice, sample)), winsound.SND_MEMORY)
