#!/usr/bin/env bash
# ==============================================================================
# start_chrome_debug.sh
# 100% 徹底分離 (Fully Detached / Daemonized) 的 Chrome CDP 調試啟動腳本
# 核心機制：start_new_session=True (底層 setsid) + close_fds=True + DEVNULL 脫鉤 + 9333 端口就緒探測
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

echo "🚀 正在透過獨立 Session 守護進程啟動 Google Chrome (端口: ${DEBUG_PORT})..."

# 3. 核心：使用 start_new_session=True (底層 setsid) + close_fds=True 脫離 Agent 的 Process Group
python3 -c '
import sys, subprocess, os

chrome_bin = sys.argv[1]
port = sys.argv[2]
profile = sys.argv[3]
target_url = sys.argv[4]

cmd = [
    chrome_bin,
    f"--remote-debugging-port={port}",
    f"--user-data-dir={profile}",
    "--no-first-run",
    "--no-default-browser-check",
    target_url
]

subprocess.Popen(
    cmd,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    close_fds=True,
    start_new_session=True
)
' "${CHROME_BIN}" "${DEBUG_PORT}" "${PROFILE_DIR}" "${TARGET_URL}"

# 4. 主動輪詢探測 (Readiness Probe)，確認就緒後立即 Exit 0
echo "⏳ 等待 Chrome 調試端口響應..."
MAX_ATTEMPTS=20
for ((i=1; i<=MAX_ATTEMPTS; i++)); do
    if curl -s -f --max-time 1 "${CDP_URL}" >/dev/null 2>&1; then
        echo "✅ Chrome 調試端口 (${DEBUG_PORT}) 已成功啟動並就緒！"
        exit 0
    fi
    sleep 0.3
done

echo "⚠️ 等待 Chrome 調試端口 (${DEBUG_PORT}) 逾時。" >&2
exit 1
