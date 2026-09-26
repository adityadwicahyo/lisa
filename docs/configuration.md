# Configuration

Defaults are in [`config.default.json`](../config.default.json). Put your changes in `config.json` in the same
folder, with only the keys you want different; sections are merged, so `{"voice": {"name": "bf_emma"}}`
changes only the voice.

**When changes apply:** hook settings (`events`, `tool_use`, `reply`, `task_done`) on the next Claude Code
event. `voice` settings after `lisa generate` (for the clips) and `lisa off` + `lisa on` (for live speech).
Listener settings (`listener`, `wake`, `speech_to_text`, `typing`, `confirm`, `commands`, `voice_check`) after
`lisa mic off` + `lisa mic on`.

## voice

| Key       | Default    | Meaning                                                                        |
|-----------|------------|--------------------------------------------------------------------------------|
| `engine`  | `"kokoro"` | `"kokoro"`, or `"piper"` (needs `pip install -e ".[piper]"` and voices in `models/piper/`) |
| `name`    | `"af_bella"` | Kokoro: `af_bella`, `af_heart`, `af_nicole`, `af_sky`, `af_nova`, `af_sarah`, `bf_emma`, `bf_lily`, … (`lisa voices` plays them all) |
| `address` | `"sir"`    | How Lisa addresses you; replaces `{address}` in `phrases.json`                 |
| `speed`   | `1.0`      | Speaking speed                                                                 |
| `volume`  | `1.0`      | Loudness of her voice (Windows volume applies on top)                          |

## events

What Lisa reacts to.

| Key             | Default | Meaning                                                                            |
|-----------------|---------|------------------------------------------------------------------------------------|
| `session_start` | `true`  | Greeting when a Claude Code session starts or resumes                              |
| `prompt_submit` | `false` | "On it, sir." when you send a prompt                                               |
| `tool_use`      | `true`  | Say what Claude is doing ("Reading Login View Model")                              |
| `permission`    | `true`  | "I need your approval to proceed" when Claude waits for permission                 |
| `stop`          | `true`  | Speak when Claude finishes: the reply (see `reply`) or an end-of-task phrase       |
| `loading_word`  | `false` | Say Claude Code's loading word ("Zigzagging…") when you send a prompt. Rewrites `spinnerVerbs` in your Claude settings; see docs/architecture.md |

## tool_use

| Key               | Default | Meaning                                                  |
|-------------------|---------|----------------------------------------------------------|
| `min_gap_seconds` | `0`     | Minimum time between two tool descriptions               |

## reply

| Key                 | Default       | Meaning                                                                      |
|---------------------|---------------|------------------------------------------------------------------------------|
| `read`              | `"paragraph"` | `"paragraph"`: the first paragraph; `"sentences"`: the first `max_sentences`; `"off"`: an end-of-task phrase instead |
| `max_sentences`     | `2`           | For `"sentences"`                                                            |
| `max_words`         | `80`          | Either mode stops at the last full sentence within this many words          |
| `max_delay_seconds` | `60`          | How long a reply may wait behind other speech before it is skipped           |

## task_done

Picks the end-of-task phrase (`phrases.json`) when replies aren't read or have no prose.

| Key                       | Default | Meaning                                                           |
|---------------------------|---------|-------------------------------------------------------------------|
| `research_tool_threshold` | `5`     | Reads/searches in one turn that make it "research"                |
| `long_task_seconds`       | `180`   | Turns longer than this are "long"                                 |
| `build_command_keywords`  | gradle, npm run build, pytest, … | Shell commands containing one of these make it "build" |

## server

| Key                 | Default | Meaning                                                          |
|---------------------|---------|------------------------------------------------------------------|
| `port`              | `47321` | Local port of the speech server                                  |
| `max_delay_seconds` | `8`     | Tool descriptions older than this are skipped, so Lisa never lags behind |
| `idle_minutes`      | `60`    | The server exits (freeing its memory) after this long unused     |

## listener

| Key                          | Default          | Meaning                                                        |
|------------------------------|------------------|----------------------------------------------------------------|
| `enabled_on_battery`         | `false`          | Keep listening when the laptop is unplugged                    |
| `microphone`                 | `null`           | Device name or number (`python -m sounddevice` lists them); `null` = Windows default |
| `port`                       | `47322`          | Local port of the listener                                     |
| `claude_code_processes`      | `["claude.exe"]` | Processes that count as Claude Code being open                 |
| `claude_code_excluded_paths` | `["\\AnthropicClaude\\"]` | Paths that don't count (the Claude desktop app)       |
| `silence_seconds`            | `1.0`            | A pause this long ends what you're saying                      |
| `min_speech_seconds`         | `0.4`            | Shorter sounds are ignored                                     |
| `max_sentence_seconds`       | `20`             | Longest sentence or prompt                                     |
| `wait_for_prompt_seconds`    | `5`              | After a bare "Lisa", how long she waits for you to start       |

## wake

| Key            | Default                | Meaning                                                       |
|----------------|------------------------|---------------------------------------------------------------|
| `name`         | `"lisa"`               | Her name                                                      |
| `aliases`      | lisa, liza, elisa, …   | Spellings speech-to-text may produce for the name             |
| `prefix_words` | hey, ok, okay, hi, …   | Allowed before the name ("Hey Lisa, …")                       |

## speech_to_text

| Key            | Default      | Meaning                                                                    |
|----------------|--------------|----------------------------------------------------------------------------|
| `quick_model`  | `"tiny.en"`  | Checks every sentence for the name and transcribes yes/no answers          |
| `model`        | `"small.en"` | Transcribes prompts. `"base.en"` answers ~2 s faster, slightly less accurate |
| `language`     | `"en"`       | Spoken language (use multilingual models, e.g. `"small"`, for others)      |
| `hint`         | Claude, Lisa, README, … | Words it should expect; add names and terms it mishears        |
| `idle_minutes` | `10`         | Models are unloaded after this long unused                                 |

## typing

| Key        | Default | Meaning                                                                        |
|------------|---------|--------------------------------------------------------------------------------|
| `apps`     | Code.exe, WindowsTerminal.exe, JetBrains IDEs, … | Apps Lisa may type into; otherwise she copies to the clipboard |
| `delay_ms` | `5`     | Pause between typed characters                                                 |

## confirm

| Key               | Default | Meaning                                                              |
|-------------------|---------|----------------------------------------------------------------------|
| `enabled`         | `true`  | Ask "Shall I send it?" after typing; `false` leaves the text for you |
| `timeout_seconds` | `6`     | How long she waits for your answer                                   |
| `max_words`       | `6`     | Longer answers count as neither yes nor no                           |
| `send_words`      | yes, okay, send it, looks good, … | Answers that press Enter                   |
| `cancel_words`    | no, wait, cancel, not yet, …      | Answers that erase the text (they win over send words) |

## commands

| Key                     | Meaning                                                                      |
|-------------------------|------------------------------------------------------------------------------|
| `cancel_phrases`        | A whole prompt that means "never mind"                                       |
| `cancel_phrases_at_end` | Phrases that cancel even at the end of a longer prompt ("…, actually forget it") |
| `off_phrases`           | "Lisa, off": same as `lisa off`                                              |
| `mic_off_phrases`       | "Lisa, stop listening": same as `lisa mic off`                               |

## voice_check

Only your voice is accepted once you have run `lisa enroll` (needs `pip install -e ".[voice-check]"`).

| Key                   | Default | Meaning                                                               |
|-----------------------|---------|-----------------------------------------------------------------------|
| `enabled`             | `true`  | Use the voiceprint when one is enrolled                               |
| `threshold`           | `0.4`   | Match score (0-1) a sentence needs; the log shows scores to tune by  |
| `short_threshold`     | `0.3`   | For sentences shorter than `short_seconds` ("Lisa", "yes")            |
| `short_seconds`       | `1.0`   |                                                                       |
| `enroll_seconds`      | `30`    | Length of the `lisa enroll` reading                                   |
| `enroll_short_rounds` | `2`     | Rounds of short words in `lisa enroll short`                          |

## Other

| Key                    | Default                     | Meaning                                                           |
|------------------------|-----------------------------|-------------------------------------------------------------------|
| `claude_settings_path` | `"~/.claude/settings.json"` | Claude Code settings used by `lisa install` and the loading-word sync (the `LISA_CLAUDE_SETTINGS` environment variable overrides it) |
