"""The live speech server: keeps the voice model loaded and speaks sentences sent by the hook and the listener.

Messages (one JSON object per connection to 127.0.0.1:<server.port>):
    {"text": "...", "sent_at": <epoch seconds>}          speak, unless older than `server.max_delay_seconds`
    plus "kind": "response", "max_delay": <seconds>      a reply summary, allowed to wait longer
    {"cancel": "response", "sent_at": <epoch seconds>}   drop reply sentences not spoken yet
    {"shutdown": true}                                   exit now (`lisa off`)

Text is synthesized and played one sentence at a time, so a long reply starts after its first sentence.
Started on demand (`python -m lisa.speech.server [first message]`); exits after `server.idle_minutes` idle.
"""

import json
import os
import queue
import sys
import threading
import time
import traceback
import winsound

from lisa.config import load_config
from lisa.log import log as write_log
from lisa.speech.engines import create_engine, wav_bytes
from lisa.speech.player import playback_lock
from lisa.system import bind_port, is_port_in_use, receive_messages
from lisa.text.summarize import split_sentences


def log(message):
    write_log("server", message)


class SpeechServer:
    def __init__(self, config):
        self.config = config
        self.max_delay = config["server"]["max_delay_seconds"]
        self.idle_seconds = config["server"]["idle_minutes"] * 60
        self.last_activity = time.monotonic()
        self.replies_cancelled_at = 0.0
        self.to_synthesize = queue.Queue()
        self.to_play = queue.Queue()

        self.socket = bind_port(config["server"]["port"])  # Fails if a server already runs.
        self.engine = create_engine(config)
        self.voice = config["voice"]["name"]
        self.engine.synthesize(self.voice, "Ready.")  # Warm up, so the first real sentence is fast.

    def handle_message(self, message):
        if message.get("shutdown"):
            log("Shutdown requested, exiting")
            os._exit(0)
        elif message.get("cancel") == "response":
            self.replies_cancelled_at = message.get("sent_at", time.time())
        elif message.get("text"):
            message.setdefault("sent_at", time.time())
            self.last_activity = time.monotonic()
            self.to_synthesize.put(message)

    def is_stale(self, item):
        """True (and logged) when an item was cancelled or has waited too long to still be worth saying.

        :param item: Queued message for one sentence
        """
        if item.get("kind") == "response" and item["sent_at"] <= self.replies_cancelled_at:
            log(f"Skipped (new prompt sent): {item['text']}")
            return True
        waited = time.time() - item["sent_at"]
        if waited > item.get("max_delay", self.max_delay):
            log(f"Skipped (too late, {waited:.1f}s): {item['text']}")
            return True
        return False

    def synthesize_loop(self):
        while True:
            message = self.to_synthesize.get()
            for sentence in split_sentences(message["text"]):
                item = {**message, "text": sentence}
                if self.is_stale(item):
                    break
                try:
                    item["wav"] = wav_bytes(*self.engine.synthesize(self.voice, sentence))
                except Exception:
                    log(f"Synthesis failed for {sentence!r}:\n{traceback.format_exc()}")
                    continue
                self.to_play.put(item)

    def play_loop(self):
        while True:
            item = self.to_play.get()
            if self.is_stale(item):
                continue
            with playback_lock(max_wait_seconds=item.get("max_delay", self.max_delay)) as acquired:
                if acquired and not self.is_stale(item):
                    log(f"Speaking ({time.time() - item['sent_at']:.1f}s after it was sent): {item['text']}")
                    winsound.PlaySound(item["wav"], winsound.SND_MEMORY | winsound.SND_NODEFAULT)

    def run(self):
        threading.Thread(target=receive_messages, args=(self.socket, self.handle_message), daemon=True).start()
        for loop in (self.synthesize_loop, self.play_loop):
            threading.Thread(target=loop, daemon=True).start()
        log(f"Server started with {self.config['voice']['engine']} voice '{self.voice}'")
        while time.monotonic() - self.last_activity < self.idle_seconds:
            time.sleep(10)
        log("Idle timeout reached, exiting")


def main():
    try:
        server = SpeechServer(load_config())
        if len(sys.argv) > 1:  # The sentence that made the hook start this server.
            message = json.loads(sys.argv[1])
            message["sent_at"] = time.time()  # Don't count model loading time as delay.
            server.to_synthesize.put(message)
        server.run()
    except OSError as error:
        if not is_port_in_use(error):
            log(f"Server failed: {error!r}")
    except Exception:
        log(f"Server crashed:\n{traceback.format_exc()}")
    finally:
        os._exit(0)


if __name__ == "__main__":
    main()
