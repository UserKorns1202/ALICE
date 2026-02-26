@echo off

:: Main script logic starts here
call :ensure_choco

:: Ensure required commands are installed
call :check_command git git

cd .\llama

:: Download and extract w64devkit
call :download_w64devkit

:: Clone llamacpp repository only if not already cloned
call :is_repo_cloned
if %errorlevel% equ 0 (
    echo.
    echo llamacpp repository is already cloned.
) else (
    call :print_header "Cloning llamacpp Repository"
    git clone https://github.com/ggerganov/llama.cpp.git
    call :check_error "Failed to clone llamacpp repository."
)

:: Build llamacpp only if not installed
call :is_llama_installed
if %errorlevel% equ 0 (
    echo.
    echo llamacpp is already installed.
) else (
    call :print_header "Building llamacpp with w64devkit"

    :: Add w64devkit to the PATH
    set path=%CD%\w64devkit\bin;%path%

    :: Change to llama.cpp directory
    cd "%CD%\llama.cpp"

    call :retry_build "make llama-server -j 4" 13
)

:: Download openchat model only if not downloaded yet
call :is_model_downloaded
if %errorlevel% equ 0 (
    echo.
    echo openchat_3.5.Q4_K_M.gguf model is already downloaded.
) else (
    call :print_header "Downloading openchat_3.5.Q4_K_M.gguf Model"
    curl -L -o models\openchat_3.5.Q4_K_M.gguf https://huggingface.co/TheBloke/openchat_3.5-GGUF/resolve/main/openchat_3.5.Q4_K_M.gguf
    call :check_error "Failed to download openchat_3.5.Q4_K_M.gguf model."
)

:: Add w64devkit to the PATH if not already set
echo %PATH% | findstr /i "%CD%\\w64devkit\\bin" >nul
if %errorlevel% neq 0 (
    set path=%CD%\w64devkit\bin;%path%
    
    echo.
    echo Added w64devkit to the PATH.

    :: Change to llama.cpp directory
    cd "%CD%\llama.cpp"
) else (
    echo.
    echo w64devkit is already in the PATH.
)

:: Start llama.cpp server
call :print_header "Starting llama.cpp Server"
llama-server.exe -m models\openchat_3.5.Q4_K_M.gguf --port 8080
call :check_error "Failed to start llama.cpp server"

echo.
echo llamacpp server is running on port 8080.
pause

:: Function to print section headers
:print_header
echo.
echo ==================== %1 ====================
echo.
goto :eof

:: Function to check for errors
:check_error
if %errorlevel% neq 0 (
    echo.
    echo Error occurred: %1 
    exit /b 1
)
goto :eof

:: Install missing package
:install_package
echo.
echo Installing %1...
choco install -y %1
call :check_error "Failed to install %1"
echo.
echo %1 installed successfully
goto :eof

:: Function to check if a command exists
:check_command
where %1 >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo %1 is not installed. Installing it...
    call :install_package %2
) else (
    echo.
    echo %1 is already installed.
)
goto :eof

:: Ensure Chocolatey is installed
:ensure_choco
call :print_header "Ensuring Chocolatey is Installed"
where choco >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo Chocolatey not found. Installing Chocolatey...
    @powershell -NoProfile -ExecutionPolicy Bypass -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12; iex ((New-Object System.Net.WebClient).DownloadString('https://chocolatey.org/install.ps1'))"
    call :check_error "Failed to install Chocolatey"
) else (
    echo.
    echo Chocolatey is already installed.
)
goto :eof

:: Download and extract w64devkit if not already present
:download_w64devkit
if not exist "w64devkit" (
    call :print_header "Downloading w64devkit"
    curl -L -o w64devkit-x64-2.0.0.exe https://github.com/skeeto/w64devkit/releases/download/v2.0.0/w64devkit-x64-2.0.0.exe
    call :check_error "Failed to download w64devkit."
    
    echo.
    echo Extracting w64devkit...
    w64devkit-x64-2.0.0.exe -y
    call :check_error "Failed to extract w64devkit."
    
    echo.
    echo w64devkit downloaded and extracted successfully.
) else (
    echo.
    echo w64devkit is already present.
)
goto :eof

:: Clone llamacpp repository if not already cloned
:is_repo_cloned
if exist ".\llama.cpp" (
    exit /b 0
) else (
    exit /b 1
)

:: Build llamacpp if not installed
:is_llama_installed
if exist ".\llama.cpp\llama-server.exe" (
    exit /b 0
) else (
    exit /b 1
)

:: Check if model is already downloaded
:is_model_downloaded
if exist ".\llama.cpp\models\openchat_3.5.Q4_K_M.gguf" (
    exit /b 0
) else (
    exit /b 1
)

:: Retry build process
:retry_build
setlocal
set "command=%~1"
set /a "max_retries=%2"
set "retry_count=1"

:retry_loop
if %retry_count% geq %max_retries% (
    echo Failed to build after %max_retries% attempts.
    endlocal
    exit /b 1
)

echo.
echo Attempt #%retry_count% to build...
echo.

:: Attempt to build
%command%
if %errorlevel% equ 0 (
    echo Build successful.
    endlocal
    goto :eof
)

:: If build failed, increment retry count and retry after delay
echo.
echo Build failed. Retrying again...
echo.
set /a "retry_count+=1"
goto retry_loop


