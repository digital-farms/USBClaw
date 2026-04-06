@echo off
setlocal EnableDelayedExpansion

title AI USB Assistant

:: =============================================
::  Variables
:: =============================================
set "BASE=%~dp0"
set "FILES=%BASE%Files\"
set "LLAMA=%FILES%llama\win\llama-server.exe"
set "MODELS=%FILES%models"
set "HOST=127.0.0.1"
set "PORT=8080"
set "CTX=4096"
set "MMPROJ_FILE=gemma-4-e2b-mmproj.gguf"
set "RAG_PORT=8085"
set "RAG_SERVER=%FILES%rag\server.py"
set "PYTHON="
set "THINKING=0"
set "MODEL_FILE="
set "MODEL_NAME="
set "THINK_LABEL=OFF"

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
    pause
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
set "E2B_FILE="
set "E4B_FILE="
set "B31_FILE="
if exist "%MODELS%\gemma-4-E2B-it-Q4_K_M.gguf" ( set "HAS_E2B=1" & set "E2B_FILE=gemma-4-E2B-it-Q4_K_M.gguf" )
if exist "%MODELS%\gemma-4-e2b.gguf" ( set "HAS_E2B=1" & set "E2B_FILE=gemma-4-e2b.gguf" )
if exist "%MODELS%\gemma-4-E4B-it-Q4_K_M.gguf" ( set "HAS_E4B=1" & set "E4B_FILE=gemma-4-E4B-it-Q4_K_M.gguf" )
if exist "%MODELS%\gemma-4-e4b.gguf" ( set "HAS_E4B=1" & set "E4B_FILE=gemma-4-e4b.gguf" )
if exist "%MODELS%\gemma-4-31B-it-Q4_K_M.gguf" ( set "HAS_31B=1" & set "B31_FILE=gemma-4-31B-it-Q4_K_M.gguf" )
if exist "%MODELS%\gemma-4-31b.gguf" ( set "HAS_31B=1" & set "B31_FILE=gemma-4-31b.gguf" )

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
echo    [0]  Exit
echo.
set "MENU="
set /p "MENU=  > "
if "!MENU!"=="1" goto :pre_launch
if "!MENU!"=="2" goto :model_menu
if "!MENU!"=="3" goto :settings_menu
if "!MENU!"=="4" goto :download_menu
if "!MENU!"=="0" exit /b 0
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
set /p "CTXIN=  Enter context size: "
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
cls
echo.
echo  ============================================
echo    Download Models
echo  ============================================
echo.
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
echo.
echo  Available downloads:
echo.
echo    [1]  Gemma 4 E2B   ~1.8 GB   fast, light     4+ GB RAM
echo    [2]  Gemma 4 E4B   ~3.1 GB   smarter         8+ GB RAM
echo    [3]  Gemma 4 31B   ~18 GB    most powerful   20+ GB RAM
echo.
echo    [0]  Back
echo.
set "DC="
set /p "DC=  > "
if "!DC!"=="1" goto :download_e2b
if "!DC!"=="2" goto :download_e4b
if "!DC!"=="3" goto :download_31b
goto :main_menu

:download_e2b
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
    echo.
    echo  [OK] Gemma 4 E2B downloaded!
)
echo.
pause
goto :download_menu

:download_e4b
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
    echo.
    echo  [OK] Gemma 4 E4B downloaded!
)
echo.
pause
goto :download_menu

:download_31b
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
pause
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

:: Multimodal (E-series models only, detected by MODEL_NAME)
set "MMPROJ_PATH=%MODELS%\!MMPROJ_FILE!"
if "!MODEL_NAME!"=="Gemma 4 E2B" if exist "!MMPROJ_PATH!" set "EXTRA_ARGS=--mmproj "!MMPROJ_PATH!""
if "!MODEL_NAME!"=="Gemma 4 E4B" if exist "!MMPROJ_PATH!" set "EXTRA_ARGS=--mmproj "!MMPROJ_PATH!""

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

start "llama-server" "%LLAMA%" --host %HOST% --port %PORT% -m "!MODEL_PATH!" -c %CTX% !EXTRA_ARGS!

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
