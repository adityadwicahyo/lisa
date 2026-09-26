"""Voice activity detection with the Silero VAD model (the ONNX export used by openWakeWord, Apache-2.0)."""

import numpy as np

from lisa.download import download
from lisa.paths import VAD_MODEL

MODEL_URL = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/silero_vad.onnx"
SAMPLE_RATE = 16000


class VoiceActivityDetector:
    def __init__(self):
        import onnxruntime

        download(MODEL_URL, VAD_MODEL)
        options = onnxruntime.SessionOptions()
        options.inter_op_num_threads = options.intra_op_num_threads = 1
        self.session = onnxruntime.InferenceSession(str(VAD_MODEL), sess_options=options,
                                                    providers=["CPUExecutionProvider"])
        self.reset()

    def reset(self):
        """Forget the recurrent state, e.g. before listening for an answer."""
        self._h = np.zeros((2, 1, 64), dtype=np.float32)
        self._c = np.zeros((2, 1, 64), dtype=np.float32)

    def speech_probability(self, chunk, frame_size=640):
        """Average probability (0-1) that the chunk contains speech.

        :param chunk: int16 samples at 16 kHz
        :param frame_size: Samples per model step (40 ms)
        """
        probabilities = []
        for start in range(0, len(chunk) - frame_size + 1, frame_size):
            frame = (chunk[start:start + frame_size] / 32767).astype(np.float32)[None, :]
            output, self._h, self._c = self.session.run(
                None, {"input": frame, "h": self._h, "c": self._c, "sr": np.array(SAMPLE_RATE, dtype=np.int64)})
            probabilities.append(float(output[0][0]))
        return float(np.mean(probabilities)) if probabilities else 0.0
