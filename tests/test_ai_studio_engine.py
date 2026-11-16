#!/usr/bin/env python3
"""
Unit tests for AI Studio Engine.
"""

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from ai_studio_engine import (
    parse_thinking_budget,
    resolve_model_cascade,
    strip_code_fences_if_needed,
    TASK_SYSTEM_PROMPTS,
)


class TestAIStudioEngine(unittest.TestCase):
    def test_thinking_budget_parsing(self) -> None:
        self.assertEqual(parse_thinking_budget("off", 2048), 0)
        self.assertEqual(parse_thinking_budget("low", 2048), 1024)
        self.assertEqual(parse_thinking_budget("medium", 2048), 4096)
        self.assertEqual(parse_thinking_budget("high", 2048), 16384)
        self.assertEqual(parse_thinking_budget("8192", 2048), 8192)
        self.assertEqual(parse_thinking_budget("auto", 4096), 4096)

    def test_model_cascade_resolution(self) -> None:
        # High complexity task: plan/architect -> Argon (4096) first
        plan_cascade = resolve_model_cascade("plan")
        self.assertEqual(plan_cascade[0], ("gemini-4-argon", 4096))
        self.assertEqual(plan_cascade[1], ("gemini-4-hydrogen", 16384))

        # Medium/Low complexity task: code -> Hydrogen (16384) first
        code_cascade = resolve_model_cascade("code")
        self.assertEqual(code_cascade[0], ("gemini-4-hydrogen", 16384))

    def test_strip_code_fences_for_source_files(self) -> None:
        raw_code = "```python\ndef add(a: int, b: int) -> int:\n    return a + b\n```"
        stripped = strip_code_fences_if_needed(raw_code, "test.py")
        self.assertEqual(stripped.strip(), "def add(a: int, b: int) -> int:\n    return a + b")

        # Non-code files should keep fences intact
        markdown_text = "```python\ndef add(): pass\n```"
        kept = strip_code_fences_if_needed(markdown_text, "report.md")
        self.assertEqual(kept, markdown_text)

    def test_task_system_prompts_coverage(self) -> None:
        expected_tasks = ["plan", "architect", "code", "debug", "review", "test", "general"]
        for task in expected_tasks:
            self.assertIn(task, TASK_SYSTEM_PROMPTS)
            self.assertTrue(len(TASK_SYSTEM_PROMPTS[task]) > 20)


if __name__ == "__main__":
    unittest.main()
