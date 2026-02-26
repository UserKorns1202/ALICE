@echo off
setlocal

:: Main script starts here

:: Check if Chocolatey is installed
call :print_header "Checking Chocolatey"
call :check_chocolatey

:: Check for required dependencies
call :print_header "Checking Dependencies"
call :check_and_install node nodejs
call :check_and_install vcredist2015 vcredist2015

:: Check if Piper is already installed
call :print_header "Checking Piper Installation"
call :check_if_installed
if "%ERRORLEVEL%" == "0" (
    call :print_header "Piper is already installed."

    :: Run voice installer script
    call :print_header "Downloading voice from voice-installer.bat"
    call ".\piper\voice-installer.bat"
    call :check_error "Failed to execute voice-installer.bat"

    call :terminate_npm_install
    
    :: Install npm dependencies and start the application
    call :print_header "Installing npm Dependencies and Starting Piper server"
    cd .\piper\ && npm install
    start cmd /k "cd piper && npm start"
    call :check_error "npm failed"
    exit /b 0
    
)

:: Determine the OS and architecture
set "ARCHITECTURE=windows_amd64"

:: Download the release file
call :print_header "Fetching Latest Release"
for /f "tokens=*" %%i in ('powershell -Command "(Invoke-WebRequest -Uri https://github.com/rhasspy/piper/releases/latest -MaximumRedirection 0).Headers.Location"') do set "redirect_url=%%i"
for %%i in ("%redirect_url%") do set "release_tag=%%~nxi"

set "release_file_name=piper_%ARCHITECTURE%.zip"
set "release_file_url=https://github.com/rhasspy/piper/releases/download/%release_tag%/%release_file_name%"

call :print_header "Downloading Piper"
powershell -Command "Invoke-WebRequest -Uri %release_file_url% -OutFile %release_file_name%"
call :check_error "Failed to download %release_file_name%"

:: Extract the zip file
call :print_header "Extracting Piper"
powershell -Command "Expand-Archive -Path %release_file_name% -DestinationPath ."
call :check_error "Failed to extract %release_file_name%"

:: Cleanup
del %release_file_name%

:: Run voice installer script
call :print_header "Downloading voice from voice-installer.bat"
call ".\piper\voice-installer.bat"
call :check_error "Failed to execute voice-installer.bat"

:: Install npm dependencies and start the application
call :print_header "Installing npm Dependencies and Starting Piper server"
cd .\piper\ && npm install && start cmd /k "cd .\piper\ && npm start"

call :terminate_npm_install

call :check_error "npm failed"

:: Function to terminate previous npm install terminals
:terminate_npm_install
for /f "tokens=1,2 delims=," %%i in ('tasklist /FI "IMAGENAME eq node.exe" /FI "WINDOWTITLE eq npm install*" /FO CSV /NH') do (
    echo Terminating Process ID: %%j
    taskkill /PID %%j /F
)
goto :eof

:: Function to print section headers
:print_header
    echo.
    echo ==================== %1 ====================
    echo.
goto :eof

:: Function to check for errors
:check_error
if not "%ERRORLEVEL%" == "0" (
    echo.
    echo Error occurred: %1
    echo.
    pause
)
goto :eof

:: Function to check if a command exists
:check_and_install
where %1 >nul 2>&1
if not "%ERRORLEVEL%" == "0" (
    echo.
    echo %1 not found. Installing...
    goto :install_package %2
) else (
    echo.
    echo %1 is already installed.
)
goto :eof

:: Function to install a package based on the OS
:install_package
if "%OS%" == "Windows_NT" (
    echo.
    echo Installing %2...
    powershell -Command "choco install -y %2"
    call :check_error "Failed to install %2"
) else (
    echo.
    echo Unsupported OS for package installation.
    echo.
    pause 
)
goto :eof

:: Function to check if Chocolatey is installed
:check_chocolatey
where choco >nul 2>&1
if "%ERRORLEVEL%" == "0" (
    echo.
    echo Chocolatey is already installed.
) else (
    echo.
    echo Chocolatey is not installed. Installing Chocolatey...
    powershell -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
    call :check_error "Failed to install Chocolatey"
)
goto :eof

:: Function to check if Piper is already installed
:check_if_installed
if exist .\piper\piper.exe (
    echo.
    echo Piper is already installed.
    exit /b 0
) else (
    exit /b 1
)
