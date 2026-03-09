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

function Test-Port {
    param($ComputerName, $Port)
    try {
        $connection = Test-NetConnection -ComputerName $ComputerName -Port $Port -ErrorAction Stop
        return $connection.TcpTestSucceeded
    } catch {
        return $false
    }
}

# ---------- Configuration (adjust if needed) ----------
$AMICA_CANDIDATES = @()

$cand1 = Join-Path $PSScriptRoot 'Amica-temp'
if(Test-Path $cand1){ $r = Resolve-Path $cand1 -ErrorAction SilentlyContinue; if($r) { $AMICA_CANDIDATES += $r.Path } }

$cand2 = Join-Path $PSScriptRoot 'amica-tts'
if(Test-Path $cand2){ $r = Resolve-Path $cand2 -ErrorAction SilentlyContinue; if($r) { $AMICA_CANDIDATES += $r.Path } }

$PIPER_DIR = $null
$pdir = Join-Path $PSScriptRoot '..\..\piper'
if(Test-Path $pdir){ $r = Resolve-Path $pdir -ErrorAction SilentlyContinue; if($r) { $PIPER_DIR = $r.Path } }

# Node and Python executables (use PATH by default)
$NODE_EXE = 'node'
# Prefer a known 212-umob venv if present, else use system python
$PYTHON_EXE = 'python'
$UMOB_PY = 'C:\Users\troyk\OneDrive\Desktop\212_Umbral_Observer\212-umob\Scripts\python.exe'
if(Test-Path $UMOB_PY){ $PYTHON_EXE = $UMOB_PY }

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
            # If this folder itself is an amica-tts uvicorn app
            if(Test-Path (Join-Path $cand 'app.py')){ return @{ Path=$cand; Type='uvicorn' } }
            # Fallback: find amica-tts folder (or nested amica-tts)
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
    # Prefer the 212-umob venv, then a local venv inside the Amica folder, else system python
    $venvPython = Join-Path $amicaPath 'venv\Scripts\python.exe'
    if(Test-Path $UMOB_PY){ $pythonToUse = $UMOB_PY }
    elseif(Test-Path $venvPython){ $pythonToUse = $venvPython }
    else { $pythonToUse = $PYTHON_EXE }
    $amicaCommand = "Set-Location -LiteralPath '$amicaPath'; & '$pythonToUse' -m uvicorn app:app --host 127.0.0.1 --port $AMICA_PORT --log-level info"
}

# Piper command
if(-not $PIPER_DIR){ Write-Host 'Piper directory not found; Piper will not be started.'; $piperCommand = $null }
else { $piperCommand = "Set-Location -LiteralPath '$PIPER_DIR'; & '$NODE_EXE' server.js" }

Write-Host "Launching Amica GUI..."
Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoExit','-Command',$amicaCommand) -WindowStyle Normal

Start-Sleep -Milliseconds 250

if($piperCommand){
    if(Test-Port -ComputerName localhost -Port $PIPER_PORT){
        Write-Host "Piper is already running on port $PIPER_PORT; skipping startup."
    } else {
        Write-Host "Launching Piper (TTS) server..."
        Start-Process -FilePath 'powershell.exe' -ArgumentList @('-NoExit','-Command',$piperCommand) -WindowStyle Normal
    }
} else {
    Write-Host "Piper command not available; skipping Piper startup."
}
Write-Host 'Done. Check the newly opened PowerShell windows for output.'
