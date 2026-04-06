# AI USB Assistant

Portable local AI assistant powered by **Gemma 4 + llama.cpp**.  
Runs from USB flash drive — no installation, no internet, no cloud.  
Supports text, images, audio, and optional reasoning/thinking mode.

## Install to USB Flash Drive

### Option A: Git Clone (recommended)

```bash
git clone https://github.com/digital-farms/USBClaw.git E:\
```

Replace `E:\` with your USB drive letter.

### Option B: Download ZIP

1. Go to https://github.com/digital-farms/USBClaw
2. Click **Code → Download ZIP**
3. Extract to USB flash drive root

### Download a model

Everything is included except AI models (too large for git).  
Launch `Start_Windows.bat` and use **[4] Download models** — it will download directly.

Or download manually:

| Model | Size | RAM | Direct link |
|-------|------|-----|-------------|
| **Gemma 4 E2B** | ~1.8 GB | 4+ GB | [Download](https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_K_M.gguf) |
| **Gemma 4 E4B** | ~3.1 GB | 8+ GB | [Download](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf) |
| **Gemma 4 31B** | ~18 GB | 20+ GB | [Download](https://huggingface.co/unsloth/gemma-4-31B-it-GGUF/resolve/main/gemma-4-31B-it-Q4_K_M.gguf) |

Save model files to `Files\models\` and rename:
- `gemma-4-E2B-it-Q4_K_M.gguf` → `gemma-4-e2b.gguf`
- `gemma-4-E4B-it-Q4_K_M.gguf` → `gemma-4-e4b.gguf`
- `gemma-4-31B-it-Q4_K_M.gguf` → `gemma-4-31b.gguf`

**Step 3 — Vision/audio support (optional, ~941 MB)**

For image and audio input, download the multimodal projector:
- [gemma-4-e2b-mmproj.gguf](https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-e2b-mmproj-BF16.gguf)
- Save as `Files\models\gemma-4-e2b-mmproj.gguf`

## Quick Start

1. Double-click **`Start_Windows.bat`**
2. Select model, adjust settings if needed
3. Press **[1] Start server**
4. Browser opens to `http://127.0.0.1:8085`

## Features

- **Model selection** — choose between E2B (fast), E4B (smart), 31B (powerful)
- **Thinking toggle** — brain icon in browser, click to enable/disable reasoning on the fly
- **RAG** — document icon in browser, upload local docs for context-aware answers (requires Python)
- **Download models** — built-in downloader in the launcher menu
- **Context size** — adjustable from 2048 to 16384 tokens

## Requirements

- **Windows 10+**
- **4+ GB RAM** (8+ for E4B, 20+ for 31B)
- USB flash drive formatted as **exFAT** (FAT32 has 4 GB file limit)
- **Python 3.10+** (optional, only for RAG feature)

## Project Structure

```
USBClaw/
├── Start_Windows.bat          Windows launcher with interactive menu
├── Files/
│   ├── llama/
│   │   └── win/               llama-server.exe + DLLs
│   ├── models/
│   │   ├── gemma-4-e2b.gguf   E2B model
│   │   ├── gemma-4-e4b.gguf   E4B model (optional)
│   │   ├── gemma-4-31b.gguf   31B model (optional)
│   │   └── gemma-4-e2b-mmproj.gguf  Vision/audio projector
│   ├── rag/
│   │   ├── server.py          RAG proxy server
│   │   └── inject.js          Browser UI controls
│   ├── config/
│   │   └── settings.json      Server configuration
│   └── data/
│       ├── docs/              Your documents for RAG
│       └── index/             Auto-generated search index
```

## How It Works

1. `Start_Windows.bat` launches **llama-server** with the selected model
2. If Python is available, a **RAG proxy** starts on port 8085
3. The proxy injects UI controls (reasoning toggle, RAG panel) into the chat
4. All requests go through the proxy which can augment them with local documents
5. No data leaves your machine — everything runs locally

## Notes

- **No internet needed** to run (only for downloading models)
- **All paths are relative** — works from any drive letter
- **No installation** — just copy and run
