@echo off
REM run_bridge.bat — Create/activate venv, install deps, and start the Amica-ALICE bridge
REM Run this from the repository root (double-click or run from cmd/powershell)

REM If Python is not on PATH, set full path to python.exe here:
SET PY=python






@echo off
REM run_bridge.bat — Create/activate venv, install deps, and start the Amica-ALICE bridge
REM Run this from the repository root (double-click or run from cmd/powershell)

REM If Python is not on PATH, set full path to python.exe here:
SET PY=python

REM Create a virtual environment if it doesn't exist
IF NOT EXIST ".venv\Scripts\activate.bat" (
	ECHO Creating virtual environment .venv...
	%PY% -m venv .venv
)

REM Activate venv
ECHO Activating virtual environment...
call ".venv\Scripts\activate.bat"

REM Upgrade pip and install requirements
ECHO Installing/upgrading pip and required packages (fastapi, uvicorn, httpx)...
%PY% -m pip install --upgrade pip
%PY% -m pip install "fastapi[all]" uvicorn httpx

REM Ensure BRIDGE_API_KEY exists — generate a temporary one if not set
IF "%BRIDGE_API_KEY%"=="" (
	set BRIDGE_API_KEY=%RANDOM%%RANDOM%%RANDOM%
	ECHO Generated BRIDGE_API_KEY=%BRIDGE_API_KEY%
) ELSE (
	ECHO Using existing BRIDGE_API_KEY environment variable.
)

REM Default KEVIN/PIPER URLs if not provided
IF "%KEVIN_URL%"=="" set KEVIN_URL=http://127.0.0.1:5000/query
IF "%PIPER_URL%"=="" set PIPER_URL=http://127.0.0.1:3000

ECHO Starting Amica-ALICE Bridge on http://127.0.0.1:8700 ...
REM Use python -m uvicorn so we don't depend on uvicorn.exe being on PATH
%PY% -m uvicorn amica_alice_bridge:app --host 127.0.0.1 --port 8700 --reload

ECHO Bridge exited. Press any key to close window.
pause >nul