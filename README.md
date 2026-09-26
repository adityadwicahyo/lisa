# Lisa

**An offline voice assistant for [Claude Code](https://claude.com/claude-code) on Windows.**
Lisa reads Claude's replies aloud, tells you what Claude is doing while it works, and types what you say
into Claude Code. Speech recognition and her voice run on your own computer; nothing is sent anywhere.

- 🔊 **Reads replies:** when Claude finishes, Lisa reads the first paragraph of its answer.
- 🛠️ **Narrates the work:** "Reading Login View Model", "Running unit tests", "Searching the web for…".
- 🎙️ **Takes voice prompts:** "Lisa, run the unit tests." She types it, asks "Shall I send it, sir?"
  and presses Enter when you say yes.
- 🙋 **Only your voice** (optional): she can learn your voice and ignore other people.
- 🔋 **Stays out of the way:** she listens only while Claude Code is open, pauses on battery, and turns
  off with one command or "Lisa, off".

## Requirements

- Windows 10 or 11, a microphone and speakers
- Python 3.11 or newer
- Claude Code (terminal, VS Code or JetBrains)
- About 1.5 GB of disk space for the voice and speech-recognition models

## Install

```powershell
git clone https://github.com/adityadwicahyo/lisa.git
cd lisa
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[voice-check]"
.\lisa.cmd install
```

`lisa install` downloads Lisa's voice, generates her spoken lines (a few minutes), adds her hooks to
`~/.claude/settings.json` (your other settings are kept), creates the `/lisa` command in Claude Code, and
puts `lisa` on your PATH. **Restart Claude Code** afterwards. The speech-recognition models download on
first use.

## Talking to Lisa

Start with her name, **"Lisa"**, then say what you want. Anything that doesn't start with "Lisa" is ignored.

### 1. Say "Lisa" and your prompt

> **"Lisa, run the unit tests."**

Lisa types `run the unit tests` into Claude Code. You can say it in one breath, or in two steps:

> **"Lisa."** … *"Yes, sir?"* … **"Run the unit tests."**

### 2. Answer her question

After typing, she asks something like *"Shall I send it, sir?"*:

| You answer                                   | Lisa                                              |
|----------------------------------------------|---------------------------------------------------|
| **"Yes"**, "Okay", "Send it", "Looks good"   | presses Enter, and Claude starts working          |
| **"Keep it"**, "Wait", "Hold on", "I'll edit it" | leaves the text for you to edit, right away   |
| *(nothing for 4 seconds)*                    | leaves the text for you to edit                   |
| **"No"**, "Cancel", "Never mind", "Delete it" | erases what she typed                            |

### Commands

Say these after "Lisa" instead of a prompt:

| You say                          | Lisa                                                             |
|----------------------------------|------------------------------------------------------------------|
| **"Lisa, never mind"**           | types nothing (*"Okay, never mind, sir."*)                       |
| **"Lisa, stop listening"**       | turns the microphone off; she still reads Claude's replies       |
| **"Lisa, off"**                  | turns herself off completely                                     |

To turn her back on, run `lisa on` (or `lisa mic on`) in a terminal, or `/lisa on` in Claude Code.

### Good to know

- The name only counts at the **start**: "please tell Lisa about the bug" is ignored.
- Commands only count as the **whole** sentence: "Lisa, turn off the debug logging" is typed as a prompt.
- You can change your mind mid-sentence: "Lisa, run the tests… actually, never mind" types nothing.
- A new "Lisa, …" **replaces** text she left unsent, unless you've typed in the box yourself since (then
  your edits stay and the new prompt goes after them).
- She types only into the apps in `typing.apps` (VS Code, Windows Terminal, JetBrains IDEs, …). If another app
  is focused, she copies the prompt to the clipboard and tells you.

## The `lisa` command

Run it in a terminal, or as `/lisa <command>` in Claude Code.

| Command                     | What it does                                                        |
|-----------------------------|---------------------------------------------------------------------|
| `lisa status`               | what is on and running                                              |
| `lisa on` / `lisa off`      | Lisa as a whole; off frees her memory, CPU and the microphone       |
| `lisa mic on` / `mic off`   | only the microphone                                                 |
| `lisa enroll`               | teach her your voice (read a text for 30 s, in a terminal)          |
| `lisa enroll short`         | add your short answers ("yes", "no") to your voiceprint             |
| `lisa enroll add`           | add another voiceprint, e.g. with a headset                         |
| `lisa generate`             | re-render her spoken lines after changing her voice or phrases      |
| `lisa voices`               | hear every available voice                                          |
| `lisa install` / `uninstall`| connect Lisa to Claude Code, or remove her hooks, command and PATH entry |

## Configuration

Settings live in [`config.default.json`](config.default.json). To change one, create `config.json` next to
it with only what you want different:

```json
{
  "voice": { "name": "bf_emma", "address": "boss" },
  "reply": { "read": "sentences", "max_sentences": 2 },
  "events": { "tool_use": false }
}
```

Every setting is explained in [docs/configuration.md](docs/configuration.md). Hook settings apply at once;
after changing her voice or phrases run `lisa generate`, and after changing listener settings run
`lisa mic off` and `lisa mic on`. Her lines are in [`phrases.json`](phrases.json) (`{address}` becomes
"sir" or your own `voice.address`).

## Privacy

- Everything runs locally: text-to-speech (Kokoro), speech-to-text (Whisper), voice detection and the voiceprint.
- Sentences that don't start with "Lisa" are transcribed in memory, checked for the name and dropped; they
  are never stored or logged.
- `.lisa/logs/` keeps the prompts you dictated and what Lisa said, for troubleshooting. Your voiceprint
  (`.lisa/voiceprint.npy`) is a list of numbers describing your voice, not a recording.

## Resource use

| Part                        | When                                  | Cost                                     |
|-----------------------------|---------------------------------------|------------------------------------------|
| Hook                        | each Claude Code event                | ~50 ms, exits at once                    |
| Speech server (her voice)   | after she speaks; exits after 60 min idle | ~400 MB RAM                          |
| Listener, quiet room        | Claude Code open and plugged in       | ~100 MB RAM, ~2% of one CPU core         |
| Listener, people talking    | each sentence is transcribed          | ~20–40% of one core                      |
| Prompt transcription        | after "Lisa, …"                       | ~500 MB RAM, unloaded after 10 min idle  |

## Troubleshooting

- **No sound:** `lisa status`, then `.lisa/logs/hook.log` and `.lisa/logs/server.log`.
- **She doesn't react to "Lisa":** is Claude Code open and the laptop plugged in? `lisa status` says why the
  listener is paused; `.lisa/logs/listener.log` shows what she heard.
- **Wrong microphone:** list devices with `.\.venv\Scripts\python.exe -m sounddevice` and set
  `listener.microphone` to the device's name or number.
- **Uninstall:** `lisa uninstall`, then delete the folder.

## How it works

Claude Code runs Lisa's hook on every event; a speech server keeps her voice loaded; a listener process
handles the microphone. See [docs/architecture.md](docs/architecture.md).

## Credits

[Kokoro](https://huggingface.co/hexgrad/Kokoro-82M) via [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx),
[faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Silero VAD](https://github.com/snakers4/silero-vad)
(the export published by [openWakeWord](https://github.com/dscripka/openWakeWord)),
[WeSpeaker](https://github.com/wenet-e2e/wespeaker) via [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx),
and optionally [Piper](https://github.com/OHF-Voice/piper1-gpl).

## License

[MIT](LICENSE)
