#!/usr/bin/env bash
# ==============================================================================
# install.sh - Gemini Web Copilot 一鍵跨電腦安裝腳本
# 支援單行安裝：curl -fsSL https://raw.githubusercontent.com/workingharry/gemini-web-copilot/main/install.sh | bash
# ==============================================================================

set -euo pipefail

REPO_URL="https://github.com/workingharry/gemini-web-copilot.git"
TARGET_DIR="${HOME}/.gemini/config/skills/gemini-web-copilot"

echo "===================================================="
echo "   🚀 正在安裝 Gemini Web Copilot for Antigravity   "
echo "===================================================="

# 1. 確保全域技能目錄存在
mkdir -p "${HOME}/.gemini/config/skills"

# 2. 判斷是從現有目錄執行，還是透過 curl 下載
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" >/dev/null 2>&1 && pwd || echo "")"

if [[ -d "${SCRIPT_DIR}/scripts" && "${SCRIPT_DIR}" != "${TARGET_DIR}" ]]; then
  echo "📦 正在從本地來源同步至全域技能目錄: ${TARGET_DIR}..."
  mkdir -p "${TARGET_DIR}"
  cp -R "${SCRIPT_DIR}"/* "${TARGET_DIR}/"
else
  echo "🌐 正在從 GitHub 下載最新版本至: ${TARGET_DIR}..."
  if [[ -d "${TARGET_DIR}/.git" ]]; then
    echo "🔄 偵測到既有倉庫，正在更新 (git pull)..."
    git -C "${TARGET_DIR}" pull --rebase
  else
    rm -rf "${TARGET_DIR}"
    git clone "${REPO_URL}" "${TARGET_DIR}"
  fi
fi

# 3. 設定執行權限
echo "🔑 配置腳本執行權限..."
chmod +x "${TARGET_DIR}"/scripts/*.sh "${TARGET_DIR}"/scripts/*.py

# 4. 初始化 Python 虛擬環境與安裝依賴
echo "🐍 正在設置專屬 Python 虛擬環境與依賴 (Playwright + pyperclip)..."
bash "${TARGET_DIR}/scripts/setup_env.sh"

echo ""
echo "===================================================="
echo "   🎉 安裝完成！Gemini Web Copilot 已成功就緒        "
echo "===================================================="
echo ""
echo "💡 首次在新電腦使用說明："
echo "1. 執行以下指令啟動專屬 Chrome 實例："
echo "   bash ~/.gemini/config/skills/gemini-web-copilot/scripts/run.sh --launch-only"
echo "2. 在彈出的 Chrome 視窗中登入您的 Google / Gemini 帳號（只需登入一次，永久復用）。"
echo "3. 之後在 Antigravity 中即可隨時使用 /gemini-web-copilot 或呼叫 gemini-web-agent！"
echo ""
