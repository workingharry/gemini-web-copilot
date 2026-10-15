#!/usr/bin/env bash
# ==============================================================================
# run.sh
# Antigravity Gemini Web Copilot 執行封裝腳本
# 自動檢查環境，並傳遞參數呼叫 gemini_copilot.py
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_DIR="${HOME}/.gemini/gemini_copilot_env"
PYTHON_BIN="${ENV_DIR}/bin/python"

# 1. 檢查虛擬環境是否存在
if [[ ! -f "$PYTHON_BIN" ]]; then
  echo "📦 虛擬環境不存在，正在自動初始化..."
  bash "${SCRIPT_DIR}/setup_env.sh"
fi

# 2. 執行主腳本
exec "$PYTHON_BIN" "${SCRIPT_DIR}/gemini_copilot.py" "$@"
