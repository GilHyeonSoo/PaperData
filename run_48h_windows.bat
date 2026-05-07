@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set MPLBACKEND=Agg

if exist ".venv\Scripts\activate.bat" (
  call .venv\Scripts\activate.bat
)

echo [48h] Starting S1-S6 wall-clock simulation.
echo [48h] Output: outputs\scenarios_wallclock_48h
echo [48h] This run uses --resume, so restarting this file will continue from saved summaries.

python -m simulator.run_wallclock_parallel ^
  --config simulator/config/scenarios_v2.yaml ^
  --target-seconds 172800 ^
  --max-workers 6 ^
  --output-root outputs/scenarios_wallclock_48h ^
  --resume ^
  --save-run-details first

if errorlevel 1 (
  echo [error] 48h simulation stopped with an error.
  echo [hint] You can rerun this file to resume from completed run summaries.
  pause
  exit /b 1
)

python scripts/analyze_wallclock_v2.py ^
  --output-root outputs/scenarios_wallclock_48h ^
  --figures-dir figures/wallclock_48h ^
  --figure-prefix 48h ^
  --summary-name wallclock_48h_results_summary.md

echo.
echo [done] 48h simulation and analysis completed.
pause
