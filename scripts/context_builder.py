#!/usr/bin/env python3
"""
context_builder.py
智慧上下文打包引擎：自動收集專案元數據、目錄樹、依賴與相關原始碼，
並套用專業架構師 / 工程師 Prompt 範本，組合成完整的萬字級 Context Bundle。
"""

import os
import sys
import glob
import json
import subprocess
from pathlib import Path
from typing import List, Optional

IGNORE_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", ".nuxt", "__pycache__",
    ".cache", "coverage", ".turbo", "vendor", ".agent", ".gemini"
}

IGNORE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".zip", ".tar", ".gz",
    ".pdf", ".exe", ".dll", ".so", ".dylib", ".lock", "package-lock.json",
    "yarn.lock", "pnpm-lock.yaml"
}


def get_git_info(cwd: str) -> str:
    """獲取 Git 當前分支與狀態摘要"""
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=cwd, stderr=subprocess.DEVNULL
        ).decode().strip()
        status = subprocess.check_output(
            ["git", "status", "-s"], cwd=cwd, stderr=subprocess.DEVNULL
        ).decode().strip()
        diff_summary = subprocess.check_output(
            ["git", "diff", "--stat"], cwd=cwd, stderr=subprocess.DEVNULL
        ).decode().strip()

        lines = [f"- **Git Branch**: `{branch or 'HEAD'}`"]
        if status:
            modified_count = len(status.splitlines())
            lines.append(f"- **Uncommitted Changes**: {modified_count} files modified")
        if diff_summary:
            lines.append(f"- **Recent Diff Summary**:\n```\n{diff_summary[:400]}\n```")
        return "\n".join(lines)
    except Exception:
        return "- **Git**: Not a git repository or git not installed."


def get_project_metadata(root_dir: str) -> str:
    """自動掃描專案類型、依賴套件與技術棧"""
    root = Path(root_dir).resolve()
    meta_lines = []

    # 1. Node.js / TypeScript
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                name = data.get("name", "app")
                version = data.get("version", "0.0.0")
                deps = list(data.get("dependencies", {}).keys())[:12]
                dev_deps = list(data.get("devDependencies", {}).keys())[:8]
                meta_lines.append(f"- **Project Name**: `{name} v{version}` (Node.js ecosystem)")
                if deps:
                    meta_lines.append(f"- **Core Dependencies**: `{', '.join(deps)}`")
                if dev_deps:
                    meta_lines.append(f"- **Dev Dependencies**: `{', '.join(dev_deps)}`")
        except Exception:
            pass

    # 2. Python
    pyproject = root / "pyproject.toml"
    reqs = root / "requirements.txt"
    if pyproject.exists():
        meta_lines.append("- **Python Project**: `pyproject.toml` detected")
    elif reqs.exists():
        try:
            with open(reqs, "r", encoding="utf-8") as f:
                libs = [line.strip() for line in f if line.strip() and not line.startswith("#")][:10]
                meta_lines.append(f"- **Python Dependencies**: `{', '.join(libs)}`")
        except Exception:
            pass

    # 3. 目錄結構摘要 (限深 2 層)
    tree_lines = []
    try:
        for p in sorted(root.iterdir()):
            if p.name.startswith(".") or p.name in IGNORE_DIRS:
                continue
            if p.is_dir():
                tree_lines.append(f"  ├── {p.name}/")
                for sub in sorted(p.iterdir())[:8]:
                    if not sub.name.startswith(".") and sub.name not in IGNORE_DIRS:
                        tree_lines.append(f"  │   └── {sub.name}{'/' if sub.is_dir() else ''}")
            else:
                tree_lines.append(f"  ├── {p.name}")
    except Exception:
        pass

    if tree_lines:
        meta_lines.append("- **Project Directory Overview**:\n```text\n" + "\n".join(tree_lines[:25]) + "\n```")

    git_info = get_git_info(root_dir)
    meta_lines.append(git_info)

    return "\n".join(meta_lines) if meta_lines else "Standard project environment."


def detect_language(file_path: str) -> str:
    """根據副檔名判定語法高亮標籤"""
    ext = Path(file_path).suffix.lower()
    mapping = {
        ".ts": "typescript", ".tsx": "tsx", ".js": "javascript", ".jsx": "jsx",
        ".py": "python", ".json": "json", ".md": "markdown", ".html": "html",
        ".css": "css", ".scss": "scss", ".sh": "bash", ".bash": "bash",
        ".bat": "batch", ".ps1": "powershell", ".sql": "sql", ".rs": "rust",
        ".go": "go", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml"
    }
    return mapping.get(ext, "")


def collect_codebase_context(file_paths: List[str], root_dir: str = ".") -> str:
    """讀取指定的程式碼檔案並組裝成結構化 Markdown"""
    if not file_paths:
        return "_No specific files attached. Refer to project metadata above._"

    chunks = []
    root = Path(root_dir).resolve()

    for fp in file_paths:
        p = Path(fp)
        if not p.is_absolute():
            p = root / p

        if not p.exists() or p.is_dir():
            continue

        if p.suffix.lower() in IGNORE_EXTENSIONS:
            continue

        try:
            rel_path = p.relative_to(root)
        except Exception:
            rel_path = p.name

        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            lang = detect_language(str(p))
            chunks.append(f"### File: `{rel_path}`\n```{lang}\n{content.strip()}\n```\n")
        except Exception as e:
            chunks.append(f"### File: `{rel_path}`\n_Error reading file: {e}_\n")

    return "\n".join(chunks) if chunks else "_Specified files could not be read._"


def build_rich_prompt(
    task: str,
    instructions: str,
    include_files: Optional[List[str]] = None,
    root_dir: str = ".",
    template_dir: Optional[str] = None
) -> str:
    """
    根據任務類型 (plan, code, debug) 與上下文檔案，生成深度架構等級的完整 Prompt。
    """
    if not template_dir:
        template_dir = str(Path(__file__).resolve().parent.parent / "templates")

    template_file = Path(template_dir) / f"{task}_template.md"
    if not template_file.exists():
        # Fallback 到 plan 或通用範本
        template_file = Path(template_dir) / "plan_template.md"

    with open(template_file, "r", encoding="utf-8") as f:
        template_content = f.read()

    project_metadata = get_project_metadata(root_dir)
    codebase_context = collect_codebase_context(include_files or [], root_dir=root_dir)

    filled_prompt = template_content.replace("{INSTRUCTIONS}", instructions.strip())
    filled_prompt = filled_prompt.replace("{PROJECT_METADATA}", project_metadata)
    filled_prompt = filled_prompt.replace("{CODEBASE_CONTEXT}", codebase_context)

    return filled_prompt


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Context Builder for Gemini Web Copilot")
    parser.add_argument("--task", choices=["plan", "code", "debug"], default="plan", help="任務類型")
    parser.add_argument("--instructions", "-i", required=True, help="給予 Gemini 的核心指令")
    parser.add_argument("--include", "-f", nargs="*", help="附加的程式碼檔案清單")
    parser.add_argument("--root", default=".", help="專案根目錄")
    parser.add_argument("--output", "-o", help="產出檔案路徑")
    args = parser.parse_args()

    result = build_rich_prompt(
        task=args.task,
        instructions=args.instructions,
        include_files=args.include,
        root_dir=args.root
    )

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"✅ 豐富上下文提示詞已打包完成: {args.output} ({len(result)} 字元)")
    else:
        print(result)
