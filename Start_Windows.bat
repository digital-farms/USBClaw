@echo off
setlocal EnableDelayedExpansion

title AI USB Assistant

set "BASE=%~dp0"
set "FILES=%BASE%Files\"
set "LLAMA=%FILES%llama\win\llama-server.exe"
set "MODELS=%FILES%models"
set "HOST=127.0.0.1"
set "PORT=8080"
set "CTX=4096"
set "MMPROJ_FILE=gemma-4-e2b-mmproj.gguf"

echo.
echo  ============================================
echo   AI USB Assistant (Gemma 4)
echo  ============================================
echo.
echo  Base: %FILES%
echo.

:: =============================================
::  Check llama-server.exe
:: =============================================
if not exist "%LLAMA%" (
    echo  [ERROR] llama-server.exe not found!
    echo  Expected: %LLAMA%
    echo.
    echo  Download from github.com/ggml-org/llama.cpp/releases
    echo  and place into Files\llama\win\ folder.
    echo.
    pause
    exit /b 1
)
echo  [OK] llama-server.exe

:: =============================================
::  Detect available models
:: =============================================
set "HAS_E2B=0"
set "HAS_E4B=0"
if exist "%MODELS%\gemma-4-e2b.gguf" set "HAS_E2B=1"
if exist "%MODELS%\gemma-4-e4b.gguf" set "HAS_E4B=1"

echo  Models found: E2B=!HAS_E2B! E4B=!HAS_E4B!

:: No models at all
if "!HAS_E2B!"=="0" if "!HAS_E4B!"=="0" (
    echo.
    echo  [ERROR] No model found in models\ folder!
    echo  Expected: gemma-4-e2b.gguf or gemma-4-e4b.gguf
    echo.
    pause
    exit /b 1
)

:: Only E2B exists - use it directly, no menu
if "!HAS_E2B!"=="1" if "!HAS_E4B!"=="0" (
    set "MODEL_FILE=gemma-4-e2b.gguf"
    set "MODEL_NAME=Gemma 4 E2B [vision+audio]"
    goto :model_ready
)

:: Only E4B exists - use it directly, no menu
if "!HAS_E2B!"=="0" if "!HAS_E4B!"=="1" (
    set "MODEL_FILE=gemma-4-e4b.gguf"
    set "MODEL_NAME=Gemma 4 E4B [vision+audio]"
    goto :model_ready
)

:: Both exist - show menu
echo.
echo  Two models available:
echo   [1] Gemma 4 E2B  - fast, light  (4+ GB RAM)
echo   [2] Gemma 4 E4B  - smarter      (8+ GB RAM)
echo.
set /p "MCHOICE=  Select [1-2]: "
if "!MCHOICE!"=="2" goto :pick_e4b

:: Default to E2B
set "MODEL_FILE=gemma-4-e2b.gguf"
set "MODEL_NAME=Gemma 4 E2B [vision+audio]"
goto :model_ready

:pick_e4b
set "MODEL_FILE=gemma-4-e4b.gguf"
set "MODEL_NAME=Gemma 4 E4B [vision+audio]"
goto :model_ready

:: =============================================
::  Model selected
:: =============================================
:model_ready
set "MODEL_PATH=%MODELS%\!MODEL_FILE!"
echo.
echo  [OK] Model: !MODEL_NAME!
echo       File:  !MODEL_FILE!

:: =============================================
::  Multimodal projection
:: =============================================
set "EXTRA_ARGS="
set "MMPROJ_PATH=%MODELS%\!MMPROJ_FILE!"
if exist "!MMPROJ_PATH!" (
    set "EXTRA_ARGS=--mmproj "!MMPROJ_PATH!""
    echo  [OK] Multimodal: !MMPROJ_FILE!
) else (
    echo  [WARNING] mmproj not found - vision/audio disabled
)

:: =============================================
::  Check port
:: =============================================
set "NSTMP=%TEMP%\llama_ns.tmp"
netstat -an > "!NSTMP!" 2>nul
findstr ":%PORT%" "!NSTMP!" >nul 2>&1
if not errorlevel 1 (
    del "!NSTMP!" 2>nul
    echo.
    echo  [NOTE] Port %PORT% already in use. Server is running.
    echo.
    echo  [1] Kill old server and restart
    echo  [2] Just open browser
    echo.
    set /p "PKILL=  Select [1-2]: "
    if "!PKILL!"=="1" (
        echo  Stopping old server...
        taskkill /F /IM llama-server.exe >nul 2>&1
        timeout /t 2 >nul
        echo  [OK] Old server stopped. Restarting...
        echo.
        goto :launch_server
    ) else (
        explorer "http://%HOST%:%PORT%"
        echo.
        pause
        exit /b 0
    )
)
del "!NSTMP!" 2>nul

:: =============================================
::  Launch server
:: =============================================
:launch_server
echo.
echo  ============================================
echo   Starting: !MODEL_NAME!
echo   Address:  http://%HOST%:%PORT%
echo  ============================================
echo.

start "llama-server" "%LLAMA%" --host %HOST% --port %PORT% -m "!MODEL_PATH!" -c %CTX% !EXTRA_ARGS!

:: Wait for server to load model
echo.
echo  Loading model, please wait...
echo  (this may take 15-60 seconds depending on your drive)
echo.
timeout /t 15 >nul
echo  Opening browser...
explorer "http://%HOST%:%PORT%"

echo.
echo  ============================================
echo   Server: http://%HOST%:%PORT%
echo   To stop: close this window + llama-server
echo  ============================================
echo.
pause
