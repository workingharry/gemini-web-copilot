@echo off
REM ==============================================================================
REM start_chrome_debug.bat - Windows Chrome 9333 CDP 調試模式啟動腳本
REM ==============================================================================

setlocal enabledelayedexpansion

set "DEBUG_PORT=9333"
set "PROFILE_DIR=%USERPROFILE%\.gemini\chrome_profile"
set "TARGET_URL=https://gemini.google.com/app"

echo 🔍 正在檢測 Chrome 調試端口 (%DEBUG_PORT%)...
curl -s -f "http://127.0.0.1:%DEBUG_PORT%/json/version" >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ Chrome 調試端口 (%DEBUG_PORT%) 已經在運行中。
    exit /b 0
)

REM 尋找 Windows Chrome 執行檔路徑
set "CHROME_BIN="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_BIN=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
) else if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_BIN=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    set "CHROME_BIN=%LocalAppData%\Google\Chrome\Application\chrome.exe"
)

if "%CHROME_BIN%"=="" (
    echo ❌ 找不到 Google Chrome 執行檔，請確認已安裝 Chrome。
    exit /b 1
)

if not exist "%PROFILE_DIR%" mkdir "%PROFILE_DIR%"

echo 🚀 正在啟動 Google Chrome (端口: %DEBUG_PORT%, 獨立 Profile: %PROFILE_DIR%)...
start "" "%CHROME_BIN%" --remote-debugging-port=%DEBUG_PORT% --user-data-dir="%PROFILE_DIR%" --no-first-run --no-default-browser-check "%TARGET_URL%"

REM 等待端口就緒
echo ⏳ 等待 Chrome 調試端口響應...
for /l %%i in (1,1,20) do (
    curl -s -f "http://127.0.0.1:%DEBUG_PORT%/json/version" >nul 2>&1
    if !errorlevel! equ 0 (
        echo ✅ Chrome 調試端口 (%DEBUG_PORT%) 已成功啟動並就緒！
        exit /b 0
    )
    timeout /t 1 /nobreak >nul
)

echo ⚠️ 等待 Chrome 調試端口超時。
exit /b 1
