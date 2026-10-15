#!/usr/bin/env bash
# ==============================================================================
# setup_env.sh
# 建立專屬 Python 虛擬環境並安裝 Playwright & pyperclip
# ==============================================================================

set -euo pipefail

ENV_DIR="${HOME}/.gemini/gemini_copilot_env"

echo "📦 檢查 / 準備 Python 虛擬環境: ${ENV_DIR}"

if [[ ! -d "$ENV_DIR" ]]; then
  echo "🛠️ 正在建立虛擬環境..."
  python3 -m venv "$ENV_DIR"
fi

PYTHON_BIN="${ENV_DIR}/bin/python"
PIP_BIN="${ENV_DIR}/bin/pip"

echo "⬇️ 檢查並安裝必要依賴 (playwright, pyperclip)..."
"$PIP_BIN" install --upgrade pip >/dev/null 2>&1 || true
"$PIP_BIN" install playwright pyperclip

echo "✅ 環境安裝完成！"
echo "   Python 直譯器: ${PYTHON_BIN}"
