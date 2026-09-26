"""The microphone listener (`python -m lisa.listener`): say "Lisa, <prompt>" and she types it into Claude Code.

    microphone → one spoken sentence (voice activity detection) → [voiceprint check] → quick speech-to-text
    → starts with "Lisa"? → accurate speech-to-text → command / "never mind" / prompt → type, ask, press Enter
"""
