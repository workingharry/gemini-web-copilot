#!/usr/bin/env python3
"""
clipboard_guard.py
Atomic clipboard preservation and process mutex for Antigravity Copilots.
Prevents host desktop clipboard destruction and cross-process CDP port collisions.
"""

import os
import sys
import time
import fcntl
import platform
import subprocess
from typing import Optional

LOCK_PATH = "/tmp/antigravity_browser_copilot.lock"
CURRENT_OS = platform.system()


def read_system_clipboard() -> str:
    """Read the current system clipboard text safely without throwing unhandled exceptions."""
    try:
        if CURRENT_OS == "Darwin":
            proc = subprocess.Popen(["pbpaste"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = proc.communicate(timeout=2.0)
            return out.decode("utf-8", errors="ignore")
        elif CURRENT_OS == "Windows":
            cmd = ["powershell", "-NoProfile", "-Command", "Get-Clipboard"]
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            out, _ = proc.communicate(timeout=2.0)
            return out.decode("utf-8", errors="ignore")
        else:
            for bin_name, args in [("xclip", ["-selection", "clipboard", "-o"]), ("wl-paste", [])]:
                try:
                    proc = subprocess.Popen([bin_name] + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    out, _ = proc.communicate(timeout=2.0)
                    return out.decode("utf-8", errors="ignore")
                except FileNotFoundError:
                    continue
    except (subprocess.SubprocessError, OSError, UnicodeDecodeError):
        return ""
    return ""


def write_system_clipboard(text: str) -> bool:
    """Write text to the system clipboard safely."""
    try:
        data = text.encode("utf-8")
        if CURRENT_OS == "Darwin":
            proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            proc.communicate(data, timeout=2.0)
            return proc.returncode == 0
        elif CURRENT_OS == "Windows":
            cmd = ["powershell", "-NoProfile", "-Command", "$input | Set-Clipboard"]
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            proc.communicate(data, timeout=2.0)
            return proc.returncode == 0
        else:
            for bin_name, args in [("xclip", ["-selection", "clipboard"]), ("wl-copy", [])]:
                try:
                    proc = subprocess.Popen([bin_name] + args, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    proc.communicate(data, timeout=2.0)
                    return proc.returncode == 0
                except FileNotFoundError:
                    continue
    except (subprocess.SubprocessError, OSError):
        return False
    return False


class CopilotMutex:
    """File lock mutex to prevent concurrent browser copilot port and focus collisions."""

    def __init__(self, lock_file: str = LOCK_PATH, timeout: float = 15.0):
        self.lock_file = lock_file
        self.timeout = timeout
        self.fd: Optional[int] = None

    def __enter__(self):
        start = time.time()
        self.fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR, 0o666)
        max_attempts = max(1, int(self.timeout / 0.25))

        for attempt in range(max_attempts):
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                os.ftruncate(self.fd, 0)
                os.write(self.fd, f"PID:{os.getpid()} TIME:{time.time()}\n".encode("utf-8"))
                return self
            except (BlockingIOError, IOError):
                if time.time() - start >= self.timeout:
                    break
                time.sleep(0.25)

        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

        raise TimeoutError(
            f"Could not acquire copilot lock ({self.lock_file}) within {self.timeout}s. "
            "Another copilot process is actively running."
        )

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            except OSError as err:
                sys.stderr.write(f"Warning: Failed to unlock {self.lock_file}: {err}\n")
            try:
                os.close(self.fd)
            except OSError as err:
                sys.stderr.write(f"Warning: Failed to close lock fd: {err}\n")
            self.fd = None
        return False


class ClipboardGuard:
    """
    Context manager that saves the host clipboard before copilot operations
    and restores it upon completion. Also acquires the copilot file mutex.
    """

    def __init__(self, lock_timeout: float = 15.0, restore_clipboard: bool = True):
        self.mutex = CopilotMutex(timeout=lock_timeout)
        self.restore_clipboard = restore_clipboard
        self.saved_clipboard: str = ""

    def __enter__(self):
        self.mutex.__enter__()
        if self.restore_clipboard:
            self.saved_clipboard = read_system_clipboard()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.restore_clipboard:
                write_system_clipboard(self.saved_clipboard)
        finally:
            self.mutex.__exit__(exc_type, exc_val, exc_tb)
        return False
