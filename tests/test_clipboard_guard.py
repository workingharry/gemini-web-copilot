#!/usr/bin/env python3
"""
Unit tests for ClipboardGuard and CopilotMutex.
"""

import sys
import unittest
from pathlib import Path

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from clipboard_guard import ClipboardGuard, CopilotMutex, read_system_clipboard, write_system_clipboard


class TestClipboardGuard(unittest.TestCase):
    def test_read_and_write_clipboard(self) -> None:
        initial = read_system_clipboard()
        test_val = "UNIT_TEST_CLIPBOARD_STRING_ALPHA"
        written = write_system_clipboard(test_val)
        self.assertTrue(written)
        self.assertEqual(read_system_clipboard(), test_val)

        # Restore
        write_system_clipboard(initial)
        self.assertEqual(read_system_clipboard(), initial)

    def test_clipboard_guard_restores_original_value(self) -> None:
        initial = read_system_clipboard()
        with ClipboardGuard(lock_timeout=5.0) as guard:
            write_system_clipboard("TEMPORARY_DIRTY_VALUE")
            self.assertEqual(read_system_clipboard(), "TEMPORARY_DIRTY_VALUE")

        # After exiting guard context, initial clipboard must be preserved
        self.assertEqual(read_system_clipboard(), initial)

    def test_copilot_mutex_acquisition(self) -> None:
        lock_file = "/tmp/test_copilot_unit.lock"
        with CopilotMutex(lock_file=lock_file, timeout=2.0) as mutex:
            self.assertIsNotNone(mutex.fd)


if __name__ == "__main__":
    unittest.main()
