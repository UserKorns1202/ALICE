@echo off
REM Start VRGL: ensure dependencies then run.
python scripts\ensure_and_run_vrgl.py --run
if %ERRORLEVEL% neq 0 (
  echo VRGL failed to start. See installer output above.
  pause
)