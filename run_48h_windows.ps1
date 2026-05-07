$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$env:PYTHONUTF8 = "1"
$env:MPLBACKEND = "Agg"

if (Test-Path ".venv\Scripts\Activate.ps1") {
    . ".venv\Scripts\Activate.ps1"
}

Write-Host "[48h] Starting S1-S6 wall-clock simulation."
Write-Host "[48h] Output: outputs\scenarios_wallclock_48h"
Write-Host "[48h] This run uses --resume, so restarting this script will continue from saved summaries."

python -m simulator.run_wallclock_parallel `
    --config simulator/config/scenarios_v2.yaml `
    --target-seconds 172800 `
    --max-workers 6 `
    --output-root outputs/scenarios_wallclock_48h `
    --resume `
    --save-run-details first

python scripts/analyze_wallclock_v2.py `
    --output-root outputs/scenarios_wallclock_48h `
    --figures-dir figures/wallclock_48h `
    --figure-prefix 48h `
    --summary-name wallclock_48h_results_summary.md

Write-Host "[done] 48h simulation and analysis completed."
