@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
set MPLBACKEND=Agg

if exist ".venv\Scripts\activate.bat" (
  call .venv\Scripts\activate.bat
)

echo [quick] Running a short S1 smoke test...
python -m simulator.run_wallclock_parallel ^
  --config simulator/config/scenarios_v2.yaml ^
  --only S1 ^
  --quick-test ^
  --max-workers 1 ^
  --output-root outputs/scenarios_wallclock_48h_quick ^
  --overwrite ^
  --save-run-details first

if errorlevel 1 (
  echo [error] Quick test failed.
  pause
  exit /b 1
)

python scripts/analyze_wallclock_v2.py ^
  --output-root outputs/scenarios_wallclock_48h_quick ^
  --figures-dir figures/wallclock_48h_quick ^
  --figure-prefix quick ^
  --summary-name wallclock_48h_quick_results_summary.md

echo.
echo [done] Quick test completed.
pause
