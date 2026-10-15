# ==============================================================================
# install.ps1 - Gemini Web Copilot Windows 一鍵安裝腳本 (PowerShell)
# 支援單行安裝：irm https://raw.githubusercontent.com/workingharry/gemini-web-copilot/main/install.ps1 | iex
# ==============================================================================

$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/workingharry/gemini-web-copilot.git"
$TargetDir = "$env:USERPROFILE\.gemini\config\skills\gemini-web-copilot"
$EnvDir = "$env:USERPROFILE\.gemini\gemini_copilot_env"

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "   🚀 正在 Windows 上安裝 Gemini Web Copilot       " -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# 1. 確保目標資料夾存在
if (-not (Test-Path "$env:USERPROFILE\.gemini\config\skills")) {
    New-Item -ItemType Directory -Path "$env:USERPROFILE\.gemini\config\skills" -Force | Out-Null
}

# 2. 下載或更新倉庫
if (Test-Path "$TargetDir\.git") {
    Write-Host "🔄 偵測到既有倉庫，正在更新 (git pull)..." -ForegroundColor Yellow
    git -C "$TargetDir" pull --rebase
} else {
    Write-Host "🌐 正在下載 Gemini Web Copilot 至: $TargetDir..." -ForegroundColor Yellow
    if (Test-Path "$TargetDir") { Remove-Item -Recurse -Force "$TargetDir" }
    git clone "$RepoUrl" "$TargetDir"
}

# 3. 初始化 Python 虛擬環境
$PythonExe = "$EnvDir\Scripts\python.exe"
if (-not (Test-Path "$PythonExe")) {
    Write-Host "🐍 正在建立專屬 Python 虛擬環境 ($EnvDir)..." -ForegroundColor Yellow
    python -m venv "$EnvDir"
}

Write-Host "⬇️ 安裝必要依賴 (playwright, pyperclip)..." -ForegroundColor Yellow
& "$EnvDir\Scripts\pip.exe" install --upgrade pip | Out-Null
& "$EnvDir\Scripts\pip.exe" install playwright pyperclip

Write-Host ""
Write-Host "====================================================" -ForegroundColor Green
Write-Host "   🎉 Windows 安裝完成！Gemini Web Copilot 已就緒     " -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
Write-Host ""
Write-Host "💡 首次在 Windows 使用說明：" -ForegroundColor White
Write-Host "1. 執行以下指令啟動獨立 Chrome 視窗：" -ForegroundColor Gray
Write-Host "   & '$TargetDir\scripts\run.bat' --launch-only" -ForegroundColor Yellow
Write-Host "2. 在彈出的 Chrome 視窗中登入一次您的 Google / Gemini 帳號。" -ForegroundColor Gray
Write-Host "3. 之後在 Antigravity 中即可隨時使用 /gemini-web-copilot！" -ForegroundColor Gray
Write-Host ""
