@echo off
REM Batch wrapper to launch the PowerShell script in a new window.
REM This is useful if you want a double-clickable .bat file.

SET SCRIPT_PATH="%~dp0start_amica_piper.ps1"
REM Use PowerShell to run the launcher script in a new window
START "AMICA & Piper Launcher" powershell -NoExit -ExecutionPolicy Bypass -File %SCRIPT_PATH%

REM End of file
