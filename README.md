# AI USB Assistant

Portable local AI assistant powered by **Gemma 4 + llama.cpp**.  
Runs from USB flash drive — no installation, no internet, no cloud.  
Supports text, images, audio, and optional reasoning/thinking mode.

## Install to USB Flash Drive

### Option A: Git Clone (recommended)

Insert your USB flash drive (formatted as **exFAT**), open PowerShell/CMD and run:

```
git clone https://github.com/digital-farms/USBClaw.git
```

This creates a `USBClaw` folder wherever you run it. Move it to your flash drive if needed.

Or clone directly to the flash drive (replace `G:` with your drive letter):

```
git clone https://github.com/digital-farms/USBClaw.git G:\USBClaw
```

### Option B: Download ZIP

1. Go to https://github.com/digital-farms/USBClaw
2. Green button **Code → Download ZIP**
3. Extract to USB flash drive

### Download a model

Everything is included except AI models (too large for git).  
Launch `Start_Windows.bat` and use **[4] Download models** — it will download directly.

Or download manually:

| Model | Size | RAM | Direct link |
|-------|------|-----|-------------|
| **Gemma 4 E2B** | ~1.8 GB | 4+ GB | [Download](https://huggingface.co/unsloth/gemma-4-E2B-it-GGUF/resolve/main/gemma-4-E2B-it-Q4_K_M.gguf) |
| **Gemma 4 E4B** | ~3.1 GB | 8+ GB | [Download](https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf) |
| **Gemma 4 31B** | ~18 GB | 20+ GB | [Download](https://huggingface.co/unsloth/gemma-4-31B-it-GGUF/resolve/main/gemma-4-31B-it-Q4_K_M.gguf) |

Save downloaded files to `Files\models\` (no renaming needed).

**Step 3 — Vision/audio support (optional, ~941 MB)**

For image and audio input, download the multimodal projector:
- [gemma-4-e2b-mmproj.gguf](https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF/resolve/main/mmproj-gemma-4-e2b-it-f16.gguf)
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
- **USB-persisted chats** — chat history and settings are mirrored to `Files/data/storage.json` on the USB stick. On next launch (even on a different PC) chats are restored automatically.
- **Sterile host** — on tab close the browser's `localStorage`, `sessionStorage`, cookies, IndexedDB and caches are wiped, so the host PC keeps no traces. Your data lives only on the USB drive.

## ⚠ Uncensored models

USBClaw can optionally download and run **uncensored** Gemma 4 variants
([HauhauCS Aggressive abliterated builds](https://huggingface.co/HauhauCS)).
These models have safety alignment removed and will generate **any** content
you request — including content that may be illegal in your jurisdiction,
harmful, offensive, or factually false.

**By using uncensored models you accept full responsibility for everything
you generate, request, store, and share.** The project authors provide this
capability as-is and are NOT liable for your use.

Access:
1. Launcher → `[4] Download models` → `[u]` Uncensored models.
2. First entry shows a consent screen — type `I ACCEPT` to proceed.
3. Consent + every download + every launch are recorded with HMAC-signed
   timestamps in `Files/data/uncensored_consent.log` (on the USB drive only —
   never written to the host PC). You can revoke consent any time via
   `[r]` in the same menu, which deletes the log.

When an uncensored model is loaded, the browser UI shows a permanent
red banner at the top of every page so you always know the current mode.

## Requirements

- **Windows 10+**
- **4+ GB RAM** (8+ for E4B, 20+ for 31B)
- USB flash drive formatted as **exFAT** (FAT32 has 4 GB file limit)
- **Python 3.10+** — optional, needed for RAG / system tools / system prompt.
  Install it system-wide, **or** use the built-in portable distribution:
  Launcher menu **[4] Download models → [p] Portable Python** (~10 MB,
  unpacks to `Files\python\`, fully self-contained, leaves no trace on host PC).

## Project Structure

```
USBClaw/
├── Start_Windows.bat          Windows launcher with interactive menu
├── Files/
│   ├── llama/
│   │   └── win/               llama-server.exe + DLLs
│   ├── python/                Portable Python (optional, via launcher menu)
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
