#!/usr/bin/env pwsh
Write-Host "Ensuring VRGL dependencies and starting..."
python ./scripts/ensure_and_run_vrgl.py --run
if($LASTEXITCODE -ne 0){
    Write-Host "VRGL failed to start. Check installer output above." -ForegroundColor Red
    pause
}