"""Text-to-speech engines. Each has `voices()` and `synthesize(voice, text) -> (int16 PCM bytes, sample rate)`.

    kokoro  voices like "af_bella", "af_heart", "bf_lily"   (models/kokoro/, the default)
    piper   voices like "en_US-lessac-medium"                 (models/piper/*.onnx, optional: pip install piper-tts)
"""

import io
import wave

import numpy as np

from lisa.paths import KOKORO_DIR, PIPER_DIR

KOKORO_FILES = {
    "kokoro-v1.0.onnx": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin": "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}


class KokoroEngine:
    def __init__(self, config):
        from kokoro_onnx import Kokoro

        self.kokoro = Kokoro(str(KOKORO_DIR / "kokoro-v1.0.onnx"), str(KOKORO_DIR / "voices-v1.0.bin"))
        self.speed = config["voice"]["speed"]
        self.volume = config["voice"]["volume"]

    def voices(self):
        return [voice for voice in self.kokoro.get_voices() if voice[:2] in ("af", "bf")]  # English, female

    def synthesize(self, voice, text):
        language = "en-gb" if voice.startswith("b") else "en-us"
        samples, rate = self.kokoro.create(text, voice=voice, speed=self.speed, lang=language)
        pcm = (np.clip(samples * self.volume, -1.0, 1.0) * 32767).astype(np.int16)
        return pcm.tobytes(), rate


class PiperEngine:
    def __init__(self, config):
        from piper import SynthesisConfig

        self.synthesis = SynthesisConfig(length_scale=1.0 / config["voice"]["speed"], volume=config["voice"]["volume"])
        self.loaded = {}

    def voices(self):
        return [model.stem for model in sorted(PIPER_DIR.glob("*.onnx"))]

    def synthesize(self, voice, text):
        from piper import PiperVoice

        if voice not in self.loaded:
            model = PIPER_DIR / f"{voice}.onnx"
            if not model.exists():
                raise FileNotFoundError(f"Piper voice model not found: {model}")
            self.loaded[voice] = PiperVoice.load(model)
        chunks = list(self.loaded[voice].synthesize(text, syn_config=self.synthesis))
        return b"".join(chunk.audio_int16_bytes for chunk in chunks), chunks[0].sample_rate


ENGINES = {"kokoro": KokoroEngine, "piper": PiperEngine}


def create_engine(config):
    name = config["voice"]["engine"]
    if name not in ENGINES:
        raise ValueError(f"Unknown voice engine '{name}'. Use one of: {', '.join(ENGINES)}")
    return ENGINES[name](config)


def wav_bytes(pcm_bytes, rate):
    """Wrap mono int16 PCM in a WAV container, for `winsound.SND_MEMORY` or a file.

    :param pcm_bytes: Mono 16-bit samples
    :param rate: Sample rate in Hz
    """
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        wav_file.writeframes(pcm_bytes)
    return buffer.getvalue()
