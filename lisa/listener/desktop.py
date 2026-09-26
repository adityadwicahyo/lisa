"""Windows desktop actions: which window is focused, typing, Enter/Backspace, recent input, clipboard."""

import ctypes
import time
from ctypes import wintypes
from pathlib import Path

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = wintypes.LPVOID
kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]

VK_BACK, VK_RETURN = 0x08, 0x0D
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, INPUT_KEYBOARD = 0x2, 0x4, 1


def focused_window():
    return user32.GetForegroundWindow()


def focused_app():
    """Executable name of the focused window's process, e.g. "Code.exe"."""
    window = user32.GetForegroundWindow()
    if not window:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(window, ctypes.byref(pid))
    handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return Path(buffer.value).name
    finally:
        kernel32.CloseHandle(handle)


class _KeyboardInput(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _MouseInput(ctypes.Structure):  # Only here so the union has the size Windows expects.
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class _Input(ctypes.Structure):
    class _Union(ctypes.Union):
        _fields_ = [("ki", _KeyboardInput), ("mi", _MouseInput)]

    _anonymous_ = ("union",)
    _fields_ = [("type", wintypes.DWORD), ("union", _Union)]


def _send_key(virtual_key=0, scan=0, flags=0):
    events = (_Input * 2)()
    for event, extra in zip(events, (0, KEYEVENTF_KEYUP)):
        event.type = INPUT_KEYBOARD
        event.ki = _KeyboardInput(virtual_key, scan, flags | extra, 0, 0)
    user32.SendInput(2, events, ctypes.sizeof(_Input))


def type_text(text, delay_seconds):
    """Type text as Unicode key presses, like the on-screen keyboard; works in terminals and editors.

    :param text: Text to type (no Enter is pressed)
    :param delay_seconds: Pause between characters, so slow apps keep up
    """
    units = text.encode("utf-16-le")
    for i in range(0, len(units), 2):
        _send_key(scan=int.from_bytes(units[i:i + 2], "little"), flags=KEYEVENTF_UNICODE)
        time.sleep(delay_seconds)


def press_enter():
    _send_key(VK_RETURN)


def erase_typed(text, delay_seconds):
    """Backspace over text that was just typed (one press per character).

    :param text: The typed text
    :param delay_seconds: Pause between presses
    """
    for _ in text:
        _send_key(VK_BACK)
        time.sleep(delay_seconds)


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def last_input_tick():
    """Tick count of the last keyboard or mouse input (Lisa's own typing counts too), to spot you editing."""
    info = _LastInputInfo(ctypes.sizeof(_LastInputInfo), 0)
    user32.GetLastInputInfo(ctypes.byref(info))
    return info.dwTime


def copy_to_clipboard(text):
    """Put text on the clipboard. False if the clipboard stayed busy.

    :param text: Text to copy
    """
    data = ctypes.create_unicode_buffer(text)
    size = ctypes.sizeof(data)
    for _ in range(10):  # Another app may have the clipboard open for a moment.
        if user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return False
    try:
        user32.EmptyClipboard()
        handle = kernel32.GlobalAlloc(0x0002, size)  # GMEM_MOVEABLE
        pointer = kernel32.GlobalLock(handle)
        ctypes.memmove(pointer, data, size)
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(13, handle):  # CF_UNICODETEXT; the clipboard owns the memory on success.
            kernel32.GlobalFree(handle)
            return False
        return True
    finally:
        user32.CloseClipboard()
