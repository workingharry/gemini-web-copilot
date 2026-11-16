#!/usr/bin/env python3
"""
ai_studio_engine.py
High-performance Google AI Studio API Engine for Antigravity Gemini Copilot.
Direct REST generation with native thinking budgets and tiered model cascade:
  - High Jobs (plan, architect): gemini-4-argon (Medium Thinking: 4096) -> gemini-4-hydrogen (High Thinking: 16384) -> gemini-3.8-flash
  - Medium/Low Jobs (code, debug, review, test): gemini-4-hydrogen (High Thinking: 16384) -> gemini-3.8-flash
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

THINKING_BUDGET_MAP = {
    "off": 0,
    "low": 1024,
    "medium": 4096,
    "high": 16384,
}

TASK_SYSTEM_PROMPTS = {
    "plan": (
        "You are an enterprise software architect. Design scalable, resilient architectures. "
        "Detail state machines, failure modes, concurrency boundaries, and data synchronization patterns. "
        "Strictly avoid hand-waving or vague recommendations."
    ),
    "architect": (
        "You are an enterprise systems architect. Model domain entities, public seams, state machines, and concurrency boundaries. "
        "Ensure high cohesion, loose coupling, and make illegal states unrepresentable."
    ),
    "code": (
        "You are an expert principal software engineer operating under strict production standards. "
        "Model domain types first. Adhere to YAGNI: provide the minimal clean solution. "
        "Strictly zero phase-narrating comments (no narrative step comments). "
        "Zero half-products (no TODOs, no FIXMEs, no placeholder ellipses or empty stubs). "
        "When writing code, output complete, production-ready, testable implementations."
    ),
    "debug": (
        "You are a systems debugging expert performing Root Cause Analysis (RCA). "
        "Trace the defect to its foundational root cause. Detail race conditions, off-by-one errors, or lifecycle bugs. "
        "Provide minimal, targeted, and non-breaking surgical fixes accompanied by regression assertions."
    ),
    "review": (
        "You are a rigorous systems and security architect reviewing code. "
        "Probe boundary conditions, concurrency edge cases, null/overflow hazards, and resource leaks. "
        "Provide direct, actionable findings with exact file references and concrete assertions."
    ),
    "test": (
        "You are an adversarial test architect. Formulate comprehensive test suites covering happy paths, failure modes, and boundary extremes. "
        "Every test function must assert concrete behavioral invariants (strictly zero dummy assertions)."
    ),
    "general": (
        "You are a senior Google Gemini engineering assistant providing precise, technically sound, and concise responses."
    ),
}


def load_gemini_api_key(explicit_key: Optional[str] = None) -> str:
    """Load Gemini API Key from explicit arg, environment, local .env, or ~/.zshrc."""
    if explicit_key and explicit_key.strip():
        return explicit_key.strip()

    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key and env_key.strip():
        return env_key.strip()

    curr = Path.cwd()
    for parent in [curr] + list(curr.parents)[:4]:
        env_file = parent / ".env"
        if env_file.is_file():
            try:
                for line in env_file.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY="):
                        val = line.split("=", 1)[1].split("#", 1)[0].strip().strip('"').strip("'")
                        if val:
                            return val
            except (OSError, UnicodeDecodeError):
                continue

    zshrc = Path.home() / ".zshrc"
    if zshrc.is_file():
        try:
            for line in zshrc.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if "GEMINI_API_KEY=" in line and not line.startswith("#"):
                    rhs = line.split("GEMINI_API_KEY=", 1)[1].split("#", 1)[0].strip()
                    val = rhs.split()[0].strip('"').strip("'") if rhs else ""
                    if val:
                        return val
        except (OSError, UnicodeDecodeError):
            return ""

    raise RuntimeError("GEMINI_API_KEY not found in environment, .env, or ~/.zshrc.")


def resolve_model_cascade(task: str, explicit_model: Optional[str] = None) -> List[Tuple[str, int]]:
    """
    Resolve primary model and cascade list with designated thinking budgets.
    Returns list of (model_name, thinking_budget).
    """
    if explicit_model and explicit_model != "auto":
        # User specified a specific model
        budget = 16384 if "hydrogen" in explicit_model else (4096 if "argon" in explicit_model else 2048)
        return [
            (explicit_model, budget),
            ("gemini-4-hydrogen", 16384),
            ("gemini-3.8-flash", 2048),
        ]

    # High complexity tasks
    if task in ("plan", "architect"):
        return [
            ("gemini-4-argon", 4096),       # High job: Argon with medium thinking
            ("gemini-4-hydrogen", 16384),   # Fallback 1: Hydrogen with high thinking
            ("gemini-3.8-flash", 2048),     # Fallback 2: Flagship flash
        ]

    # Medium and Low complexity tasks (code, debug, review, test, general)
    return [
        ("gemini-4-hydrogen", 16384),       # Medium/Low job: Hydrogen with high thinking
        ("gemini-3.8-flash", 2048),         # Fallback: Flagship flash
    ]


def parse_thinking_budget(thinking_arg: Optional[str], default_budget: int) -> int:
    """Parse user thinking flag into integer token budget."""
    if not thinking_arg or thinking_arg == "auto":
        return default_budget
    arg_lower = str(thinking_arg).strip().lower()
    if arg_lower in THINKING_BUDGET_MAP:
        return THINKING_BUDGET_MAP[arg_lower]
    try:
        return max(0, int(arg_lower))
    except ValueError:
        return default_budget


def strip_code_fences_if_needed(text: str, output_path: Optional[str] = None) -> str:
    """Strip markdown code block fences when writing output directly to source files."""
    if not output_path:
        return text

    code_exts = {
        ".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs", ".swift",
        ".java", ".c", ".cpp", ".h", ".hpp", ".rb", ".sh", ".json", ".yaml", ".yml", ".sql"
    }
    ext = Path(output_path).suffix.lower()
    if ext not in code_exts:
        return text

    stripped = text.strip()
    blocks = re.findall(r"```[a-zA-Z0-9_-]*\r?\n(.*?)\r?\n```", stripped, re.DOTALL)
    if blocks:
        return "\n\n".join(b.strip() for b in blocks) + "\n"

    filtered = [l for l in stripped.splitlines() if not l.strip().startswith("```")]
    return "\n".join(filtered) + "\n"


def execute_ai_studio_query(
    prompt: str,
    task: str = "general",
    explicit_model: Optional[str] = None,
    explicit_thinking: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: int = 120,
) -> Dict[str, Any]:
    """
    Execute AI Studio prompt generation with thinking budgets and automatic error cascade.
    """
    try:
        key = load_gemini_api_key(api_key)
    except RuntimeError as e:
        return {
            "ok": False,
            "error": str(e),
            "output": "",
            "model_used": None,
        }

    cascade = resolve_model_cascade(task, explicit_model)
    system_prompt = TASK_SYSTEM_PROMPTS.get(task, TASK_SYSTEM_PROMPTS["general"])
    errors = []

    for model_name, default_budget in cascade:
        budget = parse_thinking_budget(explicit_thinking, default_budget)
        print(f"⚡ [AI Studio Engine] Attempting {model_name} (Thinking Budget: {budget})...", file=sys.stderr)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={key}"
        body: Dict[str, Any] = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_prompt}]},
        }

        gen_config: Dict[str, Any] = {}
        if budget > 0:
            gen_config["thinkingConfig"] = {"thinkingBudget": budget}
        if gen_config:
            body["generationConfig"] = gen_config

        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

        try:
            start_t = time.time()
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                duration = time.time() - start_t

                candidates = data.get("candidates", [])
                if not candidates:
                    errors.append(f"{model_name}: No candidates returned")
                    continue

                parts = candidates[0].get("content", {}).get("parts", [])
                output_text = "".join(p.get("text", "") for p in parts if "text" in p)

                # Collect thought summary if available
                thought_parts = [p.get("text", "") for p in parts if "thought" in p]
                thought_chars = sum(len(t) for t in thought_parts)

                print(
                    f"✅ [AI Studio Engine] {model_name} completed in {duration:.2f}s "
                    f"({len(output_text)} chars, thoughts: {thought_chars} chars)",
                    file=sys.stderr
                )

                return {
                    "ok": True,
                    "output": output_text,
                    "model_used": model_name,
                    "thinking_budget": budget,
                    "duration_sec": duration,
                    "error": None,
                }

        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"⚠️ [AI Studio Engine] {model_name} returned HTTP {e.code}: {err_body[:200]}", file=sys.stderr)
            errors.append(f"{model_name} (HTTP {e.code}): {err_body[:150]}")
            # If 429 rate limit or 503 high demand, immediately cascade to next model
            time.sleep(0.5)
            continue
        except Exception as e:
            print(f"⚠️ [AI Studio Engine] {model_name} error: {e}", file=sys.stderr)
            errors.append(f"{model_name}: {str(e)}")
            continue

    return {
        "ok": False,
        "error": "All models in cascade failed: " + "; ".join(errors),
        "output": "",
        "model_used": None,
    }
