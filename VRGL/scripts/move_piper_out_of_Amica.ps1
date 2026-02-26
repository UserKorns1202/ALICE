# Move Amica\piper out to repo root `piper` directory.
# Usage: Run from repo root in PowerShell as Administrator/user with file permissions.

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Repository root is parent of the scripts directory
$repoRoot = Resolve-Path (Join-Path $scriptDir '..')
Set-Location $repoRoot

$src = Join-Path $repoRoot 'Amica\piper'
$dst = Join-Path $repoRoot 'piper'

if (-not (Test-Path $src)) {
    Write-Host "Source folder not found: $src" -ForegroundColor Yellow
    exit 1
}

if (Test-Path $dst) {
    Write-Host "Destination folder already exists: $dst" -ForegroundColor Yellow
    Write-Host "Attempting to merge contents. If you want a fresh move, remove or rename $dst first." -ForegroundColor Yellow
}

try {
    Write-Host "Moving $src -> $dst"
    Move-Item -LiteralPath $src -Destination $dst -Force
    Write-Host "Move completed." -ForegroundColor Green
} catch {
    Write-Host "Move failed: $_" -ForegroundColor Red
    exit 2
}

Write-Host "Tip: run scripts\archive_Amica.ps1 to move the remaining Amica folder to archive." -ForegroundColor Cyan
