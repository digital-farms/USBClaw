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
::  Git safe.directory (USB drives need this)
:: =============================================
where git >nul 2>&1
if not errorlevel 1 (
    git config --global --add safe.directory "%BASE:~0,-1%" >nul 2>&1
)

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

:: Check Python
where python >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        if not defined PYTHON set "PYTHON=%%P"
    )
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
    echo    Python        OK  - RAG enabled
) else (
    echo    Python        --  - RAG disabled
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
echo    [0]  Back
echo.
set "DC="
set /p "DC=  > "
if "!DC!"=="1" goto :download_e2b
if "!DC!"=="2" goto :download_e4b
if "!DC!"=="3" goto :download_31b
if "!DC!"=="4" goto :download_mmproj_e2b
if "!DC!"=="5" goto :download_mmproj_e4b
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

:: Check port
set "NSTMP=%TEMP%\llama_ns.tmp"
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

echo  Loading model...
echo  This may take 15-60 seconds depending on your drive.
echo.

:: Animated wait
for /L %%i in (1,1,15) do (
    <nul set /p "=."
    timeout /t 1 >nul
)
echo.
echo.

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
