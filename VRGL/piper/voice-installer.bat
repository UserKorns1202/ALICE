@echo off
SETLOCAL EnableDelayedExpansion

:: List of files to download
set "files=voice-en-us-amy-low.tar.gz"

:: GitHub release URL
set "url=https://github.com/rhasspy/piper/releases/download/v0.0.2"

:: Destination folder to extract the files
set "destination_folder=.\piper\models"

:: Main script starts here

:: Create the destination folder if it doesn't exist
call :print_header "Checking Destination Folder"
if not exist "%destination_folder%" (
    call :print_status "Creating destination folder: %destination_folder%"
    mkdir "%destination_folder%"
    if errorlevel 1 call :print_error "Failed to create destination folder %destination_folder%"
) else (
    call :print_status "Destination folder %destination_folder% already exists."
)

call :download_and_extract_files "voice-en-us-amy-low"

:: Function to download and extract files based on language filter
:download_and_extract_files
    set "lang_filter=%1"

    for %%f in (%files%) do (
        echo %%f
        if not errorlevel 1 (
            set "file=%%f"
            set "file_basename=!file:~6!"
            set "file_basename=!file_basename:~0,-7!"

            :: Check if the file is already installed
            call :is_installed !file_basename!
            if errorlevel 1 (
                :: Download the file
                call :print_header "Downloading !file!"
                powershell -Command "Invoke-WebRequest -Uri %url%/!file! -OutFile !file!"
                if errorlevel 1 call :print_error "Failed to download !file!"

                :: Extract the file to the destination folder
                call :print_header "Extracting !file!"
                tar -xzf "!file!" -C "%destination_folder%"
                if errorlevel 1 call :print_error "Failed to extract !file!"

                :: Clean up the downloaded archive
                del "!file!"
                call :print_status "Cleaned up !file!"
            ) else (
                call :print_status "!file! is already installed."
            )
        )
    )
    exit /b 0
endlocal

:: Function to print section headers
:print_header
    echo ==================== %1 ====================
    goto :eof

:: Function to print errors
:print_error
    echo Error: %1
    goto :eof

:: Function to print status
:print_status
    echo %1
    goto :eof

:: Check if a file is already installed
:is_installed
    set "file_basename=%1"
    if exist "!destination_folder!\!file_basename!.onnx" (
        exit /b 0
    ) else if exist "!destination_folder!\!file_basename!.onnx.json" (
        exit /b 0
    ) else (
        exit /b 1
    )


