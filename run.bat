@echo off
REM ──────────────────────────────────────────────────────────
REM Murmur — Windows Launch Script
REM Double-click this file (or run from Command Prompt)
REM ──────────────────────────────────────────────────────────
setlocal

set MURMUR_DIR=%~dp0
set MURMUR_DIR=%MURMUR_DIR:~0,-1%

REM Activate virtual environment
call "%MURMUR_DIR%\.venv\Scripts\activate.bat"

REM Ollama runs as a Windows service — no need to start it manually.
REM If you installed Ollama, it starts automatically with Windows.

echo.
echo   ^ Murmur is starting at http://localhost:8501
echo   Close this window to stop Murmur.
echo.

cd /d "%MURMUR_DIR%"
streamlit run app.py --server.headless false --theme.base dark

pause
