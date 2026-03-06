@echo off
REM ──────────────────────────────────────────────────────────
REM Murmur — Windows Installer
REM Run this once in PowerShell or Command Prompt as your user
REM ──────────────────────────────────────────────────────────
setlocal enabledelayedexpansion

set MURMUR_DIR=%~dp0
set MURMUR_DIR=%MURMUR_DIR:~0,-1%

echo.
echo   ^ Murmur — local voice + AI copilot
echo   Installing on Windows...
echo.

REM ── 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not on PATH.
    echo.
    echo   Please install Python 3.10+ from https://python.org
    echo   Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
echo [OK] Python found

REM ── 2. Check / install Ollama
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [INFO] Ollama is not installed.
    echo   Download it from: https://ollama.com/download/windows
    echo   Install it, then re-run this script.
    echo   ^(Ollama installs as a background service on Windows.^)
    echo.
    set /p CONTINUE="Have you installed Ollama? [y/N]: "
    if /i "!CONTINUE!" neq "y" (
        echo Exiting. Please install Ollama first.
        pause
        exit /b 1
    )
) else (
    echo [OK] Ollama found
)

REM ── 3. Pull Ollama model
echo.
echo Which Ollama model do you want?
echo   1) llama3.2:3b   - fastest, great for most tasks (~2GB)
echo   2) qwen2.5:7b    - more capable, better for clinical notes (~4GB)
echo   3) llama3.1:8b   - strong reasoning (~5GB)
echo   4) Skip          - I'll pull a model manually later
echo.
set /p MODEL_CHOICE="Enter choice [1-4, default=1]: "

if "%MODEL_CHOICE%"=="2" set OLLAMA_MODEL=qwen2.5:7b
if "%MODEL_CHOICE%"=="3" set OLLAMA_MODEL=llama3.1:8b
if "%MODEL_CHOICE%"=="4" set OLLAMA_MODEL=
if "%MODEL_CHOICE%"==""  set OLLAMA_MODEL=llama3.2:3b
if "%MODEL_CHOICE%"=="1" set OLLAMA_MODEL=llama3.2:3b

if defined OLLAMA_MODEL (
    echo.
    echo Pulling model: %OLLAMA_MODEL% — this may take a few minutes...
    ollama pull %OLLAMA_MODEL%
    echo [OK] Model ready: %OLLAMA_MODEL%
)

REM ── 4. Python virtual environment
echo.
echo Setting up Python environment...
python -m venv "%MURMUR_DIR%\.venv"
call "%MURMUR_DIR%\.venv\Scripts\activate.bat"
python -m pip install --upgrade pip --quiet
pip install -r "%MURMUR_DIR%\requirements.txt" --quiet
echo [OK] Python environment ready

REM ── 5. Done
echo.
echo =============================================
echo   Murmur is ready!
echo =============================================
echo.
echo   To launch Murmur, double-click run.bat
echo   or run:  run.bat
echo.
echo   On first run, faster-whisper will download
echo   the Whisper model (~150MB, one-time).
echo.
pause
