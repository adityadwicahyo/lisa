"""Where Lisa keeps things. Everything lives inside the repository folder, so removing it removes Lisa."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CONFIG_DEFAULT = ROOT / "config.default.json"
CONFIG_USER = ROOT / "config.json"  # Your overrides; not committed.
PHRASES_FILE = ROOT / "phrases.json"
LOADING_WORDS_FILE = ROOT / "loading_words.json"

AUDIO_DIR = ROOT / "audio"  # Generated clips (`lisa generate`).
MODELS_DIR = ROOT / "models"  # Downloaded models.
KOKORO_DIR = MODELS_DIR / "kokoro"
PIPER_DIR = MODELS_DIR / "piper"
WHISPER_DIR = MODELS_DIR / "whisper"
SPEAKER_MODEL = MODELS_DIR / "speaker" / "wespeaker_en_voxceleb_resnet34.onnx"
VAD_MODEL = MODELS_DIR / "vad" / "silero_vad.onnx"

DATA_DIR = ROOT / ".lisa"  # Your local state, voiceprint and logs; not committed.
STATE_FILE = DATA_DIR / "state.json"
VOICEPRINT_FILE = DATA_DIR / "voiceprint.npy"
PLAYBACK_LOCK = DATA_DIR / "playback.lock"
LAST_CLIP_FILE = DATA_DIR / "last_clip"
NEXT_LOADING_WORD_FILE = DATA_DIR / "next_loading_word"
LAST_TOOL_SPOKEN_FILE = DATA_DIR / "last_tool_spoken"
LOG_DIR = DATA_DIR / "logs"
