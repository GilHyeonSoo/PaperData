@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set MPLBACKEND=Agg

if exist ".venv\Scripts\activate.bat" (
  call .venv\Scripts\activate.bat
)

python scripts/analyze_wallclock_v2.py ^
  --output-root outputs/scenarios_wallclock_48h ^
  --figures-dir figures/wallclock_48h ^
  --figure-prefix 48h ^
  --summary-name wallclock_48h_results_summary.md

echo.
echo [done] 48h output analysis completed.
pause
