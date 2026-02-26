@echo off
REM start_vrgl_bot.bat
REM Usage: start_vrgl_bot.bat [DISCORD_TOKEN] [OLLAMA_URL] [OLLAMA_MODEL]
REM If DISCORD_TOKEN is omitted, you'll be prompted. If OLLAMA settings are omitted, existing env vars are used.
setlocal

REM Accept token as first argument or prompt the user
if "%~1"=="" (
    if defined DISCORD_BOT_TOKEN (
        echo Using existing DISCORD_BOT_TOKEN environment variable
    ) else (
        set /p DISCORD_BOT_TOKEN=Enter Discord bot token: 
    )
) else (
    set DISCORD_BOT_TOKEN=%~1
)

REM Optional Ollama overrides
if not "%~2"=="" set OLLAMA_URL=%~2
if not "%~3"=="" set OLLAMA_MODEL=%~3

REM Ensure we run from the script directory (project root)
cd /d "%~dp0"

REM Try to activate local venvs: venv, .venv, or a common external path
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
    set PYTHON_EXE=%~dp0venv\Scripts\python.exe
) else if exist "%~dp0.venv\Scripts\activate.bat" (
    call "%~dp0.venv\Scripts\activate.bat"
    set PYTHON_EXE=%~dp0.venv\Scripts\python.exe
) else if exist "C:\Users\troyk\OneDrive\Desktop\212_Umbral_Observer\212-umob\Scripts\activate.bat" (
    call "C:\Users\troyk\OneDrive\Desktop\212_Umbral_Observer\212-umob\Scripts\activate.bat"
    set PYTHON_EXE=C:\Users\troyk\OneDrive\Desktop\212_Umbral_Observer\212-umob\Scripts\python.exe
) else (
    echo No virtualenv activate script found in common locations; using system Python
    set PYTHON_EXE=python
)

REM If PYTHON_EXE not set for some reason, fallback to system python
if "%PYTHON_EXE%"=="" set PYTHON_EXE=python

echo Using python: %PYTHON_EXE%

echo Starting VRGL Discord watcher...
echo DISCORD_BOT_TOKEN is set (hidden)

REM Start the bot; this will run until stopped.
"%PYTHON_EXE%" discord_integration.py run

endlocal
