<#
start_amica_piper.ps1

Simplified launcher: start only the Amica GUI (prefer `npm run dev` in the Amica
project) and the Piper `server.js`. This version avoids referencing unrelated
Python installs and prefers local venv/python when starting amica-tts.

Edit the `$AMICA_CANDIDATES` and `$PIPER_DIR` variables below if your layout
differs. The script launches each service in a new PowerShell window for easy
log visibility.
#>

Set-StrictMode -Version Latest

# ---------- Configuration (adjust if needed) ----------
# This launcher is intended for the portable VRGL package. It will look for a
# local `piper` folder inside the VRGL directory (relative to this script).
$PIPER_DIR = $null
$pdir = Join-Path $PSScriptRoot '..\piper'
if(Test-Path $pdir){ $r = Resolve-Path $pdir -ErrorAction SilentlyContinue; if($r) { $PIPER_DIR = $r.Path } }

# Node and Python executables (use PATH by default)
$NODE_EXE = 'node'
$PYTHON_EXE = 'python'

# Ports (optional overrides via env)
function Get-EnvInt($name, $default){
    $val = [Environment]::GetEnvironmentVariable($name)
    if(-not $val){ return $default }
    $out = 0
    if([int]::TryParse($val, [ref]$out)) { return $out } else { return $default }
}

$AMICA_PORT = Get-EnvInt 'AMICA_PORT' 5002

$PIPER_PORT = Get-EnvInt 'PIPER_PORT' 5001


function Find-AmicaProject {
    param($candidates)
    foreach($cand in $candidates){
        if(-not $cand) { continue }
        if(Test-Path $cand){
            # Prefer folder containing package.json
            if(Test-Path (Join-Path $cand 'package.json')){
                try{
                    $pkg = Get-Content -Raw -LiteralPath (Join-Path $cand 'package.json') | ConvertFrom-Json -ErrorAction SilentlyContinue
                    if($pkg.scripts -and $pkg.scripts.dev){ return @{ Path=$cand; Type='npm' } }
                } catch { }
            }
            # Fallback: find amica-tts folder
            if(Test-Path (Join-Path $cand 'amica-tts')){ return @{ Path=(Join-Path $cand 'amica-tts'); Type='uvicorn' } }
        }
    }
    return $null
}

Write-Host "Locating Amica project..."
$amicaInfo = Find-AmicaProject -candidates $AMICA_CANDIDATES
if(-not $amicaInfo){ Write-Host 'No Amica project found under candidates. Aborting.'; exit 1 }

$amicaPath = $amicaInfo.Path
$amicaType = $amicaInfo.Type
Write-Host "Selected Amica path: $amicaPath (type: $amicaType)"

# Build commands
if($amicaType -eq 'npm'){
    $amicaCommand = "Set-Location -LiteralPath '$amicaPath'; npm run dev"
} else {
    # Prefer python from a local venv if present
    $venvPython = Join-Path $amicaPath 'venv\Scripts\python.exe'
    if(Test-Path $venvPython){ $pythonToUse = $venvPython } else { $pythonToUse = $PYTHON_EXE }
    $amicaCommand = "Set-Location -LiteralPath '$amicaPath'; & '$pythonToUse' -m uvicorn app:app --host 127.0.0.1 --port $AMICA_PORT --log-level info"
}

# Piper command
if(-not $PIPER_DIR){ Write-Host 'Piper directory not found; Piper will not be started.'; $piperCommand = $null }
else { $piperCommand = "Set-Location -LiteralPath '$PIPER_DIR'; & '$NODE_EXE' server.js" }

Write-Host "Launching Amica GUI..."
Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoExit','-Command',$amicaCommand) -WindowStyle Normal

Start-Sleep -Milliseconds 250

if($piperCommand){
    Write-Host "Launching Piper (TTS) server..."
    Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoExit','-Command',$piperCommand) -WindowStyle Normal
} else {
    Write-Host "Piper command not available; skipping Piper startup."
}
Write-Host 'Done. Check the newly opened PowerShell windows for output.'
