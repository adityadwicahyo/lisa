"""Windows process helpers: background processes, local messages between them, Claude Code detection, power.

Lisa's background processes (speech server, listener) each listen on a local port. The port doubles as a
single-instance lock, and a one-shot JSON message is how other parts talk to them.
"""

import ctypes
import json
import socket
import subprocess
import sys
from pathlib import Path

from lisa.paths import ROOT


def spawn(module, *args):
    """Start `python -m <module>` detached and windowless, so the caller (often the hook) returns at once.

    :param module: Module to run, e.g. "lisa.speech.server"
    :param args: Command-line arguments
    """
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    subprocess.Popen([str(interpreter), "-m", module, *map(str, args)], cwd=ROOT, creationflags=flags,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)


def send_message(port, message, timeout=0.3):
    """Send one JSON message to a local Lisa process. Returns False when nothing listens on the port.

    :param port: Port of the target process
    :param message: JSON-serializable object
    :param timeout: Connection timeout in seconds
    """
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout) as connection:
            connection.sendall(json.dumps(message).encode("utf-8"))
        return True
    except OSError:
        return False


def is_running(port):
    return send_message(port, {"ping": True})


def receive_messages(listener_socket, handle):
    """Accept one-shot JSON messages forever and pass each to `handle`. Runs in a daemon thread.

    :param listener_socket: Bound, listening socket
    :param handle: Callback taking the decoded message
    """
    while True:
        connection, _ = listener_socket.accept()
        with connection:
            connection.settimeout(2)
            data = b""
            try:
                while chunk := connection.recv(65536):
                    data += chunk
                message = json.loads(data.decode("utf-8"))
            except (OSError, ValueError):
                continue
        handle(message)


def bind_port(port):
    """Listening socket on 127.0.0.1. Raises OSError (winerror 10048) if another instance already runs.

    :param port: Port to bind
    """
    listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener_socket.bind(("127.0.0.1", port))
    listener_socket.listen(16)
    return listener_socket


def is_port_in_use(error):
    return getattr(error, "winerror", None) == 10048


class _SystemPowerStatus(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]


def on_ac_power():
    """True when plugged in, or when Windows can't tell (a desktop without a battery)."""
    status = _SystemPowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return True
    return status.ACLineStatus != 0  # 0 = battery, 1 = plugged in, 255 = unknown


class _ProcessEntry32(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong), ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", ctypes.c_ulong),
                ("cntThreads", ctypes.c_ulong), ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_wchar * 260)]


def process_path(pid):
    """Full executable path of a process, or "" when it can't be read.

    :param pid: Process id
    """
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.restype = ctypes.c_void_p
    handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ""
    try:
        size = ctypes.c_ulong(1024)
        buffer = ctypes.create_unicode_buffer(size.value)
        ok = kernel32.QueryFullProcessImageNameW(ctypes.c_void_p(handle), 0, buffer, ctypes.byref(size))
        return buffer.value if ok else ""
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(handle))


def claude_code_running(config):
    """True while a Claude Code CLI process runs (terminal, VS Code or JetBrains), not the Claude desktop app.

    :param config: Settings; uses the `listener` process names and excluded paths
    """
    names = {name.lower() for name in config["listener"]["claude_code_processes"]}
    excluded = [part.lower() for part in config["listener"]["claude_code_excluded_paths"]]
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    snapshot = kernel32.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        return True  # Can't tell: keep listening rather than stop by mistake.
    try:
        entry = _ProcessEntry32()
        entry.dwSize = ctypes.sizeof(_ProcessEntry32)
        found = kernel32.Process32FirstW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
        while found:
            if entry.szExeFile.lower() in names:
                path = process_path(entry.th32ProcessID).lower()
                if not any(part in path for part in excluded):
                    return True
            found = kernel32.Process32NextW(ctypes.c_void_p(snapshot), ctypes.byref(entry))
        return False
    finally:
        kernel32.CloseHandle(ctypes.c_void_p(snapshot))
