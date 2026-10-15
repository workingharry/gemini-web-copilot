#!/usr/bin/env bash
# ==============================================================================
# start_chrome_debug.sh
# 100% 徹底分離 (Fully Detached / Daemonized) 的 Chrome CDP 調試啟動腳本
# 核心架構：Double-Fork + setsid() + 關閉所有檔案描述符 (FD 0,1,2,3+) + 9333 端口就緒探測
# ==============================================================================

set -euo pipefail

DEBUG_PORT="${1:-9333}"
PROFILE_DIR="${2:-${HOME}/.gemini/chrome_profile}"
CDP_URL="http://127.0.0.1:${DEBUG_PORT}/json/version"
TARGET_URL="https://gemini.google.com/app"

# 1. 冪等檢查：如果 9333 端口已在監聽中，直接退出 (Exit 0)
if curl -s -f --max-time 1 "${CDP_URL}" >/dev/null 2>&1; then
    echo "✅ Chrome 調試端口 (${DEBUG_PORT}) 已經在運行中。"
    exit 0
fi

# 2. 自動尋找 Chrome 執行檔
detect_chrome_bin() {
    local mac_paths=(
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary"
        "/Applications/Chromium.app/Contents/MacOS/Chromium"
    )
    for p in "${mac_paths[@]}"; do
        [[ -x "$p" ]] && { echo "$p"; return 0; }
    done

    # Linux fallback
    local linux_bins=("google-chrome" "google-chrome-stable" "chromium" "chromium-browser")
    for b in "${linux_bins[@]}"; do
        command -v "$b" >/dev/null 2>&1 && { command -v "$b"; return 0; }
    done
    return 1
}

CHROME_BIN="$(detect_chrome_bin || true)"
if [[ -z "${CHROME_BIN}" ]]; then
    echo "❌ 找不到 Google Chrome 執行檔！" >&2
    exit 1
fi

mkdir -p "${PROFILE_DIR}"

CHROME_ARGS=(
    "--remote-debugging-port=${DEBUG_PORT}"
    "--user-data-dir=${PROFILE_DIR}"
    "--no-first-run"
    "--no-default-browser-check"
    "${TARGET_URL}"
)

echo "🚀 正在透過 Double-Fork 與 setsid 守護進程啟動 Google Chrome (端口: ${DEBUG_PORT})..."

# 3. 核心：Double-Fork + setsid() 脫鉤 + 關閉全數 FD，徹底避免 Agent 背景任務掛起 (Orphaned Task)
python3 - "${CHROME_BIN}" "${CHROME_ARGS[@]}" << 'EOF' </dev/null >/dev/null 2>&1
import os
import sys

chrome_bin = sys.argv[1]
chrome_args = sys.argv[1:]

# 第一次 Fork
if os.fork() > 0:
    sys.exit(0)

# 建立獨立 Session 與 Process Group，徹底脫離 Agent 的 PGID 追蹤
os.setsid()

# 第二次 Fork，防止取得 Controlling TTY
if os.fork() > 0:
    sys.exit(0)

# 重導向標準輸入、輸出、錯誤 (FD 0, 1, 2) 至 /dev/null
devnull = os.open(os.devnull, os.O_RDWR)
for fd in (0, 1, 2):
    try:
        os.dup2(devnull, fd)
    except OSError:
        pass
if devnull > 2:
    os.close(devnull)

# 關閉所有殘留的 FD (防止繼承 Agent 建立的匿名狀態管道)
try:
    os.closerange(3, 1024)
except Exception:
    pass

# 執行 Chrome
os.execv(chrome_bin, chrome_args)
EOF

# 4. 主動輪詢探測 (Readiness Probe)，端口就緒後父進程立即 Exit 0 釋放調度器
echo "⏳ 等待 Chrome 調試端口響應..."
MAX_ATTEMPTS=30
for ((i=1; i<=MAX_ATTEMPTS; i++)); do
    if curl -s -f --max-time 1 "${CDP_URL}" >/dev/null 2>&1; then
        echo "✅ Chrome 調試端口 (${DEBUG_PORT}) 已成功啟動並就緒！"
        exit 0
    fi
    sleep 0.3
done

echo "⚠️ 等待 Chrome 調試端口 (${DEBUG_PORT}) 逾時。" >&2
exit 1
