#!/usr/bin/env python3
"""
gemini_copilot.py
Antigravity Copilot Bridge for Google Gemini:
  - Dual-Engine Architecture: Google AI Studio API (Primary with native thinking) + Web CDP Automation
  - Model Matrix & Thinking Budget Calibration:
      High Jobs (plan, architect): gemini-4-argon (Medium Thinking 4k) -> gemini-4-hydrogen (High Thinking 16k) -> gemini-3.8-flash
      Medium/Low Jobs (code, debug, review, test): gemini-4-hydrogen (High Thinking 16k) -> gemini-3.8-flash
  - Web Resilience:
      Auth-aware window placement (starts visible, moves off-screen only after login verification)
      Automated conversation deletion (prevents sidebar clutter, --keep-chat opt-out)
      Thread resumption (--chat-url / --resume for ongoing projects)
      Atomic desktop clipboard protection & process mutex (/tmp/antigravity_browser_copilot.lock)
"""

import argparse
import os
import platform
import shutil
import subprocess
import sys
import time
import urllib.request
import json
from pathlib import Path
from typing import Optional, Tuple

CURRENT_OS = platform.system()
DEBUG_PORT = 9333
CDP_URL = f"http://127.0.0.1:{DEBUG_PORT}"
PROFILE_DIR = os.path.expanduser("~/.gemini/chrome_profile")

# Import local helper engines
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from clipboard_guard import ClipboardGuard, read_system_clipboard, write_system_clipboard
from ai_studio_engine import execute_ai_studio_query, strip_code_fences_if_needed


def find_chrome_executable() -> str:
    """Find Google Chrome executable across macOS, Windows, and Linux."""
    if CURRENT_OS == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
        for p in candidates:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
    elif CURRENT_OS == "Windows":
        candidates = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
    else:
        for binary in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            p = shutil.which(binary)
            if p:
                return p
    raise FileNotFoundError(f"Google Chrome executable not found on {CURRENT_OS}.")


def is_cdp_ready() -> bool:
    """Check if Chrome CDP port responds with HTTP 200."""
    try:
        req = urllib.request.Request(f"{CDP_URL}/json/version", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def ensure_chrome_running(visible: bool = False) -> bool:
    """Launch detached Google Chrome instance if not already running."""
    if is_cdp_ready():
        return True

    print(f"🚀 未偵測到 {DEBUG_PORT} 端口，啟動 Chrome (獨立 Profile: {PROFILE_DIR})...", file=sys.stderr)
    os.makedirs(PROFILE_DIR, exist_ok=True)
    chrome_bin = find_chrome_executable()

    initial_pos = "100,100" if visible else "100,100"
    cmd = [
        chrome_bin,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        f"--window-position={initial_pos}",
        "--window-size=1280,800",
        "https://gemini.google.com/app",
    ]

    if CURRENT_OS == "Windows":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        )
    else:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
        )

    for _ in range(25):
        if is_cdp_ready():
            return True
        time.sleep(0.4)

    return is_cdp_ready()


def set_window_bounds_via_cdp(browser, left: int, top: int, width: int = 1280, height: int = 800) -> bool:
    """Reposition Chrome window bounds via CDP session."""
    try:
        cdp = browser.new_browser_cdp_session()
        target_info = cdp.send("Browser.getWindowForTarget")
        window_id = target_info.get("windowId")
        if window_id:
            cdp.send(
                "Browser.setWindowBounds",
                {
                    "windowId": window_id,
                    "bounds": {
                        "left": left,
                        "top": top,
                        "width": width,
                        "height": height,
                        "windowState": "normal",
                    },
                },
            )
            return True
    except Exception as err:
        sys.stderr.write(f"Notice: Failed to set window bounds: {err}\n")
    return False


def find_or_open_gemini_page(context, chat_url: Optional[str] = None):
    """Find existing or open Gemini tab. Supports thread resumption via chat_url."""
    if chat_url and chat_url.strip():
        url = chat_url.strip()
        print(f"🔗 正在恢復既有 Gemini 對話: {url}", file=sys.stderr)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            page.goto(url, timeout=30000, wait_until="commit")
        except Exception as err:
            sys.stderr.write(f"Notice: Failed to navigate chat url {url}: {err}\n")
        page.bring_to_front()
        time.sleep(1.0)
        return page

    # Look for existing Gemini page
    for page in context.pages:
        if "gemini.google.com" in page.url:
            print(f"🔗 發現已存在的 Gemini 標籤頁: {page.url}，帶至前景...", file=sys.stderr)
            page.bring_to_front()
            if page.url != "https://gemini.google.com/app":
                try:
                    page.goto("https://gemini.google.com/app", timeout=20000, wait_until="commit")
                except Exception as err:
                    sys.stderr.write(f"Notice: Navigation to /app notice: {err}\n")
            else:
                new_btn = page.query_selector("button[aria-label*='New chat'], button[aria-label*='發起新對話'], a[href='/app']")
                if new_btn and len(page.query_selector_all("model-response")) > 0:
                    try:
                        new_btn.click()
                        time.sleep(1.5)
                    except Exception as err:
                        sys.stderr.write(f"Notice: New chat click notice: {err}\n")
            time.sleep(1.0)
            return page

    # Use first empty tab if available
    if len(context.pages) > 0:
        page = context.pages[0]
        print("🌐 使用現有頁面導航至 Gemini...", file=sys.stderr)
        try:
            page.goto("https://gemini.google.com/app", timeout=30000, wait_until="commit")
        except Exception as err:
            sys.stderr.write(f"Notice: Page goto /app notice: {err}\n")
        page.bring_to_front()
        time.sleep(1.0)
        return page

    print("🌐 開啟新的 Gemini 標籤頁...", file=sys.stderr)
    page = context.new_page()
    try:
        page.goto("https://gemini.google.com/app", timeout=30000, wait_until="commit")
    except Exception as err:
        sys.stderr.write(f"Notice: New page goto /app notice: {err}\n")
    page.bring_to_front()
    time.sleep(1.0)
    return page


def locate_input_box(page, timeout_sec: int = 15):
    """Locate Gemini prompt input box with retry."""
    selectors = [
        "rich-textarea div[contenteditable='true']",
        "div.ql-editor[contenteditable='true']",
        "div[role='textbox']",
        "textarea[placeholder*='Prompt']",
        "div[contenteditable='true']",
    ]
    start = time.time()
    while time.time() - start < timeout_sec:
        for sel in selectors:
            try:
                elem = page.wait_for_selector(sel, state="visible", timeout=1500)
                if elem:
                    return elem, sel
            except Exception:
                continue
        time.sleep(0.5)
    raise RuntimeError("無法定位 Gemini 輸入框，請確認網頁是否正常加載或是否已登入 Google 帳號。")


def send_prompt_web(page, prompt_text: str, file_path: Optional[str] = None):
    """Inject prompt and submit via Gemini Web UI."""
    input_elem, _ = locate_input_box(page)
    input_elem.click()

    if file_path and os.path.exists(file_path):
        file_size = os.path.getsize(file_path)
        print(f"📎 準備上傳 Context 檔案: {file_path} ({file_size} bytes)", file=sys.stderr)
        file_inputs = page.query_selector_all("input[type='file']")
        uploaded = False
        for fi in file_inputs:
            try:
                fi.set_input_files(file_path)
                uploaded = True
                print("✅ 檔案已成功注入檔案上傳器，等待晶片就緒...", file=sys.stderr)
                time.sleep(2)
                break
            except Exception:
                continue

        if not uploaded:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            prompt_text = f"{prompt_text}\n\n```\n{content}\n```"

    # Use clipboard for large text insertion to prevent browser typing freezes
    if len(prompt_text) > 400:
        print(f"📋 Prompt 字數較長 ({len(prompt_text)} 字)，使用剪貼簿快速貼上...", file=sys.stderr)
        try:
            write_system_clipboard(prompt_text)
            paste_key = "Meta+V" if CURRENT_OS == "Darwin" else "Control+V"
            page.keyboard.press(paste_key)
            time.sleep(0.5)
        except Exception:
            page.keyboard.insert_text(prompt_text)
    else:
        page.keyboard.insert_text(prompt_text)

    time.sleep(0.5)
    # Check if text was pasted properly; fallback to insert_text if missing
    current_text = input_elem.inner_text().strip()
    if len(current_text) < min(80, len(prompt_text)):
        input_elem.click()
        page.keyboard.press("Meta+A" if CURRENT_OS == "Darwin" else "Control+A")
        page.keyboard.press("Backspace")
        time.sleep(0.2)
        page.keyboard.insert_text(prompt_text)
        time.sleep(0.8)

    # Click send button
    send_selectors = [
        "button[aria-label*='傳送']",
        "button[aria-label*='Send']",
        "button[aria-label*='發送']",
        "button.send-button",
        "button[data-test-id='send-button']",
    ]
    sent = False
    for _ in range(10):
        for s_sel in send_selectors:
            btn = page.query_selector(s_sel)
            if btn and btn.is_visible() and btn.is_enabled():
                btn.click()
                sent = True
                print("🚀 已點擊送出按鈕！", file=sys.stderr)
                break
        if sent:
            break
        time.sleep(0.5)

    if not sent:
        print("⌨️ 未找到啟用狀態的送出按鈕，嘗試按 Enter 送出...", file=sys.stderr)
        page.keyboard.press("Enter")


def wait_for_web_generation_complete(page, timeout_sec: int = 300, expected_response_count: int = 1) -> bool:
    """Wait until expected model-response finishes generating."""
    print(f"⏳ 等待 Gemini 生成回應中 (期望回應序號 >= {expected_response_count}, 最長等待: {timeout_sec}s)...", file=sys.stderr)
    stop_selectors = [
        "button[aria-label*='停止']",
        "button[aria-label*='Stop']",
        "button[data-test-id='stop-button']",
    ]

    start_time = time.time()
    end_time = start_time + timeout_sec

    # Wait for target model-response to appear
    while time.time() < end_time:
        responses = page.query_selector_all("model-response")
        if len(responses) >= expected_response_count:
            break
        time.sleep(0.5)

    # Wait for completion (Copy button visible and Stop button absent)
    while time.time() < end_time:
        responses = page.query_selector_all("model-response")
        if len(responses) >= expected_response_count:
            target_resp = responses[-1]
            copy_btn = target_resp.query_selector("button[aria-label='Copy'], button[aria-label='複製']")
            is_stop_visible = any(
                page.query_selector(s) and page.query_selector(s).is_visible()
                for s in stop_selectors
            )
            if copy_btn and copy_btn.is_visible() and not is_stop_visible:
                text = target_resp.inner_text().strip()
                if len(text) > 10:
                    time.sleep(1.0)
                    print("✅ 生成完畢！(偵測到新回應專屬 Copy 按鈕就緒)", file=sys.stderr)
                    return True
        time.sleep(1.0)

    print("⚠️ 等待超時...", file=sys.stderr)
    return False


def extract_web_response_markdown(page) -> str:
    """Extract pristine markdown by clicking the native Copy button on latest model-response."""
    print("📋 正在提取 Gemini 回應...", file=sys.stderr)
    write_system_clipboard("")

    responses = page.query_selector_all("model-response")
    if responses:
        latest_mr = responses[-1]
        copy_btn = latest_mr.query_selector("button[aria-label='Copy'], button[aria-label='複製']")
        if copy_btn:
            try:
                copy_btn.scroll_into_view_if_needed()
                copy_btn.click()
                time.sleep(1.0)
                copied_text = read_system_clipboard()
                if copied_text and len(copied_text.strip()) > 0:
                    print(f"✨ 成功透過原生 Copy 按鈕獲取純淨 Markdown ({len(copied_text)} 字元)！", file=sys.stderr)
                    return copied_text
            except Exception as e:
                print(f"⚠️ 點擊複製按鈕讀取剪貼簿失敗: {e}", file=sys.stderr)

        # Fallback to inner_text
        print("ℹ️ 啟用 model-response 文本提取 Fallback...", file=sys.stderr)
        raw_text = latest_mr.inner_text().strip()
        for prefix in ("Gemini 話\n\n", "Gemini said\n\n", "Gemini\n\n"):
            if raw_text.startswith(prefix):
                raw_text = raw_text[len(prefix):].strip()
        if raw_text:
            return raw_text

    return "⚠️ 未能獲取到回應內容，請檢查瀏覽器視窗中的 Gemini 對話。"


def delete_active_gemini_chat(page) -> bool:
    """Delete current temporary conversation to keep sidebar clean."""
    print("🧹 正在自動清理暫存對話 (保持 Gemini 側邊欄乾淨)...", file=sys.stderr)
    try:
        # Hover over current conversation or search for options menu button
        menu_selectors = [
            "button[aria-label*='Conversation options']",
            "button[aria-label*='對話選項']",
            "button[aria-label*='More options']",
            "button[aria-label*='更多選項']",
            "conversations-list-item[selected='true'] button[aria-label*='More']",
            "conversations-list-item.selected button[aria-label*='More']",
            "button[data-test-id='conversation-actions-menu-button']",
        ]
        menu_btn = None
        for sel in menu_selectors:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                menu_btn = btn
                break

        if not menu_btn:
            selected_item = page.query_selector("conversations-list-item.selected, .conversation.selected")
            if selected_item:
                selected_item.hover()
                time.sleep(0.3)
                menu_btn = selected_item.query_selector("button[aria-label*='More'], button[aria-label*='選項'], button.menu-button")

        if menu_btn:
            menu_btn.click()
            time.sleep(0.5)

            # Click Delete menu item
            delete_selectors = [
                "div[role='menuitem']:has-text('Delete')",
                "div[role='menuitem']:has-text('刪除')",
                "button:has-text('Delete')",
                "button:has-text('刪除')",
                "[data-test-id='delete-chat-menu-item']",
            ]
            for d_sel in delete_selectors:
                del_item = page.query_selector(d_sel)
                if del_item and del_item.is_visible():
                    del_item.click()
                    time.sleep(0.5)
                    break

            # Confirm delete dialog
            confirm_selectors = [
                "mat-dialog-actions button:has-text('Delete')",
                "mat-dialog-actions button:has-text('刪除')",
                "button[data-test-id='confirm-delete-button']",
                "button:has-text('Delete')",
                "button:has-text('刪除')",
            ]
            for c_sel in confirm_selectors:
                conf = page.query_selector(c_sel)
                if conf and conf.is_visible():
                    conf.click()
                    time.sleep(0.8)
                    print("✨ 暫存對話已成功刪除！", file=sys.stderr)
                    return True
    except Exception as e:
        print(f"ℹ️ 清理對話提示: {e}", file=sys.stderr)
    return False


def run_web_flow(args, prompt_content: str) -> str:
    """Execute Gemini prompt using Playwright Chrome automation."""
    from playwright.sync_api import sync_playwright

    # Ensure Chrome is running
    if not ensure_chrome_running(visible=args.visible):
        print(f"❌ 無法連接至 Chrome 調試端口 ({DEBUG_PORT})！", file=sys.stderr)
        sys.exit(1)

    with sync_playwright() as p:
        print(f"🔌 連接至 Chrome CDP: {CDP_URL}", file=sys.stderr)
        browser = p.chromium.connect_over_cdp(CDP_URL)
        default_context = browser.contexts[0]

        try:
            default_context.grant_permissions(["clipboard-read", "clipboard-write"])
        except Exception as err:
            sys.stderr.write(f"Notice: Grant permissions notice: {err}\n")

        page = find_or_open_gemini_page(default_context, chat_url=args.chat_url or args.resume)

        if args.launch_only:
            print("✅ Chrome 與 Gemini 網頁版已就緒！", file=sys.stderr)
            return "READY"

        # Check authentication / input box availability
        try:
            locate_input_box(page, timeout_sec=6)
            is_authenticated = True
        except RuntimeError:
            is_authenticated = False

        if not is_authenticated:
            set_window_bounds_via_cdp(browser, left=100, top=100)
            print("⚠️ 偵測到尚未登入 Google 或需要驗證，瀏覽器視窗已置於前景 (100, 100)，請在視窗中完成登入！", file=sys.stderr)
            locate_input_box(page, timeout_sec=60)
            print("✅ 登入驗證成功！", file=sys.stderr)

        # If authenticated and user did not specify --visible, reposition off-screen
        if not args.visible:
            set_window_bounds_via_cdp(browser, left=-3000, top=-3000)

        initial_response_count = len(page.query_selector_all("model-response"))

        # Send Prompt
        send_prompt_web(page, prompt_content, file_path=args.context_file)

        # Wait for generation to finish
        wait_for_web_generation_complete(
            page,
            timeout_sec=args.timeout,
            expected_response_count=initial_response_count + 1,
        )

        # Extract markdown
        result = extract_web_response_markdown(page)

        # Auto-delete temporary chat unless user requested to keep it or resumed an existing project
        if not args.keep_chat and not (args.chat_url or args.resume):
            delete_active_gemini_chat(page)

        # Close Chrome window unless --keep-open is requested
        if not args.keep_open:
            try:
                print("🚪 正在關閉 Chrome 視窗...", file=sys.stderr)
                cdp = browser.new_browser_cdp_session()
                cdp.send("Browser.close")
            except Exception as err:
                try:
                    page.close()
                except Exception as inner_err:
                    sys.stderr.write(f"Notice: Page close notice: {inner_err}\n")

        return result


def main():
    parser = argparse.ArgumentParser(description="Antigravity Gemini Copilot Bridge (Dual-Engine: AI Studio + Web)")
    parser.add_argument("--engine", choices=["auto", "api", "web"], default="auto",
                        help="執行引擎: auto (預設智慧路由至 AI Studio API), api (純 Google AI Studio), web (瀏覽器自動化)")
    parser.add_argument("--prompt", "-p", help="發送給 Gemini 的文字提示詞")
    parser.add_argument("--prompt-file", help="從指定的檔案讀取提示詞")
    parser.add_argument("--context-file", "-f", help="附加的程式碼或設計 Context 檔案路徑")
    parser.add_argument("--output", "-o", help="將生成的 Markdown/代碼寫入指定檔案")
    parser.add_argument("--timeout", type=int, default=300, help="等待生成完成的最長秒數 (預設: 300)")
    parser.add_argument("--launch-only", action="store_true", help="僅啟動並連接 Chrome，不發送 Prompt")

    # 任務與上下文增強參數
    parser.add_argument("--task", choices=["plan", "architect", "code", "debug", "review", "test", "general"],
                        default="general", help="任務領域 (plan, architect, code, debug, review, test, general)")
    parser.add_argument("--instructions", "-i", help="任務目標指令 (搭配 --task 使用)")
    parser.add_argument("--include", nargs="*", help="包含在 Context 中的專案檔案清單")
    parser.add_argument("--auto-context", action="store_true", help="自動掃描專案元數據 (package.json, git, 目錄樹) 並打包")

    # 模型與思考等級控制
    parser.add_argument("--model", "-m", help="指定模型 (例如 gemini-4-argon, gemini-4-hydrogen, gemini-3.8-flash)")
    parser.add_argument("--thinking", help="Thinking 等級或 Token 預算: auto, off, low (1k), medium (4k), high (16k), 或整數")

    # Web 引擎專屬參數
    parser.add_argument("--chat-url", "--resume", dest="resume", help="恢復既有對話 URL (未完成專案接續使用)")
    parser.add_argument("--keep-chat", action="store_true", help="保留對話記錄 (預設 web 模式會自動刪除暫存對話)")
    parser.add_argument("--visible", action="store_true", help="強制瀏覽器視窗顯示於螢幕前景 (不隱藏至 -3000,-3000)")
    parser.add_argument("--keep-open", action="store_true", help="獲取數據後保持瀏覽器視窗開啟")

    args = parser.parse_args()

    # Collect prompt content
    prompt_content = ""
    if args.prompt_file and os.path.exists(args.prompt_file):
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            prompt_content = f.read()
    elif args.prompt:
        prompt_content = args.prompt

    # Rich Context Packaging via context_builder
    if args.task or args.include or args.auto_context:
        try:
            from context_builder import build_rich_prompt
            raw_instructions = args.instructions or prompt_content
            if not raw_instructions and not args.launch_only:
                print("❌ 請提供 --instructions 或 --prompt 指定具體需求！", file=sys.stderr)
                sys.exit(1)

            if raw_instructions:
                prompt_content = build_rich_prompt(
                    task=args.task,
                    instructions=raw_instructions,
                    include_files=args.include,
                    root_dir=".",
                )
                print(f"📦 已智慧組裝豐富上下文 ({len(prompt_content)} 字元，任務類型: {args.task})", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ 上下文打包警告: {e}，使用原始提示詞", file=sys.stderr)

    if not prompt_content and not args.launch_only:
        print("❌ 請提供 --prompt, --prompt-file 或 --instructions！", file=sys.stderr)
        sys.exit(1)

    result_text = ""

    # Engine Execution Decision
    # If user explicitly supplied web parameters (--resume, --visible, --keep-open), route to web
    chosen_engine = args.engine
    if chosen_engine == "auto" and (args.resume or args.visible or args.launch_only):
        chosen_engine = "web"

    # Execution wrapped in atomic ClipboardGuard to ensure host desktop clipboard safety
    with ClipboardGuard(lock_timeout=20.0):
        if chosen_engine in ("auto", "api"):
            api_res = execute_ai_studio_query(
                prompt=prompt_content,
                task=args.task,
                explicit_model=args.model,
                explicit_thinking=args.thinking,
                timeout=args.timeout,
                max_wait_seconds=args.timeout,
            )
            if api_res["ok"]:
                result_text = api_res["output"]
            elif chosen_engine == "auto":
                print(f"⚠️ [AI Studio Engine] 失敗 ({api_res.get('error')})，自動平滑切換至 Web CDP 引擎...", file=sys.stderr)
                result_text = run_web_flow(args, prompt_content)
            else:
                print(f"❌ [AI Studio Engine] 執行失敗: {api_res.get('error')}", file=sys.stderr)
                sys.exit(1)
        else:
            result_text = run_web_flow(args, prompt_content)

    # Clean code fences if writing directly to code files
    if args.output:
        final_output = strip_code_fences_if_needed(result_text, args.output) if args.task == "code" else result_text
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(final_output)
        print(f"💾 結果已儲存至: {out_path}", file=sys.stderr)

    print(result_text)


if __name__ == "__main__":
    main()
