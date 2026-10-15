#!/usr/bin/env python3
"""
debug_gemini_skill.py
Gemini Web Copilot Skill 系統診斷與連線偵錯工具
執行方式：~/.gemini/gemini_copilot_env/bin/python scripts/debug_gemini_skill.py
"""

import sys
import time
import urllib.request
import json

DEBUG_PORT = 9333
CDP_URL = f"http://127.0.0.1:{DEBUG_PORT}"

print("====================================================")
print("   Gemini Web Copilot 系統診斷與連線偵錯工具       ")
print("====================================================")

# 1. 檢查調試端口
print(f"\n[1/4] 測試 Chrome 調試端口 ({DEBUG_PORT})...")
try:
    req = urllib.request.Request(f"{CDP_URL}/json/version", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=2) as resp:
        if resp.status == 200:
            info = json.loads(resp.read().decode("utf-8"))
            print(f"  ✅ 端口正常連線！")
            print(f"     瀏覽器版本: {info.get('Browser')}")
            print(f"     WebSocket:  {info.get('webSocketDebuggerUrl')}")
        else:
            print(f"  ❌ 端口響應非 200: {resp.status}")
except Exception as e:
    print(f"  ❌ 無法連線至端口 {DEBUG_PORT}: {e}")
    print("     請先執行: bash ~/.gemini/config/skills/gemini-web-copilot/scripts/start_chrome_debug.sh")

# 2. 測試 Playwright 與現有標籤頁
print("\n[2/4] 檢查開啟的標籤頁與 Gemini 狀態...")
try:
    from playwright.sync_api import sync_playwright
    import pyperclip

    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0]
        pages = context.pages
        print(f"  ✅ CDP 附加成功！目前共有 {len(pages)} 個開啟的標籤頁：")
        gemini_page = None
        for i, page in enumerate(pages):
            is_gemini = "gemini.google.com" in page.url
            mark = " 🌟 [GEMINI]" if is_gemini else ""
            print(f"     Tab #{i}: {page.title()} | {page.url}{mark}")
            if is_gemini and not gemini_page:
                gemini_page = page

        # 3. 檢查輸入框與節點狀態
        print("\n[3/4] 檢查 Gemini DOM 輸入框與按鈕狀態...")
        if gemini_page:
            gemini_page.bring_to_front()
            time.sleep(0.5)
            
            # 檢查使用者帳戶資訊
            avatar = gemini_page.query_selector("img[alt*='Google 帳戶'], img[alt*='Google Account'], a[aria-label*='Google 帳戶'], button[aria-label*='Google 帳戶']")
            sign_in = gemini_page.query_selector("button:has-text('Sign in'), button:has-text('登入')")
            
            if avatar:
                account_info = avatar.get_attribute("aria-label") or avatar.get_attribute("alt") or "已登入"
                print(f"     🎉 偵測到已登入 Google 帳號: {account_info.strip()}")
            elif sign_in and sign_in.is_visible():
                print("     ⚠️ 注意：頁面顯示『登入』按鈕，建議於 Chrome 中完成 Google 登入以獲取完整權限。")
            else:
                print("     ✅ 帳號登入狀態正常。")

            inputs = gemini_page.query_selector_all("rich-textarea div[contenteditable='true'], div.ql-editor, div[role='textbox']")
            print(f"     發現可用輸入框節點數: {len(inputs)}")
        else:
            print("     ℹ️ 目前未發現 Gemini 標籤頁，執行任務時會自動開啟。")

        # 4. 測試系統剪貼簿讀寫
        print("\n[4/4] 測試剪貼簿讀寫能力 (無損提取核心)...")
        test_payload = f"__gemini_copilot_debug_{int(time.time())}__"
        pyperclip.copy(test_payload)
        read_back = pyperclip.paste()
        if read_back == test_payload:
            print("  ✅ 剪貼簿讀寫正常！原生 Copy 按鈕提取已就緒。")
        else:
            print(f"  ⚠️ 剪貼簿讀寫異常，讀取值不一致: {read_back}")

except Exception as e:
    print(f"  ❌ 診斷過程發生例外: {e}")

print("\n====================================================")
print("✨ 診斷完成！")
print("====================================================")
