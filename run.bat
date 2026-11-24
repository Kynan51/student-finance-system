@echo off
REM ============================================================
REM  Student Finance - one-click start for Windows
REM  Double-click this file, or run it from Command Prompt.
REM ============================================================
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo Python was not found. Install Python 3.11 or newer from https://www.python.org/downloads/
  echo and tick "Add python.exe to PATH" during installation, then run this file again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/5] Creating virtual environment...
  python -m venv .venv || goto :error
)

echo [2/5] Installing requirements (first run takes a few minutes)...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt -q || goto :error

if not exist ".env" (
  echo Creating .env from .env.example ...
  copy ".env.example" ".env" >nul
)

echo [3/5] Applying database migrations...
".venv\Scripts\python.exe" manage.py migrate --noinput || goto :error

echo [4/5] Creating demo account with synthetic data (skipped if it exists)...
".venv\Scripts\python.exe" manage.py seed_demo --keep || goto :error

echo.
echo [5/5] Starting server...
echo ------------------------------------------------------------
echo   Open:  http://127.0.0.1:8000
echo   Demo:  username demo   password DemoPass2026!
echo   Stop:  press CTRL+C in this window
echo ------------------------------------------------------------
start "" http://127.0.0.1:8000
".venv\Scripts\python.exe" manage.py runserver 127.0.0.1:8000
goto :eof

:error
echo.
echo Something went wrong. Read the message above, then see README.md (Troubleshooting).
pause
exit /b 1
