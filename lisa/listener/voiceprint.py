"""Your voiceprint (`lisa enroll`), so the listener can ignore other people (`voice_check`).

A voiceprint is a speaker embedding: 256 numbers describing a voice, not a recording. Each enrollment adds one
to .lisa/voiceprint.npy, and a sentence is accepted when it is close enough (cosine similarity) to any of them.
Model: WeSpeaker ResNet34 via sherpa-onnx (~25 MB, `pip install sherpa-onnx`).
"""

import time

import numpy as np

from lisa.download import download
from lisa.listener import sounds
from lisa.paths import SPEAKER_MODEL, VOICEPRINT_FILE

MODEL_URL = ("https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/"
             "wespeaker_en_voxceleb_resnet34.onnx")
SAMPLE_RATE = 16000

READING = """\
    Good morning Lisa. Today I'm going to work on the project. First, open the
    login screen and check why the payment test keeps failing on the build server.
    After that, update the dependencies, run all the unit tests again, and write
    a short summary of what changed. If everything looks fine, prepare a commit message,
    but don't push anything yet. I'd like to review the changes myself before lunch."""

SHORT_WORDS = ["Yes", "No", "Send it", "Okay", "Lisa", "Cancel", "Submit", "Wait"]


class Voiceprint:
    def __init__(self, config):
        import sherpa_onnx

        download(MODEL_URL, SPEAKER_MODEL)
        self.extractor = sherpa_onnx.SpeakerEmbeddingExtractor(
            sherpa_onnx.SpeakerEmbeddingExtractorConfig(model=str(SPEAKER_MODEL), num_threads=1))
        self.settings = config["voice_check"]
        self.enrolled = np.load(VOICEPRINT_FILE) if VOICEPRINT_FILE.exists() else None

    def embed(self, audio):
        """Unit-length speaker embedding.

        :param audio: int16 samples at 16 kHz
        """
        stream = self.extractor.create_stream()
        stream.accept_waveform(SAMPLE_RATE, (np.asarray(audio, dtype=np.float32) / 32768).tolist())
        stream.input_finished()
        vector = np.array(self.extractor.compute(stream), dtype=np.float32)
        return vector / (np.linalg.norm(vector) or 1.0)

    def check(self, audio, speech_seconds):
        """(is it you, score). Short sentences ("Lisa", "yes") are judged against the more lenient threshold.

        :param audio: int16 samples at 16 kHz
        :param speech_seconds: How long the sentence is
        """
        score = float(np.max(self.enrolled @ self.embed(audio)))
        short = speech_seconds < self.settings["short_seconds"]
        return score >= self.settings["short_threshold" if short else "threshold"], score


def record(seconds):
    """Record from the default microphone.

    :param seconds: Length
    """
    import sounddevice

    audio = sounddevice.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sounddevice.wait()
    return audio[:, 0]


def trim_to_speech(audio, min_seconds=0.25):
    """The loud part of a short recording (plus 0.1 s either side), or None if nothing was said.

    :param audio: int16 samples at 16 kHz
    :param min_seconds: Shorter than this counts as nothing
    """
    frame = SAMPLE_RATE // 50  # 20 ms
    levels = np.array([np.sqrt(np.mean(audio[i:i + frame].astype(np.float32) ** 2))
                       for i in range(0, len(audio) - frame + 1, frame)])
    loud = np.flatnonzero(levels > max(300.0, 3 * np.percentile(levels, 20)))
    if len(loud) == 0:
        return None
    start, end = max(0, (loud[0] - 5) * frame), min(len(audio), (loud[-1] + 6) * frame)
    return audio[start:end] if end - start >= min_seconds * SAMPLE_RATE else None


def _normalized_mean(embeddings):
    mean = embeddings.mean(axis=0)
    return mean / np.linalg.norm(mean)


def _save(voiceprints):
    VOICEPRINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    np.save(VOICEPRINT_FILE, voiceprints)


def enroll(config, add=False):
    """Record you reading aloud and save the voiceprint. Returns the exit code.

    :param config: Settings
    :param add: Keep existing voiceprints (e.g. another microphone) instead of replacing them
    """
    seconds = config["voice_check"]["enroll_seconds"]
    print("Lisa will learn your voice, so she ignores other people.\n")
    print(f"After the beep, read this aloud at your normal pace and volume ({seconds} seconds):\n")
    print(READING + "\n")
    time.sleep(5)
    sounds.play(sounds.LISTENING)
    audio = record(seconds)
    sounds.play(sounds.DONE)

    segment = 3 * SAMPLE_RATE
    loud = [audio[i:i + segment] for i in range(0, len(audio) - segment + 1, segment)
            if np.sqrt(np.mean(audio[i:i + segment].astype(np.float32) ** 2)) > 300]  # Skip pauses.
    if len(loud) < 4:
        print("\nI couldn't hear enough speech. Check the microphone and run `lisa enroll` again.")
        return 1

    voiceprint = Voiceprint(config)
    embeddings = np.array([voiceprint.embed(chunk) for chunk in loud])
    centroid = _normalized_mean(embeddings)
    consistency = embeddings @ centroid
    voiceprints = (np.vstack([np.load(VOICEPRINT_FILE), centroid])
                   if add and VOICEPRINT_FILE.exists() else centroid[None, :])
    _save(voiceprints)

    threshold = config["voice_check"]["threshold"]
    print(f"\nSaved your voiceprint ({len(voiceprints)} in total).")
    print(f"Your {len(loud)} segments match it with scores {consistency.min():.2f}-{consistency.max():.2f} "
          f"(Lisa accepts from {threshold}).")
    if consistency.min() < threshold + 0.1:
        print("Some parts matched weakly. For a steadier voiceprint, run `lisa enroll` again in a quieter moment.")
    return 0


def enroll_short(config):
    """Add a voiceprint from short words, because one-word answers score low against a reading. Returns the exit code.

    :param config: Settings
    """
    if not VOICEPRINT_FILE.exists():
        print("Run `lisa enroll` first (the reading), then `lisa enroll short`.")
        return 1

    rounds = config["voice_check"]["enroll_short_rounds"]
    print("Lisa will learn how you say short answers.\n")
    print("Say each word right after its beep, the way you'd answer Lisa.\n")
    time.sleep(3)
    clips = []
    for round_number in range(1, rounds + 1):
        print(f"Round {round_number} of {rounds}")
        for word in SHORT_WORDS:
            print(f"  \"{word}\" ", end="", flush=True)
            time.sleep(0.6)  # Time to read the word before the beep.
            sounds.play(sounds.LISTENING)
            speech = trim_to_speech(record(1.8))
            print("ok" if speech is not None else "didn't hear it, skipped")
            if speech is not None:
                clips.append(speech)
    sounds.play(sounds.DONE)
    if len(clips) < len(SHORT_WORDS):
        print("\nToo few words were heard. Check the microphone and run `lisa enroll short` again.")
        return 1

    voiceprint = Voiceprint(config)
    embeddings = np.array([voiceprint.embed(clip) for clip in clips])
    previous = np.load(VOICEPRINT_FILE)
    before = np.max(embeddings @ previous.T, axis=1)
    # Score each word against a voiceprint of the *other* words: a fair estimate for future answers.
    after = np.array([max(before[i], float(embeddings[i] @ _normalized_mean(np.delete(embeddings, i, axis=0))))
                      for i in range(len(embeddings))])
    _save(np.vstack([previous, _normalized_mean(embeddings)]))

    print(f"\nSaved a short-word voiceprint ({len(previous) + 1} voiceprints in total).")
    print(f"Your short words scored {np.median(before):.2f} on average before, about {np.median(after):.2f} now "
          f"(lowest {after.min():.2f}; short answers are accepted from {config['voice_check']['short_threshold']}).")
    return 0
