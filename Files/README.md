# AI USB Assistant

Portable local AI assistant powered by Gemma 4. Runs from USB flash drive, no installation needed.
Supports text, images, audio, and reasoning (thinking mode).

## Requirements

- **Windows 10+**
- Minimum **4 GB RAM** (8+ recommended for E4B model)
- USB flash drive formatted as **exFAT** (not FAT32!)

## Quick Start

### Windows

1. Double-click `Start_Windows.bat`
2. Server starts automatically with the best available model
3. Browser opens to `http://127.0.0.1:8080`

## Models

All models are Google Gemma 4 family (Q4_K_M quantization).
All support: **text + vision + audio + thinking**.

| Model | File | Size | RAM | Included |
|-------|------|------|-----|----------|
| **Gemma 4 E2B** | `gemma-4-e2b.gguf` | ~1.8 GB | 4+ GB | Yes (default) |
| **Gemma 4 E4B** | `gemma-4-e4b.gguf` | ~3.1 GB | 8+ GB | No (optional download) |

Vision requires `gemma-4-e2b-mmproj.gguf` (~941 MB, included).

### Download Extra Models

To download the smarter E4B model (requires internet):
```powershell
.\Download_Models.ps1
```

If both models are present, the launcher will ask which one to use.

## Project Structure

```
AI_USB/
+-- llama/
|   +-- win/                llama-server.exe + DLLs (Windows)
+-- models/
|   +-- gemma-4-e2b.gguf    Default model (included)
|   +-- gemma-4-e2b-mmproj.gguf  Vision/audio projection (included)
|   +-- gemma-4-e4b.gguf    Optional smarter model (download separately)
+-- config/
|   +-- settings.json       Server config + model definitions
+-- data/
|   +-- chats/              (reserved for chat history)
|   +-- docs/               (reserved for documents)
+-- Start_Windows.bat       Windows launcher
+-- Download_Models.ps1     Optional model downloader
+-- launcher.html           Alternative browser UI
+-- README.md
+-- PROJECT_CONTEXT.md      Dev context for LLM handoff
```

## How It Works

1. Launcher detects available model files in `models/`
2. If only E2B exists, uses it automatically (no menu)
3. If both E2B and E4B exist, asks which to use
4. Starts `llama-server` with `--mmproj` for vision/audio
5. Waits for server, then opens browser
6. Chat at `http://127.0.0.1:8080`

## Notes

- **USB must be exFAT** (FAT32 has 4 GB file size limit)
- **No internet needed** to run (only for optional model downloads)
- **All paths are relative** - works from any drive letter
