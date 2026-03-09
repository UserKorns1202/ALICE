$PSScriptRoot = Split-Path -LiteralPath $MyInvocation.MyCommand.Definition -Parent
Write-Host "PSScriptRoot: $PSScriptRoot"
$AMICA_CANDIDATES = @()
$cand1 = Join-Path $PSScriptRoot 'Amica-temp'
if(Test-Path $cand1){ $r = Resolve-Path $cand1 -ErrorAction SilentlyContinue; if($r) { $AMICA_CANDIDATES += $r.Path } }
$cand2 = Join-Path $PSScriptRoot 'amica-tts'
if(Test-Path $cand2){ $r = Resolve-Path $cand2 -ErrorAction SilentlyContinue; if($r) { $AMICA_CANDIDATES += $r.Path } }
Write-Host "Candidates found:"
$AMICA_CANDIDATES | ForEach-Object { Write-Host " - $_" }
function Find-AmicaProject {
    param($candidates)
    foreach($cand in $candidates){
        Write-Host "Checking: $cand"
        if(-not $cand) { continue }
        if(Test-Path $cand){
            Write-Host "  Exists"
            if(Test-Path (Join-Path $cand 'package.json')){ Write-Host "  has package.json" }
            else { Write-Host "  no package.json" }
            if(Test-Path (Join-Path $cand 'app.py')){ Write-Host "  has app.py" }
            else { Write-Host "  no app.py" }
            if(Test-Path (Join-Path $cand 'amica-tts')){ Write-Host "  has nested amica-tts" }
            else { Write-Host "  no nested amica-tts" }
        }
    }
}
Find-AmicaProject -candidates $AMICA_CANDIDATES
