@echo off
setlocal EnableDelayedExpansion

:: Prevent window from closing on errors
if "%~1"=="" (
    cmd /k call "%~f0" run "%~dp0"
    exit /b
)

:: Use passed base path (from wrapper) or fallback
if not "%~2"=="" (
    set "BASE=%~2"
) else (
    set "BASE=%~dp0"
)

title AI USB Assistant

:: =============================================
::  Variables
:: =============================================
set "FILES=%BASE%Files\"
set "LLAMA=%FILES%llama\win\llama-server.exe"
set "MODELS=%FILES%models"
set "HOST=127.0.0.1"
set "PORT=8080"
set "CTX=4096"
set "MMPROJ_E2B=gemma-4-e2b-mmproj.gguf"
set "MMPROJ_E4B=gemma-4-e4b-mmproj.gguf"
set "MMPROJ_FILE="
set "RAG_PORT=8085"
set "RAG_SERVER=%FILES%rag\server.py"
set "PYTHON="
set "THINKING=0"
set "MODEL_FILE="
set "MODEL_NAME="
set "THINK_LABEL=OFF"

:: =============================================
::  Sterile mode: keep host PC clean
:: =============================================
:: Note: we intentionally do NOT run `git config --global` here.
:: That would write to %USERPROFILE%\.gitconfig and leave a trace
:: on every PC the USB is plugged into. The .bat doesn't need git
:: at runtime — git is only used by the user to clone the repo.

:: Local tmp directory on the USB stick (so we never touch %TEMP% on host)
set "TMP_DIR=%FILES%tmp"
if not exist "!TMP_DIR!" mkdir "!TMP_DIR!" >nul 2>&1

:: =============================================
::  System check
:: =============================================
cls
echo.
echo  ============================================
echo    AI USB Assistant  v1.0
echo    Powered by Gemma 4 + llama.cpp
echo  ============================================
echo.

:: Check llama-server
if not exist "%LLAMA%" (
    echo  [X] llama-server.exe not found
    echo      Expected: Files\llama\win\llama-server.exe
    echo.
    echo      Download from github.com/ggml-org/llama.cpp/releases
    echo.
    echo  Press any key to exit...
    pause >nul
    exit /b 1
)

:: Check Python — prefer bundled portable version on the USB drive,
:: fall back to system-installed Python.
:: Bundled Python is expected at: Files\python\python.exe (embeddable distribution)
set "PORTABLE_PY=%FILES%python\python.exe"
if exist "!PORTABLE_PY!" (
    set "PYTHON=!PORTABLE_PY!"
) else (
    where python >nul 2>&1
    if not errorlevel 1 (
        for /f "delims=" %%P in ('where python 2^>nul') do (
            if not defined PYTHON set "PYTHON=%%P"
        )
    )
)

:: Keep host PC clean: don't write .pyc files anywhere outside the USB drive
set "PYTHONDONTWRITEBYTECODE=1"
:: Force UTF-8 I/O for embeddable Python (Windows default is cp1252)
set "PYTHONIOENCODING=utf-8"

:: ---- First-time setup: auto-install portable Python in the background ----
:: If no Python is available AND we have internet, silently download the
:: portable distribution to the USB drive. After this one-time step, the
:: USB is fully self-contained and works on any offline PC.
if not defined PYTHON (
    curl.exe -s --max-time 3 -o NUL -I "https://www.python.org" >nul 2>&1
    if not errorlevel 1 call :auto_install_python
)

:: Detect models (support both original HF names and short names)
set "HAS_E2B=0"
set "HAS_E4B=0"
set "HAS_31B=0"
set "HAS_MMPROJ=0"
set "HAS_MMPROJ_E2B=0"
set "HAS_MMPROJ_E4B=0"
set "E2B_FILE="
set "E4B_FILE="
set "B31_FILE="
if exist "%MODELS%\gemma-4-E2B-it-Q4_K_M.gguf" ( set "HAS_E2B=1" & set "E2B_FILE=gemma-4-E2B-it-Q4_K_M.gguf" )
if exist "%MODELS%\gemma-4-e2b.gguf" ( set "HAS_E2B=1" & set "E2B_FILE=gemma-4-e2b.gguf" )
if exist "%MODELS%\gemma-4-E4B-it-Q4_K_M.gguf" ( set "HAS_E4B=1" & set "E4B_FILE=gemma-4-E4B-it-Q4_K_M.gguf" )
if exist "%MODELS%\gemma-4-e4b.gguf" ( set "HAS_E4B=1" & set "E4B_FILE=gemma-4-e4b.gguf" )
if exist "%MODELS%\gemma-4-31B-it-Q4_K_M.gguf" ( set "HAS_31B=1" & set "B31_FILE=gemma-4-31B-it-Q4_K_M.gguf" )
if exist "%MODELS%\gemma-4-31b.gguf" ( set "HAS_31B=1" & set "B31_FILE=gemma-4-31b.gguf" )
if exist "%MODELS%\gemma-4-e2b-mmproj.gguf" ( set "HAS_MMPROJ=1" & set "HAS_MMPROJ_E2B=1" )
if exist "%MODELS%\gemma-4-e2b-mmproj-BF16.gguf" ( set "HAS_MMPROJ=1" & set "HAS_MMPROJ_E2B=1" )
if exist "%MODELS%\gemma-4-e4b-mmproj.gguf" ( set "HAS_MMPROJ=1" & set "HAS_MMPROJ_E4B=1" )

:: Default model selection
if "!HAS_E2B!"=="1" (
    set "MODEL_FILE=!E2B_FILE!"
    set "MODEL_NAME=Gemma 4 E2B"
)
if "!HAS_E2B!"=="0" if "!HAS_E4B!"=="1" (
    set "MODEL_FILE=!E4B_FILE!"
    set "MODEL_NAME=Gemma 4 E4B"
)
if "!HAS_E2B!"=="0" if "!HAS_E4B!"=="0" if "!HAS_31B!"=="1" (
    set "MODEL_FILE=!B31_FILE!"
    set "MODEL_NAME=Gemma 4 31B"
)
if not defined MODEL_FILE (
    echo  No models found. Use [4] Download models to get started.
    echo.
)

:: =============================================
::  Main menu
:: =============================================
:main_menu
cls
echo.
echo  ============================================
echo    AI USB Assistant  v1.0
echo  ============================================
echo.
echo  System:
echo    llama-server  OK
if defined PYTHON (
    if exist "!PORTABLE_PY!" (
        echo    Python        OK  - portable [Files\python]
    ) else (
        echo    Python        OK  - system
    )
) else (
    echo    Python        --  - RAG/tools disabled  [4] Download portable Python
)
echo.
echo  --------------------------------------------
echo  Current settings:
echo.
if defined MODEL_FILE (
    echo    Model:     !MODEL_NAME!  [!MODEL_FILE!]
) else (
    echo    Model:     [not selected]
)
echo    Context:   !CTX! tokens
echo    Thinking:  controlled in browser
echo.
echo  --------------------------------------------
echo.
echo    [1]  Start server
echo    [2]  Select model
echo    [3]  Settings
echo    [4]  Download models
echo    [q]  Exit
echo.
set "MENU="
set /p "MENU=  > "
if "!MENU!"=="1" goto :pre_launch
if "!MENU!"=="2" goto :model_menu
if "!MENU!"=="3" goto :settings_menu
if "!MENU!"=="4" goto :download_menu
if /i "!MENU!"=="q" exit /b 0
goto :main_menu

:: =============================================
::  Model selection
:: =============================================
:model_menu
cls
echo.
echo  ============================================
echo    Select Model
echo  ============================================
echo.
echo  Available models:
echo.
if "!HAS_E2B!"=="1" (
    echo    [1]  Gemma 4 E2B   - fast, light      - 4+ GB RAM
) else (
    echo    [1]  Gemma 4 E2B   - [not downloaded]
)
if "!HAS_E4B!"=="1" (
    echo    [2]  Gemma 4 E4B   - smarter          - 8+ GB RAM
) else (
    echo    [2]  Gemma 4 E4B   - [not downloaded]
)
if "!HAS_31B!"=="1" (
    echo    [3]  Gemma 4 31B   - most powerful    - 20+ GB RAM
) else (
    echo    [3]  Gemma 4 31B   - [not downloaded]
)
echo.
if defined MODEL_FILE echo  Current: !MODEL_NAME!
echo.
echo    [0]  Back
echo.
set "MC="
set /p "MC=  > "
if "!MC!"=="1" goto :pick_e2b
if "!MC!"=="2" goto :pick_e4b
if "!MC!"=="3" goto :pick_31b
goto :main_menu

:pick_e2b
if "!HAS_E2B!"=="1" (
    set "MODEL_FILE=!E2B_FILE!"
    set "MODEL_NAME=Gemma 4 E2B"
) else (
    echo.
    echo  Not downloaded. Use [4] Download models.
    timeout /t 2 >nul
)
goto :main_menu

:pick_e4b
if "!HAS_E4B!"=="1" (
    set "MODEL_FILE=!E4B_FILE!"
    set "MODEL_NAME=Gemma 4 E4B"
) else (
    echo.
    echo  Not downloaded. Use [4] Download models.
    timeout /t 2 >nul
)
goto :main_menu

:pick_31b
if "!HAS_31B!"=="1" (
    set "MODEL_FILE=!B31_FILE!"
    set "MODEL_NAME=Gemma 4 31B"
) else (
    echo.
    echo  Not downloaded. Use [4] Download models.
    timeout /t 2 >nul
)
goto :main_menu

:: =============================================
::  Settings
:: =============================================
:settings_menu
cls
echo.
echo  ============================================
echo    Settings
echo  ============================================
echo.
echo    [1]  Context size:  !CTX! tokens
echo.
echo         Quick presets:
echo           [a]  2048   - minimal, saves RAM
echo           [b]  4096   - default, good balance
echo           [c]  8192   - longer conversations
echo           [d]  16384  - very long context
echo.
echo.
echo    Thinking/Reasoning is toggled in the browser UI
echo.
echo    [0]  Back
echo.
set "SC="
set /p "SC=  > "

if "!SC!"=="a" ( set "CTX=2048" & goto :settings_menu )
if "!SC!"=="b" ( set "CTX=4096" & goto :settings_menu )
if "!SC!"=="c" ( set "CTX=8192" & goto :settings_menu )
if "!SC!"=="d" ( set "CTX=16384" & goto :settings_menu )
if "!SC!"=="1" goto :ctx_input
if "!SC!"=="0" goto :main_menu
goto :settings_menu

:ctx_input
echo.
set "CTXIN="
set /p "CTXIN=  Enter context size (or 0 = back): "
if "!CTXIN!"=="0" goto :settings_menu
if "!CTXIN!"=="a" set "CTX=2048"
if "!CTXIN!"=="b" set "CTX=4096"
if "!CTXIN!"=="c" set "CTX=8192"
if "!CTXIN!"=="d" set "CTX=16384"
:: Accept numeric input
set /a "_CTXTEST=!CTXIN!" 2>nul
if !_CTXTEST! GEQ 512 if !_CTXTEST! LEQ 131072 set "CTX=!CTXIN!"
goto :settings_menu

:: =============================================
::  Download models
:: =============================================
:download_menu
:: Re-detect models after downloads
set "HAS_E2B=0"
set "HAS_E4B=0"
set "HAS_31B=0"
set "HAS_MMPROJ=0"
set "HAS_MMPROJ_E2B=0"
set "HAS_MMPROJ_E4B=0"
set "E2B_FILE="
set "E4B_FILE="
set "B31_FILE="
if exist "%MODELS%\gemma-4-E2B-it-Q4_K_M.gguf" ( set "HAS_E2B=1" & set "E2B_FILE=gemma-4-E2B-it-Q4_K_M.gguf" )
if exist "%MODELS%\gemma-4-e2b.gguf" ( set "HAS_E2B=1" & set "E2B_FILE=gemma-4-e2b.gguf" )
if exist "%MODELS%\gemma-4-E4B-it-Q4_K_M.gguf" ( set "HAS_E4B=1" & set "E4B_FILE=gemma-4-E4B-it-Q4_K_M.gguf" )
if exist "%MODELS%\gemma-4-e4b.gguf" ( set "HAS_E4B=1" & set "E4B_FILE=gemma-4-e4b.gguf" )
if exist "%MODELS%\gemma-4-31B-it-Q4_K_M.gguf" ( set "HAS_31B=1" & set "B31_FILE=gemma-4-31B-it-Q4_K_M.gguf" )
if exist "%MODELS%\gemma-4-31b.gguf" ( set "HAS_31B=1" & set "B31_FILE=gemma-4-31b.gguf" )
if exist "%MODELS%\gemma-4-e2b-mmproj.gguf" ( set "HAS_MMPROJ=1" & set "HAS_MMPROJ_E2B=1" )
if exist "%MODELS%\gemma-4-e2b-mmproj-BF16.gguf" ( set "HAS_MMPROJ=1" & set "HAS_MMPROJ_E2B=1" )
if exist "%MODELS%\gemma-4-e4b-mmproj.gguf" ( set "HAS_MMPROJ=1" & set "HAS_MMPROJ_E4B=1" )
:: Auto-select first available model if none selected
if not defined MODEL_FILE if "!HAS_E2B!"=="1" ( set "MODEL_FILE=!E2B_FILE!" & set "MODEL_NAME=Gemma 4 E2B" )
if not defined MODEL_FILE if "!HAS_E4B!"=="1" ( set "MODEL_FILE=!E4B_FILE!" & set "MODEL_NAME=Gemma 4 E4B" )
if not defined MODEL_FILE if "!HAS_31B!"=="1" ( set "MODEL_FILE=!B31_FILE!" & set "MODEL_NAME=Gemma 4 31B" )
:: Detect FAT32
set "IS_FAT32=0"
for /f "tokens=*" %%F in ('fsutil fsinfo volumeinfo "%BASE:~0,2%\" 2^>nul ^| findstr /i "FAT32"') do set "IS_FAT32=1"
cls
echo.
echo  ============================================
echo    Download Models
echo  ============================================
echo.
if "!IS_FAT32!"=="1" (
    echo  [!] Drive is FAT32 - max file size 4 GB
    echo      Models over 4 GB will NOT work.
    echo      To use 31B, reformat drive as exFAT.
    echo.
)
echo  Models on disk:
echo.
if "!HAS_E2B!"=="1" (
    echo    Gemma 4 E2B    [OK]
) else (
    echo    Gemma 4 E2B    [missing]
)
if "!HAS_E4B!"=="1" (
    echo    Gemma 4 E4B    [OK]
) else (
    echo    Gemma 4 E4B    [not downloaded]
)
if "!HAS_31B!"=="1" (
    echo    Gemma 4 31B    [OK]
) else (
    echo    Gemma 4 31B    [not downloaded]
)
if "!HAS_MMPROJ_E2B!"=="1" (
    echo    Vision E2B     [OK]
) else (
    echo    Vision E2B     [not downloaded]
)
if "!HAS_MMPROJ_E4B!"=="1" (
    echo    Vision E4B     [OK]
) else (
    echo    Vision E4B     [not downloaded]
)
echo.
echo  Available downloads:
echo.
echo    [1]  Gemma 4 E2B    ~1.8 GB   fast, light     4+ GB RAM
echo    [2]  Gemma 4 E4B    ~3.1 GB   smarter         8+ GB RAM
if "!IS_FAT32!"=="1" (
    echo    [3]  Gemma 4 31B    ~18 GB    most powerful   20+ GB RAM  [needs exFAT!]
) else (
    echo    [3]  Gemma 4 31B    ~18 GB    most powerful   20+ GB RAM
)
echo    [4]  Vision E2B     ~941 MB   image/audio for E2B
echo    [5]  Vision E4B     ~990 MB   image/audio for E4B
echo.
if exist "!PORTABLE_PY!" (
    echo    [p]  Portable Python  [OK]  required for RAG/tools
) else (
    echo    [p]  Portable Python  ~10 MB  enables RAG and system tools
)
echo.
echo    [0]  Back
echo.
set "DC="
set /p "DC=  > "
if "!DC!"=="1" goto :download_e2b
if "!DC!"=="2" goto :download_e4b
if "!DC!"=="3" goto :download_31b
if "!DC!"=="4" goto :download_mmproj_e2b
if "!DC!"=="5" goto :download_mmproj_e4b
if /i "!DC!"=="p" goto :download_python
goto :main_menu

:download_e2b
if not exist "%MODELS%" mkdir "%MODELS%"
echo.
echo  Downloading Gemma 4 E2B...
echo  Source: huggingface.co/unsloth/gemma-4-E2B-it-GGUF
echo.
curl.exe -L --progress-bar -f -o "%MODELS%\gemma-4-E2B-it-Q4_K_M.gguf" "https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_K_M.gguf"
if errorlevel 1 (
    echo.
    echo  [X] Download failed. Check your internet connection.
    del "%MODELS%\gemma-4-E2B-it-Q4_K_M.gguf" 2>nul
) else (
    set "HAS_E2B=1"
    set "E2B_FILE=gemma-4-E2B-it-Q4_K_M.gguf"
    echo.
    echo  [OK] Gemma 4 E2B downloaded!
    if "!HAS_MMPROJ_E2B!"=="0" goto :offer_mmproj_e2b
)
echo.
echo  Press any key...
pause >nul
goto :download_menu

:download_e4b
if not exist "%MODELS%" mkdir "%MODELS%"
echo.
echo  Downloading Gemma 4 E4B...
echo  Source: huggingface.co/unsloth/gemma-4-E4B-it-GGUF
echo.
curl.exe -L --progress-bar -f -o "%MODELS%\gemma-4-E4B-it-Q4_K_M.gguf" "https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf"
if errorlevel 1 (
    echo.
    echo  [X] Download failed. Check your internet connection.
    del "%MODELS%\gemma-4-E4B-it-Q4_K_M.gguf" 2>nul
) else (
    set "HAS_E4B=1"
    set "E4B_FILE=gemma-4-E4B-it-Q4_K_M.gguf"
    echo.
    echo  [OK] Gemma 4 E4B downloaded!
    if "!HAS_MMPROJ_E4B!"=="0" goto :offer_mmproj_e4b
)
echo.
echo  Press any key...
pause >nul
goto :download_menu

:download_31b
if "!IS_FAT32!"=="1" (
    echo.
    echo  [X] Cannot download 31B on FAT32 - file is ~18 GB, limit is 4 GB.
    echo      Reformat your USB drive as exFAT first.
    echo.
    echo  Press any key...
    pause >nul
    goto :download_menu
)
if not exist "%MODELS%" mkdir "%MODELS%"
echo.
echo  Downloading Gemma 4 31B (~18 GB, this will take a while)...
echo  Source: huggingface.co/unsloth/gemma-4-31B-it-GGUF
echo.
curl.exe -L --progress-bar -f -o "%MODELS%\gemma-4-31B-it-Q4_K_M.gguf" "https://huggingface.co/unsloth/gemma-4-31B-it-GGUF/resolve/main/gemma-4-31B-it-Q4_K_M.gguf"
if errorlevel 1 (
    echo.
    echo  [X] Download failed. Check your internet connection.
    del "%MODELS%\gemma-4-31B-it-Q4_K_M.gguf" 2>nul
) else (
    set "HAS_31B=1"
    echo.
    echo  [OK] Gemma 4 31B downloaded!
)
echo.
echo  Press any key...
pause >nul
goto :download_menu

:offer_mmproj_e2b
echo.
echo  --------------------------------------------
echo  Vision model for E2B enables image/audio input (~941 MB).
echo.
set "DV="
set /p "DV=  Download vision model for E2B now? [y/n] > "
if /i not "!DV!"=="y" (
    echo.
    echo  Skipped. You can download it later from [4] Download models.
    echo.
    echo  Press any key...
    pause >nul
    goto :download_menu
)

:download_mmproj_e2b
if not exist "%MODELS%" mkdir "%MODELS%"
echo.
echo  Downloading Vision model for E2B (mmproj)...
echo  Source: huggingface.co/ggml-org/gemma-4-E2B-it-GGUF
echo.
curl.exe -L --progress-bar -f -o "%MODELS%\gemma-4-e2b-mmproj.gguf" "https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF/resolve/main/mmproj-gemma-4-e2b-it-f16.gguf?download=true"
if errorlevel 1 (
    echo.
    echo  [X] Download failed. Check your internet connection.
    del "%MODELS%\gemma-4-e2b-mmproj.gguf" 2>nul
) else (
    set "HAS_MMPROJ=1"
    set "HAS_MMPROJ_E2B=1"
    echo.
    echo  [OK] Vision model for E2B downloaded!
)
echo.
echo  Press any key...
pause >nul
goto :download_menu

:offer_mmproj_e4b
echo.
echo  --------------------------------------------
echo  Vision model for E4B enables image/audio input (~990 MB).
echo.
set "DV="
set /p "DV=  Download vision model for E4B now? [y/n] > "
if /i not "!DV!"=="y" (
    echo.
    echo  Skipped. You can download it later from [5] Download models.
    echo.
    echo  Press any key...
    pause >nul
    goto :download_menu
)

:download_mmproj_e4b
if not exist "%MODELS%" mkdir "%MODELS%"
echo.
echo  Downloading Vision model for E4B (mmproj)...
echo  Source: huggingface.co/ggml-org/gemma-4-E4B-it-GGUF
echo.
curl.exe -L --progress-bar -f -o "%MODELS%\gemma-4-e4b-mmproj.gguf" "https://huggingface.co/ggml-org/gemma-4-E4B-it-GGUF/resolve/main/mmproj-gemma-4-e4b-it-f16.gguf?download=true"
if errorlevel 1 (
    echo.
    echo  [X] Download failed. Check your internet connection.
    del "%MODELS%\gemma-4-e4b-mmproj.gguf" 2>nul
) else (
    set "HAS_MMPROJ=1"
    set "HAS_MMPROJ_E4B=1"
    echo.
    echo  [OK] Vision model for E4B downloaded!
)
echo.
echo  Press any key...
pause >nul
goto :download_menu

:: =============================================
::  Portable Python (embeddable) — core installer
:: =============================================
:: Callable sub-routine. Sets PYTHON on success, leaves it empty on failure.
:: Caller is responsible for printing context (or staying silent for auto-mode).
:: Args: %1 = "auto" for silent (first-time setup) or "manual" for verbose.
:auto_install_python
setlocal EnableDelayedExpansion
set "PY_MODE=%~1"
if "!PY_MODE!"=="" set "PY_MODE=auto"
set "PY_VER=3.11.9"
set "PY_ZIP_URL=https://www.python.org/ftp/python/!PY_VER!/python-!PY_VER!-embed-amd64.zip"
set "PY_DEST=%FILES%python"
set "PY_TMP=%FILES%python_dl.zip"

if "!PY_MODE!"=="auto" (
    echo.
    echo  --------------------------------------------
    echo   First-time setup: installing portable Python ~10 MB
    echo   This happens once - the USB will work offline afterwards.
    echo  --------------------------------------------
)

if not exist "!PY_DEST!" mkdir "!PY_DEST!" >nul 2>&1

curl.exe -L --progress-bar -f -o "!PY_TMP!" "!PY_ZIP_URL!"
if errorlevel 1 (
    if "!PY_MODE!"=="manual" echo  [X] Download failed.
    del "!PY_TMP!" 2>nul
    endlocal
    exit /b 1
)

tar.exe -xf "!PY_TMP!" -C "!PY_DEST!" 2>nul
if errorlevel 1 (
    powershell -NoProfile -Command "Expand-Archive -LiteralPath '!PY_TMP!' -DestinationPath '!PY_DEST!' -Force" 2>nul
    if errorlevel 1 (
        if "!PY_MODE!"=="manual" echo  [X] Extraction failed.
        del "!PY_TMP!" 2>nul
        endlocal
        exit /b 1
    )
)
del "!PY_TMP!" 2>nul

if not exist "!PY_DEST!\python.exe" (
    if "!PY_MODE!"=="manual" echo  [X] python.exe not found after extraction.
    endlocal
    exit /b 1
)

if "!PY_MODE!"=="auto" (
    echo  [OK] Portable Python ready. RAG and System Tools enabled.
    timeout /t 1 >nul
)
endlocal
:: Propagate PYTHON path to caller scope
set "PYTHON=%PORTABLE_PY%"
exit /b 0

:: =============================================
::  Download Portable Python — menu entry
:: =============================================
:download_python
echo.
echo  --------------------------------------------
echo  Portable Python (embeddable distribution)
echo  Source: python.org   ~10 MB
echo  Installs to: Files\python\
echo  --------------------------------------------
echo.

if exist "!PORTABLE_PY!" (
    echo  [i] Portable Python is already installed.
    set "REPL="
    set /p "REPL=  Reinstall / overwrite? [y/n] > "
    if /i not "!REPL!"=="y" (
        echo  Cancelled.
        echo.
        echo  Press any key...
        pause >nul
        goto :download_menu
    )
    echo  Removing existing installation...
    rmdir /S /Q "%FILES%python" 2>nul
)

call :auto_install_python manual
if errorlevel 1 (
    echo.
    echo  Press any key...
    pause >nul
    goto :download_menu
)
echo  [OK] Portable Python installed.
echo.
echo  Press any key...
pause >nul
goto :download_menu

:: =============================================
::  Pre-launch checks
:: =============================================
:pre_launch

:: Check model selected
if not defined MODEL_FILE (
    echo.
    echo  [X] No model selected! Go to [2] Select model first.
    timeout /t 2 >nul
    goto :main_menu
)

set "MODEL_PATH=%MODELS%\!MODEL_FILE!"
if not exist "!MODEL_PATH!" (
    echo.
    echo  [X] Model file not found: !MODEL_FILE!
    echo      Download it first from [4] Download models.
    timeout /t 2 >nul
    goto :main_menu
)

:: Build extra args
set "EXTRA_ARGS="

:: Multimodal — select the correct mmproj for the chosen model
:: Each model needs its own mmproj (E2B and E4B have different embedding sizes)
set "MMPROJ_FILE="
if "!MODEL_NAME!"=="Gemma 4 E2B" set "MMPROJ_FILE=!MMPROJ_E2B!"
if "!MODEL_NAME!"=="Gemma 4 E4B" set "MMPROJ_FILE=!MMPROJ_E4B!"

if defined MMPROJ_FILE (
    set "MMPROJ_PATH=%MODELS%\!MMPROJ_FILE!"
    set "MMPROJ_OK=0"
    if exist "!MMPROJ_PATH!" (
        for %%A in ("!MMPROJ_PATH!") do (
            if %%~zA GTR 100000000 set "MMPROJ_OK=1"
        )
    )
    if "!MMPROJ_OK!"=="1" (
        set "EXTRA_ARGS=--mmproj "!MMPROJ_PATH!""
    ) else (
        if exist "!MMPROJ_PATH!" (
            echo  [!] Vision model file seems corrupt or incomplete, skipping.
            echo      Re-download it from Download models menu.
            echo.
        ) else (
            echo  [i] No vision model for !MODEL_NAME!. Download it for image/audio support.
            echo.
        )
    )
)

:: Reasoning is now controlled dynamically by the RAG proxy (inject.js toggle button)
:: No need for --reasoning flag here

:: Check port (use tmp on the USB drive, not on host PC)
set "NSTMP=!TMP_DIR!\llama_ns.tmp"
netstat -an > "!NSTMP!" 2>nul
findstr ":%PORT%" "!NSTMP!" >nul 2>&1
if not errorlevel 1 (
    del "!NSTMP!" 2>nul
    echo.
    echo  Port %PORT% is already in use.
    echo.
    echo    [1]  Kill old server and restart
    echo    [2]  Just open browser
    echo    [0]  Back to menu
    echo.
    set "PC="
    set /p "PC=  > "
    if "!PC!"=="1" goto :kill_and_restart
    if "!PC!"=="2" goto :open_browser_only
    goto :main_menu
)
del "!NSTMP!" 2>nul
goto :launch_server

:kill_and_restart
echo  Stopping old server...
taskkill /F /IM llama-server.exe >nul 2>&1
timeout /t 2 >nul
echo  [OK] Stopped.
goto :launch_server

:open_browser_only
if defined PYTHON (
    explorer "http://%HOST%:%RAG_PORT%"
) else (
    explorer "http://%HOST%:%PORT%"
)
goto :running

:: =============================================
::  Launch server
:: =============================================
:launch_server
cls
echo.
echo  ============================================
echo    Starting Server
echo  ============================================
echo.
echo  Model:      !MODEL_NAME!
echo  Context:    !CTX! tokens
echo  Thinking:   !THINK_LABEL!
if defined PYTHON (
    echo  RAG:        enabled
) else (
    echo  RAG:        disabled - no Python
)
echo.
echo  --------------------------------------------
echo.

start "llama-server" cmd /k ""%LLAMA%" --host %HOST% --port %PORT% -m "!MODEL_PATH!" -c %CTX% !EXTRA_ARGS!"

echo  Loading model (may take up to ~2 min on slow USB drives)...
echo.

:: Wait for llama-server /health to return 200 (model fully loaded)
set /a "_TRIES=0"
set "_MAX_TRIES=180"
:health_wait
set /a "_TRIES+=1"
curl.exe -sf -o NUL --max-time 2 "http://%HOST%:%PORT%/health" >nul 2>&1
if not errorlevel 1 goto :model_ready
<nul set /p "=."
if !_TRIES! GEQ !_MAX_TRIES! goto :model_timeout
timeout /t 1 >nul
goto :health_wait

:model_timeout
echo.
echo.
echo  [!] Model did not become ready within !_MAX_TRIES! seconds.
echo      Check the "llama-server" window for errors.
echo      Continuing anyway - server may still come up.
echo.
goto :after_load

:model_ready
echo.
echo  [OK] Model loaded and ready.
echo.

:after_load

:: Start RAG proxy
if defined PYTHON (
    if exist "!RAG_SERVER!" (
        echo  Starting RAG proxy...
        start "rag-proxy" "!PYTHON!" "!RAG_SERVER!" --port %RAG_PORT% --llama-port %PORT%
        timeout /t 2 >nul
    )
)

:: Set browse URL
if defined PYTHON (
    set "BROWSE_URL=http://%HOST%:%RAG_PORT%"
) else (
    set "BROWSE_URL=http://%HOST%:%PORT%"
)

echo  Opening browser...
explorer "!BROWSE_URL!"

:: =============================================
::  Running
:: =============================================
:running
echo.
echo  ============================================
echo    Server Running
echo  ============================================
echo.
echo  UI:       !BROWSE_URL!
echo  Server:   http://%HOST%:%PORT%
if defined PYTHON echo  RAG:      http://%HOST%:%RAG_PORT%
echo  Model:    !MODEL_NAME!  [ctx: !CTX!]
echo.
echo  --------------------------------------------
echo.
echo    [r]  Restart server
echo    [b]  Open browser
echo    [q]  Stop and exit
echo.

:running_loop
set "RC="
set /p "RC=  > "
if /i "!RC!"=="r" goto :do_restart
if /i "!RC!"=="b" goto :do_open
if /i "!RC!"=="q" goto :do_quit
goto :running_loop

:do_restart
echo  Stopping...
taskkill /F /IM llama-server.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq rag-proxy" >nul 2>&1
timeout /t 2 >nul
goto :launch_server

:do_open
explorer "!BROWSE_URL!"
goto :running_loop

:do_quit
echo  Stopping server...
taskkill /F /IM llama-server.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq rag-proxy" >nul 2>&1
echo  Bye!
timeout /t 1 >nul
exit /b 0
