"""The listening loop and what happens after "Lisa": prompt, cancel, command, typing and the send confirmation.

- One listener runs at a time (its port is the lock). It runs only while Lisa and the mic are on and Claude Code
  is open, and releases the microphone on battery unless `listener.enabled_on_battery`.
- It ignores the microphone while Lisa speaks, so she never hears herself.
- Sentences that don't start with "Lisa" are dropped without being logged.
"""

import collections
import queue
import threading
import time

import numpy as np

from lisa import system
from lisa.listener import desktop, sounds
from lisa.listener.language import classify_answer, is_cancel, is_stray, match_wake, voice_command
from lisa.listener.stt import SpeechToText
from lisa.listener.vad import VoiceActivityDetector
from lisa.log import log as write_log
from lisa.paths import VOICEPRINT_FILE
from lisa.speech import client
from lisa.speech.player import is_playing
from lisa.state import load_state

SAMPLE_RATE = 16000
CHUNK = 1280  # 80 ms of audio per microphone callback.
CHUNK_SECONDS = CHUNK / SAMPLE_RATE


def log(message):
    write_log("listener", message)


class Listener:
    def __init__(self, config):
        self.config = config
        self.settings = config["listener"]
        self.stop = threading.Event()
        self.audio = queue.Queue()
        self.stt = SpeechToText(config)
        self.vad = None
        self.voiceprint = None
        self.quiet_until = 0.0
        self.preroll = collections.deque(maxlen=6)  # The moment before speech starts (~0.5 s), so no word is clipped.
        self.reset_sentence()
        self.socket = system.bind_port(self.settings["port"])  # Fails if a listener already runs.

    # ---- running

    def handle_message(self, message):
        if message.get("shutdown"):
            log("Shutdown requested")
            self.stop.set()

    def should_run(self):
        state = load_state()
        if not (state["enabled"] and state["listening"]) or self.stop.is_set():
            return False
        if not system.claude_code_running(self.config):
            log("Claude Code closed: stopping")
            self.stop.set()
            return False
        return True

    def may_use_microphone(self):
        return self.settings["enabled_on_battery"] or system.on_ac_power()

    def load_models(self):
        self.vad = VoiceActivityDetector()
        if self.config["voice_check"]["enabled"] and VOICEPRINT_FILE.exists():
            from lisa.listener.voiceprint import Voiceprint

            self.voiceprint = Voiceprint(self.config)

    def run(self):
        threading.Thread(target=system.receive_messages, args=(self.socket, self.handle_message), daemon=True).start()
        self.load_models()
        log(f"Listener started, voice check {'on' if self.voiceprint else 'off'}")
        while self.should_run():
            if not self.may_use_microphone():
                log("On battery: microphone released")
                while self.should_run() and not self.may_use_microphone():
                    self.stt.unload_if_idle()
                    self.stop.wait(2)
                if self.may_use_microphone():
                    log("Plugged in: listening again")
                continue
            try:
                self.listen()
            except Exception as error:  # For example no microphone, or it was unplugged.
                log(f"Microphone error, retrying in 10s: {error!r}")
                self.stop.wait(10)
        log("Listener stopped")

    def listen(self):
        """Hear sentences until Lisa or the mic is turned off, Claude Code closes, or the laptop goes on battery."""
        import sounddevice

        def on_audio(data, frames, time_info, status):
            self.audio.put(data[:, 0].copy())

        with sounddevice.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=CHUNK,
                                     device=self.settings["microphone"], callback=on_audio):
            next_check = 0.0
            while True:
                if time.monotonic() >= next_check:
                    if not self.should_run() or not self.may_use_microphone():
                        return
                    self.stt.unload_if_idle()
                    next_check = time.monotonic() + 2
                chunk = self.next_chunk()
                if chunk is None:
                    continue
                if is_playing():
                    self.quiet_until = time.monotonic() + 0.8  # Let her voice fade from the room first.
                if time.monotonic() < self.quiet_until:
                    self.reset_sentence()
                    self.preroll.clear()
                    continue
                self.collect_sentence(chunk)

    def next_chunk(self):
        try:
            return self.audio.get(timeout=1)
        except queue.Empty:
            return None

    def clear_audio(self):
        while not self.audio.empty():
            self.audio.get_nowait()

    # ---- hearing sentences

    def reset_sentence(self):
        self.sentence, self.sentence_speech, self.sentence_silence = [], 0.0, 0.0

    def collect_sentence(self, chunk):
        """Add a chunk to the current sentence; when it ends (a pause), check whether it was meant for Lisa.

        :param chunk: 80 ms of int16 audio
        """
        speaking = self.vad.speech_probability(chunk) >= 0.5
        if not self.sentence:
            self.preroll.append(chunk)
            if speaking:
                self.sentence, self.sentence_speech, self.sentence_silence = list(self.preroll), CHUNK_SECONDS, 0.0
                self.preroll.clear()
            return

        self.sentence.append(chunk)
        if speaking:
            self.sentence_speech += CHUNK_SECONDS
            self.sentence_silence = 0.0
        else:
            self.sentence_silence += CHUNK_SECONDS

        ended = self.sentence_silence >= self.settings["silence_seconds"]
        too_long = len(self.sentence) * CHUNK_SECONDS >= self.settings["max_sentence_seconds"]
        if ended or too_long:
            frames = self.sentence[:len(self.sentence) - int(self.sentence_silence / CHUNK_SECONDS)]
            speech_seconds = self.sentence_speech
            self.reset_sentence()
            # The voice check (~50 ms) runs before speech-to-text (~800 ms), so other people's speech costs little.
            if speech_seconds >= self.settings["min_speech_seconds"] and self.is_owner(frames, speech_seconds, "sentence"):
                self.handle_sentence(frames)
                self.clear_audio()

    def is_owner(self, frames, speech_seconds, what):
        """True unless a voiceprint is enrolled and this is someone else's voice (only the score is logged).

        :param frames: Recorded chunks
        :param speech_seconds: Length of the speech
        :param what: What is being checked, for the log
        """
        if not self.voiceprint:
            return True
        accepted, score = self.voiceprint.check(np.concatenate(frames), speech_seconds)
        log(f"Voice check for {what}: {'you' if accepted else 'another voice, ignored'} (score {score:.2f})")
        return accepted

    def record_answer(self, wait_seconds, silence_seconds, max_seconds):
        """Record what you say next. None if you don't start within `wait_seconds`.

        :param wait_seconds: How long to wait for speech to start
        :param silence_seconds: Pause that ends the recording
        :param max_seconds: Longest recording
        """
        frames, speech_seconds, silence = [], 0.0, 0.0
        self.vad.reset()
        started = time.monotonic()
        while time.monotonic() - started < max_seconds:
            chunk = self.next_chunk()
            if chunk is None:
                continue
            frames.append(chunk)
            if self.vad.speech_probability(chunk) >= 0.5:
                speech_seconds += CHUNK_SECONDS
                silence = 0.0
            else:
                silence += CHUNK_SECONDS
            if speech_seconds == 0 and time.monotonic() - started > wait_seconds:
                return None
            if speech_seconds >= 0.3 and silence >= silence_seconds:
                break
        if speech_seconds < 0.3:
            return None
        return frames[:len(frames) - int(silence / CHUNK_SECONDS)] or frames  # Trailing silence isn't needed.

    def say(self, category, fallback):
        """Speak a phrase, then forget what the microphone heard meanwhile, so her words aren't taken as yours."""
        sounds.say(category, fallback)
        time.sleep(0.3)  # Let the room echo fade.
        self.clear_audio()

    # ---- after "Lisa"

    def handle_sentence(self, frames):
        """A sentence ended: act on it if it starts with "Lisa".

        :param frames: The sentence's audio
        """
        heard = self.stt.transcribe(frames, quick=True)
        prompt = match_wake(heard, self.config) if heard else None
        if prompt is None:
            return
        if not prompt:  # Just "Lisa": answer, then listen for the prompt.
            log(f"Name heard: {heard!r}")
            self.ask_for_prompt()
            return
        if self.handled_as_command_or_cancel(prompt):  # "Lisa, off": no need for the slower accurate pass.
            return
        accurate = self.stt.transcribe(frames)
        self.handle_prompt(match_wake(accurate, self.config) or prompt)

    def ask_for_prompt(self):
        self.say("wake", sounds.LISTENING)  # "Yes, sir?"
        self.stt.preload()
        frames = self.record_answer(self.settings["wait_for_prompt_seconds"], self.settings["silence_seconds"],
                                    self.settings["max_sentence_seconds"])
        if not frames:
            log("No prompt after the name")
            sounds.play(sounds.CANCELLED)
            return
        if not self.is_owner(frames, len(frames) * CHUNK_SECONDS, "prompt"):
            sounds.play(sounds.CANCELLED)
            return
        self.handle_prompt(self.stt.transcribe(frames))

    def handle_prompt(self, prompt):
        """Run a voice command, honor a "never mind", or type the prompt.

        :param prompt: Text after "Lisa"
        """
        if self.handled_as_command_or_cancel(prompt):
            return
        if is_stray(prompt, self.config):
            log(f"Ignored (not a prompt): {prompt!r}")
            sounds.play(sounds.CANCELLED)
            return
        log(f"Heard: {prompt}")
        self.deliver(prompt)

    def handled_as_command_or_cancel(self, prompt):
        command = voice_command(prompt, self.config)
        if command:
            from lisa import cli

            log(f"Voice command {command!r}: {prompt!r}")
            self.say("offline" if command == "off" else "mic_off", sounds.CANCELLED)  # Before the server stops.
            (cli.turn_off if command == "off" else cli.turn_mic_off)(self.config)
            self.stop.set()
            return True
        if is_cancel(prompt, self.config):
            log(f"Cancelled by you: {prompt!r}")
            self.say("cancelled", sounds.CANCELLED)  # "Okay, never mind, sir."
            return True
        return False

    # ---- typing and sending

    def deliver(self, text):
        """Type the prompt into the focused Claude Code window, or copy it to the clipboard if another app is focused.

        :param text: The prompt
        """
        app = desktop.focused_app()
        delay = self.config["typing"]["delay_ms"] / 1000
        if app.lower() in {name.lower() for name in self.config["typing"]["apps"]}:
            window = desktop.focused_window()
            desktop.type_text(text, delay)
            log(f"Typed into {app}")
            if self.config["confirm"]["enabled"]:
                self.confirm_and_send(window, text)
            else:
                sounds.play(sounds.DONE)
            return

        copied = desktop.copy_to_clipboard(text)
        log(f"Focused app '{app}' isn't in typing.apps; {'copied to clipboard' if copied else 'clipboard failed'}")
        message = ("Claude Code is not focused, so I copied your prompt to the clipboard" if copied
                   else "Claude Code is not focused, and I could not copy your prompt")
        address = self.config["voice"]["address"]
        client.speak(f"{message}, {address}." if address else f"{message}.", self.config)

    def confirm_and_send(self, window, text):
        """Ask "Shall I send it?"; press Enter on a clear yes, otherwise erase the text so the next prompt starts clean.

        Nothing is pressed if the focus moved to another window, and nothing is erased on a missing answer while
        you're using the keyboard or mouse (you may be editing it yourself).

        :param window: Window the text was typed into
        :param text: The typed prompt
        """
        typed_at = desktop.last_input_tick()
        self.say("confirm", sounds.LISTENING)
        frames = self.record_answer(self.config["confirm"]["timeout_seconds"], silence_seconds=0.7, max_seconds=6)
        if frames and not self.is_owner(frames, len(frames) * CHUNK_SECONDS, "answer"):
            frames = None  # Someone else answered: treat it as no answer.
        answer_text = self.stt.transcribe(frames, quick=True) if frames else ""
        answer = classify_answer(answer_text, self.config)
        same_window = desktop.focused_window() == window

        if answer == "send" and same_window:
            desktop.press_enter()
            log(f"Sent (answer {answer_text!r})")
            sounds.play(sounds.DONE)
            return
        if not same_window:
            log(f"Not sent (answer {answer_text!r}); the focus moved, so the text was left as is")
        elif answer != "cancel" and desktop.last_input_tick() != typed_at:
            log(f"Not sent (answer {answer_text!r}); you used the keyboard or mouse, so the text was left as is")
        else:
            desktop.erase_typed(text, self.config["typing"]["delay_ms"] / 1000)
            log(f"Not sent (answer {answer_text!r}); the typed text was removed")
        sounds.play(sounds.CANCELLED)
