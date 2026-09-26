import pytest

from lisa.listener.language import classify_answer, is_cancel, is_stray, match_wake, voice_command


@pytest.mark.parametrize("text, prompt", [
    ("Lisa, run the unit tests.", "run the unit tests."),
    ("lisa run the tests", "run the tests"),
    ("Hey Lisa, open the login screen.", "open the login screen."),
    ("Okay Lisa, commit this.", "commit this."),
    ("Liza, what time is it?", "what time is it?"),
    ("Elisa, build the app.", "build the app."),
    ("Lisa.", ""),
    ("Please tell Lisa about the bug.", None),
    ("The list of files is long.", None),
    ("Let's assume it works.", None),
    ("release the build", None),
])
def test_match_wake(config, text, prompt):
    assert match_wake(text, config) == prompt


@pytest.mark.parametrize("prompt, command", [
    ("Off.", "off"),
    ("Turn off now, please.", "off"),
    ("Go to sleep.", "off"),
    ("Goodbye.", "off"),
    ("Stop listening.", "mic off"),
    ("Turn off the microphone.", "mic off"),
    ("Turn off the debug logging.", None),
    ("Sleep for a while and then check the build.", None),
])
def test_voice_command(config, prompt, command):
    assert voice_command(prompt, config) == command


@pytest.mark.parametrize("prompt, cancelled", [
    ("Never mind.", True),
    ("Nevermind!", True),
    ("Never mind then, sorry.", True),
    ("Run the tests. Actually, forget it.", True),
    ("Fix the login bug, scratch that.", True),
    ("Nothing.", True),
    ("Add a button to cancel.", False),
    ("Never mind the warnings, fix the build.", False),
    ("Make the loop stop.", False),
    ("Run the unit tests.", False),
])
def test_is_cancel(config, prompt, cancelled):
    assert is_cancel(prompt, config) is cancelled


@pytest.mark.parametrize("answer, result", [
    ("Yes.", "send"),
    ("Okay, send it.", "send"),
    ("Oke.", "send"),
    ("Looks good.", "send"),
    ("No.", "cancel"),
    ("No, don't send it.", "cancel"),
    ("Not right.", "cancel"),
    ("Hmm.", None),
    ("Yes, but first check the log files please.", None),  # Too long to be a plain yes.
    ("", None),
])
def test_classify_answer(config, answer, result):
    assert classify_answer(answer, config) == result


@pytest.mark.parametrize("prompt, stray", [
    ("Thank you.", True),
    ("Lisa.", True),
    ("", True),
    ("List the files in this project.", False),
])
def test_is_stray(config, prompt, stray):
    assert is_stray(prompt, config) is stray
