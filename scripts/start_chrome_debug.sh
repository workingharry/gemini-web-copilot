#!/usr/bin/env bash
# ==============================================================================
# start_chrome_debug.sh
# 啟動具備遠程調試端口 (CDP: 9333) 的 Google Chrome
# 遵循 Chrome v136+ 安全限制：使用獨立 --user-data-dir
# ==============================================================================

set -euo pipefail

DEBUG_PORT=9333
PROFILE_DIR="${HOME}/.gemini/chrome_profile"
CHROME_APP="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# 1. 檢查 Google Chrome 是否安裝
if [[ ! -f "$CHROME_APP" ]]; then
  echo "❌ 找不到 Google Chrome: $CHROME_APP" >&2
  echo "請確認本機已安裝 Google Chrome 瀏覽器。" >&2
  exit 1
fi

# 2. 檢查 9333 端口是否已經開放 (使用 -f 確保 404/500 被視為未就緒)
if curl -s -f "http://127.0.0.1:${DEBUG_PORT}/json/version" >/dev/null 2>&1; then
  echo "✅ Chrome 遠程調試端口 (${DEBUG_PORT}) 已經在運行中。"
  exit 0
fi

# 3. 確保獨立 Profile 目錄存在
mkdir -p "$PROFILE_DIR"

echo "🚀 正在啟動 Google Chrome (調試模式)..."
echo "   端口: ${DEBUG_PORT}"
echo "   配置檔目錄: ${PROFILE_DIR}"

# 4. 啟動 Chrome
# 關鍵：指定獨立的 --user-data-dir 避免新版 Chrome (v136+) 安全限制
nohup "$CHROME_APP" \
  --remote-debugging-port="${DEBUG_PORT}" \
  --user-data-dir="${PROFILE_DIR}" \
  --no-first-run \
  --no-default-browser-check \
  "https://gemini.google.com/app" >/dev/null 2>&1 &

CHROME_PID=$!
echo "   Chrome 進程 PID: ${CHROME_PID}"

# 5. 等待調試端口就緒
echo "⏳ 等待 Chrome 調試端口響應..."
MAX_ATTEMPTS=20
ATTEMPT=0
READY=false

while [[ $ATTEMPT -lt $MAX_ATTEMPTS ]]; do
  if curl -s -f "http://127.0.0.1:${DEBUG_PORT}/json/version" >/dev/null 2>&1; then
    READY=true
    break
  fi
  sleep 0.5
  ATTEMPT=$((ATTEMPT + 1))
done

if [[ "$READY" == "true" ]]; then
  echo "✅ Chrome 調試端口 (${DEBUG_PORT}) 已成功啟動並就緒！"
  echo "💡 提示：若這是您首次啟動此 Profile，請在彈出的 Chrome 視窗中完成 Google 帳號登入一次，後續將永久復用。"
  exit 0
else
  echo "⚠️ Chrome 已啟動，但調試端口 (${DEBUG_PORT}) 在 10 秒內未響應。" >&2
  echo "請檢查 Chrome 視窗是否正常啟動，或是否有其他程式佔用該端口。" >&2
  exit 1
fi
