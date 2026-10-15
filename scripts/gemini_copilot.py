#!/usr/bin/env python3
"""
gemini_copilot.py
Antigravity Skill Bridge for Google Gemini Web (gemini.google.com)
支援跨平台：macOS、Windows、Linux (含 WSL)
透過瀏覽器自動化驅動 Gemini 網頁版進行代碼撰寫與規劃，並提取原生 Markdown。
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

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
except ImportError:
    print("❌ 缺少 playwright 依賴，請先執行 setup_env.sh (或 setup_env.bat)！", file=sys.stderr)
    sys.exit(1)

try:
    import pyperclip
except ImportError:
    pyperclip = None

DEBUG_PORT = 9333
CDP_URL = f"http://127.0.0.1:{DEBUG_PORT}"
PROFILE_DIR = os.path.expanduser("~/.gemini/chrome_profile")
CURRENT_OS = platform.system()


def find_chrome_executable() -> str:
    """跨平台智慧尋找 Google Chrome 可執行檔路徑"""
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
    else:  # Linux & WSL
        for binary in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
            p = shutil.which(binary)
            if p:
                return p
    raise FileNotFoundError(f"無法在當前系統 ({CURRENT_OS}) 上找到 Google Chrome 執行檔，請確認已安裝 Chrome。")


def is_cdp_ready():
    """檢查 Chrome 調試端口是否響應 (HTTP 200)"""
    try:
        req = urllib.request.Request(f"{CDP_URL}/json/version", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False


def ensure_chrome_running():
    """若 Chrome 端口未啟動，自動透過獨立 profile 與脫鉤守護進程啟動"""
    if is_cdp_ready():
        return True

    print(f"🚀 未偵測到 {DEBUG_PORT} 端口，自動啟動 Chrome (帶獨立 profile)...", file=sys.stderr)
    os.makedirs(PROFILE_DIR, exist_ok=True)
    
    script_dir = Path(__file__).resolve().parent
    chrome_bin = find_chrome_executable()

    cmd = [
        chrome_bin,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={PROFILE_DIR}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://gemini.google.com/app"
    ]

    # 跨平台守護進程分離 (完全避免 Agent 孤兒任務殘留)
    if CURRENT_OS == "Windows":
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        )
    else:
        # macOS & Linux: 呼叫 setsid 與關閉檔案描述符
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True
        )

    # 主動等待端口就緒 (最多等待 10 秒)
    for _ in range(25):
        if is_cdp_ready():
            return True
        time.sleep(0.4)

    return is_cdp_ready()


def find_or_open_gemini_page(context):
    """在現有頁面中尋找 Gemini 對話標籤頁，若無則開啟新分頁或導航至 /app"""
    for page in context.pages:
        if "gemini.google.com/app" in page.url:
            print(f"🔗 發現已存在的 Gemini 對話標籤頁: {page.url}", file=sys.stderr)
            page.bring_to_front()
            return page

    # 若有其他 gemini 頁面（例如 /usage 或 /settings），直接導航至 /app
    for page in context.pages:
        if "gemini.google.com" in page.url:
            print(f"🌐 導航現有 Gemini 標籤頁至對話主頁...", file=sys.stderr)
            page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
            page.bring_to_front()
            return page

    print("🌐 開啟新的 Gemini 標籤頁...", file=sys.stderr)
    page = context.new_page()
    page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
    return page


def locate_input_box(page):
    """定位 Gemini 網頁版輸入框"""
    selectors = [
        "rich-textarea div[contenteditable='true']",
        "div.ql-editor[contenteditable='true']",
        "div[role='textbox']",
        "textarea[placeholder*='Prompt']",
        "div[contenteditable='true']",
    ]
    for sel in selectors:
        try:
            elem = page.wait_for_selector(sel, state="visible", timeout=3000)
            if elem:
                return elem, sel
        except PlaywrightTimeoutError:
            continue
    raise RuntimeError("無法定位 Gemini 輸入框，請確認網頁是否正常加載或是否已登入 Google 帳號。")


def send_prompt(page, prompt_text, file_path=None):
    """
    將 Prompt 注入輸入框並提交。
    若 context 過長或有附件，優先以檔案上傳或剪貼簿貼上注入，避免 DOM 渲染卡死。
    """
    input_elem, sel = locate_input_box(page)
    input_elem.click()

    # 處理大檔案上傳（盲點四修正）
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
            print("ℹ️ 未能直接透過 file input 上傳，改將檔案內容合併至 Prompt...", file=sys.stderr)
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            prompt_text = f"{prompt_text}\n\n```\n{content}\n```"

    # 若 Prompt 文字過大，透過剪貼簿貼上避免大量按鍵事件引發瀏覽器延遲
    if len(prompt_text) > 500:
        print(f"📋 Prompt 字數較長 ({len(prompt_text)} 字)，使用剪貼簿注入...", file=sys.stderr)
        try:
            # 複製到系統剪貼簿
            if pyperclip:
                pyperclip.copy(prompt_text)
            elif CURRENT_OS == "Darwin":
                p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                p.communicate(prompt_text.encode("utf-8"))
            elif CURRENT_OS == "Windows":
                p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
                p.communicate(prompt_text.encode("utf-8"))
            
            # 在輸入框中執行貼上 (macOS: Meta+V, Windows/Linux: Control+V)
            paste_key = "Meta+V" if CURRENT_OS == "Darwin" else "Control+V"
            page.keyboard.press(paste_key)
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ 剪貼簿注入失敗，改以模擬輸入: {e}", file=sys.stderr)
            page.keyboard.insert_text(prompt_text)
    else:
        page.keyboard.insert_text(prompt_text)

    time.sleep(0.5)

    # 點擊送出按鈕或按 Enter
    send_selectors = [
        "button[aria-label*='Send']",
        "button[aria-label*='傳送']",
        "button[aria-label*='發送']",
        "button.send-button",
        "button[data-test-id='send-button']"
    ]
    sent = False
    for s_sel in send_selectors:
        btn = page.query_selector(s_sel)
        if btn and btn.is_visible() and btn.is_enabled():
            btn.click()
            sent = True
            print("🚀 已點擊送出按鈕！", file=sys.stderr)
            break

    if not sent:
        print("⌨️ 未找到啟用狀態的送出按鈕，嘗試按 Enter 送出...", file=sys.stderr)
        page.keyboard.press("Enter")


def wait_for_generation_complete(page, timeout_sec=300):
    """
    盲點二修正：
    嚴禁依賴 Send 按鈕狀態。改為監聽：
    1. Stop（停止生成）按鈕短暫出現，然後消失（detached/hidden）。
    2. 最新一則回覆底部的 Action bar（Copy 複製按鈕）出現並穩定。
    """
    print("⏳ 等待 Gemini 生成回應中...", file=sys.stderr)

    stop_selectors = [
        "button[aria-label*='Stop']",
        "button[aria-label*='停止']",
        "button[data-test-id='stop-button']",
        "mat-icon:has-text('stop')",
    ]

    # 等待生成開始（最多等 8 秒）
    start_time = time.time()
    seen_stop = False
    while time.time() - start_time < 8:
        for s_sel in stop_selectors:
            elem = page.query_selector(s_sel)
            if elem and elem.is_visible():
                seen_stop = True
                break
        if seen_stop:
            print("⚡ 偵測到正在生成中 (Stop 按鈕已出現)...", file=sys.stderr)
            break
        time.sleep(0.5)

    # 若出現了 Stop 按鈕，等待它消失
    if seen_stop:
        for s_sel in stop_selectors:
            try:
                page.wait_for_selector(s_sel, state="hidden", timeout=timeout_sec * 1000)
            except Exception:
                pass

    # 等待回覆容器與複製按鈕出現（代表生成完畢）
    copy_selectors = [
        "button[aria-label*='Copy']",
        "button[aria-label*='複製']",
        "button[data-test-id='copy-button']",
        "share-button ~ button",
    ]

    end_time = time.time() + timeout_sec
    while time.time() < end_time:
        for c_sel in copy_selectors:
            copies = page.query_selector_all(c_sel)
            if copies and len(copies) > 0 and copies[-1].is_visible():
                # 再次確認沒有任何 stop 按鈕在動
                is_still_generating = any(
                    page.query_selector(s) and page.query_selector(s).is_visible()
                    for s in stop_selectors
                )
                if not is_still_generating:
                    time.sleep(1)  # 留 1 秒讓 DOM 與動畫徹底穩定
                    print("✅ 生成完畢！(偵測到 Action bar 與 Copy 按鈕)", file=sys.stderr)
                    return True
        time.sleep(1)

    print("⚠️ 等待超時，嘗試強制提取內容...", file=sys.stderr)
    return False


def extract_response_markdown(page):
    """
    盲點三修正：
    優先點擊最新回覆底部的原生「複製（Copy）」按鈕，直接從系統剪貼簿獲取最純淨的原生 Markdown。
    以 DOM 解析作為 Fallback。
    """
    print("📋 正在提取 Gemini 回應...", file=sys.stderr)

    # 優先篩選訊息層級的完整複製按鈕（排除「複製代碼」或「複製提示詞」）
    message_copy_selectors = [
        "button[aria-label='Copy']",
        "button[aria-label='複製']",
        "button[data-test-id='copy-button']"
    ]
    
    # 清空剪貼簿
    try:
        if pyperclip:
            pyperclip.copy("")
        elif CURRENT_OS == "Darwin":
            subprocess.run(["pbcopy"], input=b"", check=False)
    except Exception:
        pass

    # 點擊最後一個（最新回覆的）訊息複製按鈕
    for c_sel in message_copy_selectors:
        buttons = page.query_selector_all(c_sel)
        valid_buttons = [
            b for b in buttons 
            if "代碼" not in (b.get_attribute("aria-label") or "") 
            and "code" not in (b.get_attribute("aria-label") or "").lower()
            and "提示詞" not in (b.get_attribute("aria-label") or "")
            and "prompt" not in (b.get_attribute("aria-label") or "").lower()
        ]
        if valid_buttons:
            latest_copy_btn = valid_buttons[-1]
            try:
                latest_copy_btn.scroll_into_view_if_needed()
                latest_copy_btn.click()
                time.sleep(1.0)

                # 從剪貼簿讀取
                copied_text = ""
                if pyperclip:
                    copied_text = pyperclip.paste()
                elif CURRENT_OS == "Darwin":
                    p = subprocess.Popen(["pbpaste"], stdout=subprocess.PIPE)
                    copied_text = p.communicate()[0].decode("utf-8", errors="ignore")
                elif CURRENT_OS == "Windows":
                    p = subprocess.Popen(["powershell", "-NoProfile", "Get-Clipboard"], stdout=subprocess.PIPE)
                    copied_text = p.communicate()[0].decode("utf-8", errors="ignore")

                if copied_text and len(copied_text.strip()) > 0:
                    print(f"✨ 成功透過原生 Copy 按鈕獲取純淨 Markdown ({len(copied_text)} 字元)！", file=sys.stderr)
                    return copied_text
            except Exception as e:
                print(f"⚠️ 點擊複製按鈕讀取剪貼簿失敗: {e}", file=sys.stderr)
                break

    # Fallback: 從 DOM 節點提取
    print("ℹ️ 啟用 DOM 文本提取 Fallback...", file=sys.stderr)
    dom_selectors = [
        "message-content",
        "model-response",
        ".response-container",
        "div[data-test-id='model-response']",
        ".markdown"
    ]
    for d_sel in dom_selectors:
        elems = page.query_selector_all(d_sel)
        if elems:
            text = elems[-1].inner_text()
            if text and len(text.strip()) > 0:
                return text

    return "⚠️ 未能獲取到回應內容，請檢查瀏覽器視窗中的 Gemini 對話。"


def main():
    parser = argparse.ArgumentParser(description="Antigravity Gemini Web Copilot Bridge (Cross-Platform)")
    parser.add_argument("--prompt", "-p", help="發送給 Gemini 的文字提示詞")
    parser.add_argument("--prompt-file", help="從指定的檔案讀取提示詞")
    parser.add_argument("--context-file", "-f", help="附加的程式碼或設計 Context 檔案路徑")
    parser.add_argument("--output", "-o", help="將生成的 Markdown/代碼寫入指定檔案")
    parser.add_argument("--timeout", type=int, default=300, help="等待生成完成的最長秒數 (預設: 300)")
    parser.add_argument("--launch-only", action="store_true", help="僅啟動並連接 Chrome，不發送 Prompt")
    args = parser.parse_args()

    # 確保 Chrome 已啟動
    if not ensure_chrome_running():
        print(f"❌ 無法連接至 Chrome 調試端口 ({DEBUG_PORT})！", file=sys.stderr)
        sys.exit(1)

    prompt_content = ""
    if args.prompt_file and os.path.exists(args.prompt_file):
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            prompt_content = f.read()
    elif args.prompt:
        prompt_content = args.prompt

    with sync_playwright() as p:
        print(f"🔌 連接至 Chrome CDP: {CDP_URL}", file=sys.stderr)
        browser = p.chromium.connect_over_cdp(CDP_URL)
        default_context = browser.contexts[0]
        
        # 賦予剪貼簿讀寫權限
        try:
            default_context.grant_permissions(["clipboard-read", "clipboard-write"])
        except Exception:
            pass

        page = find_or_open_gemini_page(default_context)

        if args.launch_only:
            print("✅ Chrome 與 Gemini 網頁版已就緒！", file=sys.stderr)
            return

        if not prompt_content:
            print("❌ 請提供 --prompt 或 --prompt-file！", file=sys.stderr)
            sys.exit(1)

        # 送出 Prompt
        send_prompt(page, prompt_content, file_path=args.context_file)

        # 等待生成完畢
        wait_for_generation_complete(page, timeout_sec=args.timeout)

        # 提取結果
        result = extract_response_markdown(page)

        # 儲存或輸出
        if args.output:
            out_path = Path(args.output).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(result)
            print(f"💾 結果已儲存至: {out_path}", file=sys.stderr)

        # 輸出至 stdout
        print(result)


if __name__ == "__main__":
    main()
