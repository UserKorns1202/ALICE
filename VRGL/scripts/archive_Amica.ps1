# Archive the Amica folder by moving it to `archived/Amica-<timestamp>`.
# Usage: Run from repo root in PowerShell after you've moved Piper out.

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
# Repository root is parent of the scripts directory
$repoRoot = Resolve-Path (Join-Path $scriptDir '..')
Set-Location $repoRoot

$src = Join-Path $repoRoot 'Amica'
if (-not (Test-Path $src)) {
    Write-Host "Amica folder not found: $src" -ForegroundColor Yellow
    exit 1
}

$ts = Get-Date -Format yyyyMMdd_HHmmss
$archiveRoot = Join-Path $repoRoot 'archived'
if (-not (Test-Path $archiveRoot)) { New-Item -ItemType Directory -Path $archiveRoot | Out-Null }
$dst = Join-Path $archiveRoot ("Amica-$ts")

try {
    Write-Host "Archiving $src -> $dst"
    Move-Item -LiteralPath $src -Destination $dst -Force
    Write-Host "Archive completed." -ForegroundColor Green
} catch {
    Write-Host "Archive failed: $_" -ForegroundColor Red
    exit 2
}
