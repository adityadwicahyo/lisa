"""Speech-to-text with faster-whisper: a quick model checks every sentence for "Lisa", an accurate one writes prompts.

Models are loaded on first use and unloaded after `speech_to_text.idle_minutes`, to give the memory back.
"""

import threading
import time

import numpy as np

from lisa.log import log
from lisa.paths import WHISPER_DIR


class SpeechToText:
    def __init__(self, config):
        self.settings = config["speech_to_text"]
        self.models = {}
        self.lock = threading.Lock()
        self.last_used = 0.0

    def model(self, name):
        with self.lock:
            if name not in self.models:
                from faster_whisper import WhisperModel

                started = time.monotonic()
                self.models[name] = WhisperModel(name, device="cpu", compute_type="int8",
                                                 download_root=str(WHISPER_DIR))
                log("listener", f"Speech-to-text model '{name}' loaded in {time.monotonic() - started:.1f}s")
            self.last_used = time.monotonic()
            return self.models[name]

    def preload(self):
        """Load the accurate model in the background while you're still talking."""
        threading.Thread(target=self.model, args=(self.settings["model"],), daemon=True).start()

    def unload_if_idle(self):
        with self.lock:
            if self.models and time.monotonic() - self.last_used > self.settings["idle_minutes"] * 60:
                self.models = {}
                log("listener", "Speech-to-text models unloaded (idle)")

    def transcribe(self, frames, quick=False):
        """Text of the recorded audio, whitespace-normalized.

        :param frames: int16 16 kHz chunks
        :param quick: Use the quick model (to check for "Lisa" or a yes/no) instead of the accurate one
        """
        name = self.settings["quick_model"] if quick else self.settings["model"]
        audio = np.concatenate(frames).astype(np.float32) / 32768
        segments, _ = self.model(name).transcribe(audio, language=self.settings["language"], beam_size=5,
                                                  vad_filter=True, initial_prompt=self.settings["hint"])
        return " ".join(" ".join(segment.text.strip() for segment in segments).split())
