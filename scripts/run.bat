@echo off
REM ==============================================================================
REM run.bat - Windows Antigravity Gemini Web Copilot 執行封裝腳本
REM ==============================================================================

setlocal

set "SCRIPT_DIR=%~dp0"
set "ENV_DIR=%USERPROFILE%\.gemini\gemini_copilot_env"
set "PYTHON_BIN=%ENV_DIR%\Scripts\python.exe"

REM 若專屬虛擬環境未就緒，先建立並安裝依賴
if not exist "%PYTHON_BIN%" (
    echo 📦 正在 Windows 上初始化 Python 虛擬環境: %ENV_DIR%...
    python -m venv "%ENV_DIR%"
    "%ENV_DIR%\Scripts\pip.exe" install playwright pyperclip
)

REM 執行 Python 主調度程式
"%PYTHON_BIN%" "%SCRIPT_DIR%gemini_copilot.py" %*
