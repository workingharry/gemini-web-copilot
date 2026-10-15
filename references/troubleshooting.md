# Gemini Web Copilot 常見問題與排障指南 (Troubleshooting)

---

## 1. Chrome 9333 調試端口問題

### 問題 1：Chrome 提示 "Remote debugging is forbidden on default user data dir"
- **原因**：Chrome v136+ 出於安全防護，嚴格禁止在預設用戶個人設定目錄直接啟用 `--remote-debugging-port`。
- **解法**：`start_chrome_debug.sh` 已強制指定獨立目錄 `--user-data-dir="$HOME/.gemini/chrome_profile"`。

### 問題 2：終端已執行啟動命令，但 9333 端口未監聽
- **原因**：在 macOS 上，若 Chrome 已經常駐在背景執行，使用 `open -a` 或不帶獨立 `--user-data-dir` 呼叫 Chrome，只會聚焦到既有視窗，而不會應用新的啟動參數。
- **解法**：必須使用帶 `--user-data-dir` 的啟動腳本 `./scripts/start_chrome_debug.sh`，這會以獨立實例執行。

---

## 2. Google 登入與風控（Bot Detection）

### 問題：遇到 "Couldn't sign you in. This browser or app may not be secure"
- **原因**：若使用純自動化無頭 Chromium（如自動下載的 Playwright 原生瀏覽器），Google 很容易識別出自動化特徵並封鎖登入。
- **解法**：
  1. 使用 `./scripts/start_chrome_debug.sh` 啟動本機真實安裝的 Google Chrome。
  2. 在跳出的視窗中完成 Google 帳號手動登入（包括 2FA 雙重驗證）。
  3. 一旦登入成功，Cookies 與 Session 將永久儲存在 `~/.gemini/chrome_profile` 中，後續自動化運行完全免再次登入。

---

## 3. 剪貼簿存取問題

### 問題：腳本無法讀取剪貼簿內容
- **解法**：
  - 在 macOS 上，腳本支援 Playwright 原生 `grant_permissions(['clipboard-read', 'clipboard-write'])`。
  - 同時內建 `pyperclip` 與系統級 `pbpaste` 雙重保險。
  - 若系統提示授予終端機或 Python 輔助使用或剪貼簿權限，請點擊允許。
