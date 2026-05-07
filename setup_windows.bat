@echo off
setlocal
cd /d "%~dp0"

echo [setup] Creating Python virtual environment...
py -3 -m venv .venv
if errorlevel 1 (
  python -m venv .venv
)
if errorlevel 1 (
  echo [error] Failed to create virtual environment. Install Python 3 first.
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements_windows.txt

echo.
echo [done] Windows Python environment is ready.
echo Use run_quick_windows.bat first, then run_48h_windows.bat.
pause
