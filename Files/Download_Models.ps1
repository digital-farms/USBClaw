$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ModelsDir = Join-Path $ScriptDir "models"
$LlamaServer = Join-Path $ScriptDir "llama\win\llama-server.exe"

if (-not (Test-Path $ModelsDir)) {
    New-Item -ItemType Directory -Path $ModelsDir -Force | Out-Null
}

Clear-Host
Write-Host ""
Write-Host "  ============================================" -ForegroundColor DarkCyan
Write-Host "   AI USB Assistant - Download Extra Models" -ForegroundColor DarkCyan
Write-Host "  ============================================" -ForegroundColor DarkCyan
Write-Host ""
Write-Host "  Gemma 4 E2B (default) is already included." -ForegroundColor Gray
Write-Host "  This script downloads OPTIONAL bigger models." -ForegroundColor Gray
Write-Host ""

# Show current models
Write-Host "  Current models in models\:" -ForegroundColor DarkGray
$existing = Get-ChildItem (Join-Path $ModelsDir "*.gguf") -ErrorAction SilentlyContinue
if ($existing) {
    foreach ($f in $existing) {
        $sizeGB = [math]::Round($f.Length / 1GB, 2)
        Write-Host "    $($f.Name) ($sizeGB GB)" -ForegroundColor Green
    }
} else {
    Write-Host "    (none)" -ForegroundColor Yellow
}
Write-Host ""

# Available downloads
Write-Host "  Available downloads:" -ForegroundColor DarkCyan
Write-Host ""

$e4bPath = Join-Path $ModelsDir "gemma-4-e4b.gguf"
$e4bMark = ""
if ((Test-Path $e4bPath) -and (Get-Item $e4bPath).Length -gt 100MB) {
    $e4bMark = " [already downloaded]"
}

Write-Host "  [1] Gemma 4 E4B  (~3.1 GB)  - smarter, needs 8+ GB RAM$e4bMark" -ForegroundColor DarkCyan
Write-Host "  [0] Exit" -ForegroundColor DarkCyan
Write-Host ""

$choice = Read-Host "  Select [1, 0]"

if ($choice -eq "0") {
    Write-Host "  Bye." -ForegroundColor Gray
    exit 0
}

if ($choice -eq "1") {
    Write-Host ""

    if ((Test-Path $e4bPath) -and (Get-Item $e4bPath).Length -gt 100MB) {
        $sizeGB = [math]::Round((Get-Item $e4bPath).Length / 1GB, 2)
        Write-Host "  [OK] gemma-4-e4b.gguf already exists ($sizeGB GB)" -ForegroundColor Green
        Write-Host ""
        Write-Host "  Press Enter to exit..." -ForegroundColor Gray
        Read-Host
        exit 0
    }

    # Method 1: Use llama-server --hf-repo (handles Xet storage)
    if (Test-Path $LlamaServer) {
        Write-Host "  Downloading via llama-server --hf-repo..." -ForegroundColor Cyan
        Write-Host "  Repo: unsloth/gemma-4-E4B-it-GGUF" -ForegroundColor DarkGray
        Write-Host "  File: gemma-4-E4B-it-Q4_K_M.gguf" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  This will start llama-server to download the model." -ForegroundColor DarkGray
        Write-Host "  It will download to HuggingFace cache, then we copy it." -ForegroundColor DarkGray
        Write-Host "  Press Ctrl+C in the server window once download finishes." -ForegroundColor Yellow
        Write-Host ""

        Start-Process -FilePath $LlamaServer -ArgumentList @(
            "--hf-repo", "unsloth/gemma-4-E4B-it-GGUF",
            "--hf-file", "gemma-4-E4B-it-Q4_K_M.gguf",
            "--host", "127.0.0.1", "--port", "8090", "-c", "512"
        ) -PassThru -Wait

        # Find the downloaded file in HF cache
        $cacheBase = Join-Path $env:USERPROFILE ".cache\huggingface\hub\models--unsloth--gemma-4-E4B-it-GGUF"
        $found = Get-ChildItem -Path $cacheBase -Recurse -Filter "gemma-4-E4B-it-Q4_K_M.gguf" -ErrorAction SilentlyContinue | Select-Object -First 1

        if ($found -and $found.Length -gt 100MB) {
            Write-Host "  Copying to models\gemma-4-e4b.gguf..." -ForegroundColor Cyan
            Copy-Item $found.FullName $e4bPath -Force
            $sizeGB = [math]::Round((Get-Item $e4bPath).Length / 1GB, 2)
            Write-Host "  [OK] Done! ($sizeGB GB)" -ForegroundColor Green
        } else {
            Write-Host "  [X] Model not found in cache after download." -ForegroundColor Red
            Write-Host "  Try running llama-server manually with --hf-repo." -ForegroundColor Yellow
        }
    } else {
        Write-Host "  [ERROR] llama-server.exe not found!" -ForegroundColor Red
        Write-Host "  Cannot download model without llama-server." -ForegroundColor Red
    }
} else {
    Write-Host "  Invalid choice." -ForegroundColor Red
}

Write-Host ""
Write-Host "  Press Enter to exit..." -ForegroundColor Gray
Read-Host
