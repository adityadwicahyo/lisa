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

    def preload(self, name=None):
        """Load a model in the background (the accurate one by default) while you're still talking.

        :param name: Model to load
        """
        threading.Thread(target=self.model, args=(name or self.settings["model"],), daemon=True).start()

    def unload_if_idle(self):
        with self.lock:
            if self.models and time.monotonic() - self.last_used > self.settings["idle_minutes"] * 60:
                self.models = {}
                log("listener", "Speech-to-text models unloaded (idle)")

    def transcribe(self, frames, quick=False):
        """Text of the recorded audio, whitespace-normalized.

        :param frames: int16 16 kHz chunks
        :param quick: Use the quick model (to check sentences for "Lisa") instead of the accurate one
        """
        name = self.settings["quick_model"] if quick else self.settings["model"]
        return self._run(name, frames, initial_prompt=self.settings["hint"])

    def transcribe_answer(self, frames):
        """Text of a short answer to "Shall I send it?", hinted with the expected words.

        The length cap and no carry-over keep the hint from sending Whisper into a loop ("no, no, no, …").

        :param frames: int16 16 kHz chunks
        """
        return self._run(self.settings["answer_model"], frames, initial_prompt=self.settings["answer_hint"],
                         max_new_tokens=16, condition_on_previous_text=False, without_timestamps=True)

    def _run(self, name, frames, **options):
        audio = np.concatenate(frames).astype(np.float32) / 32768
        segments, _ = self.model(name).transcribe(audio, language=self.settings["language"], beam_size=5,
                                                  vad_filter=True, **options)
        return " ".join(" ".join(segment.text.strip() for segment in segments).split())
