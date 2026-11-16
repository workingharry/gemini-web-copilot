#!/usr/bin/env python3
"""
Unit tests for Context Builder.
"""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from context_builder import build_rich_prompt, detect_language, get_git_info


class TestContextBuilder(unittest.TestCase):
    def test_detect_language(self) -> None:
        self.assertEqual(detect_language("app.ts"), "typescript")
        self.assertEqual(detect_language("script.py"), "python")
        self.assertEqual(detect_language("query.sql"), "sql")
        self.assertEqual(detect_language("unknown.xyz"), "")

    def test_build_rich_prompt_combines_sections(self) -> None:
        instructions = "Design a low-latency cache invalidator."
        prompt = build_rich_prompt(
            task="plan",
            instructions=instructions,
            include_files=[],
            root_dir=".",
        )
        self.assertIn("Principal Enterprise Software Architect", prompt)
        self.assertIn(instructions, prompt)
        self.assertIn("Project Context & Environment", prompt)

    def test_git_info_returns_string(self) -> None:
        git_info = get_git_info(".")
        self.assertIsInstance(git_info, str)
        self.assertTrue(len(git_info) > 0)


if __name__ == "__main__":
    unittest.main()
