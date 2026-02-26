# Start Piper server helper for Windows
# Run this from PowerShell. It will install npm deps, attempt to run the voice installer
# if no models are found, and launch the piper server in a new cmd window.

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

Write-Host "Starting Piper helper in $here"

# Check for node
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "node is not installed or not on PATH. Install Node.js (16+) and retry."
    exit 1
}

# Install npm deps
Write-Host "Installing npm dependencies..."
if (Test-Path "package-lock.json") {
    npm ci
} else {
    npm install
}

# Check models folder for .onnx files
$modelsPath = Join-Path $here 'models'
$onnxCount = 0
if (Test-Path $modelsPath) {
    $onnxCount = (Get-ChildItem -Path $modelsPath -Filter '*.onnx' -File -Recurse -ErrorAction SilentlyContinue | Measure-Object).Count
} else {
    New-Item -ItemType Directory -Path $modelsPath | Out-Null
}

if ($onnxCount -eq 0) {
    Write-Host "No .onnx voice models found in $modelsPath." -ForegroundColor Yellow
    Write-Host "Attempting to run voice-installer.bat to download a default voice. This may require Chocolatey and admin privileges."
    $bat = Join-Path $here 'voice-installer.bat'
    if (Test-Path $bat) {
        Write-Host "Running voice-installer.bat..."
        # Run in cmd so it can call choco/powershell scripts; wait for completion
        # Use ArgumentList as separate parameters to avoid PowerShell parsing issues on older shells
        $proc = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', $bat -NoNewWindow -Wait -PassThru
        if ($proc.ExitCode -ne 0) {
            Write-Warning "voice-installer.bat returned exit code $($proc.ExitCode). You may need to run it manually as Administrator."
            Write-Host "You can also manually download ONNX models into the 'models' folder."
        }
    } else {
        Write-Warning "voice-installer.bat not found. Please download a Piper voice ONNX model and place it in the 'models' folder."
    }
} else {
    Write-Host "Found $onnxCount ONNX model(s) in models/."
}

Write-Host "Launching piper server (npm start) in a new window..."
# Pass arguments separately to avoid the '&&' parsing issue in older PowerShell versions
Start-Process -FilePath 'cmd.exe' -ArgumentList '/k', "cd /d `"$here`" && npm start"
Write-Host "Done. A new terminal window should show the piper server logs."