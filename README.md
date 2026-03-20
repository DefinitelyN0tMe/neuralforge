<p align="center">
  <h1 align="center">AI Control Panel</h1>
  <p align="center">
    <strong>Your entire AI stack. One dashboard. Zero cloud.</strong>
  </p>
  <p align="center">
    LLMs &bull; Agents &bull; RAG &bull; Image/Video/3D &bull; Telegram Bot &bull; Voice Cloning &bull; Fine-Tuning
  </p>
  <p align="center">
    <a href="#-quick-start"><img src="https://img.shields.io/badge/Quick_Start-blue?style=for-the-badge" alt="Quick Start"></a>
    <a href="#-features-at-a-glance"><img src="https://img.shields.io/badge/Features-purple?style=for-the-badge" alt="Features"></a>
    <a href="#-telegram-ai-bot"><img src="https://img.shields.io/badge/Telegram_Bot-green?style=for-the-badge" alt="Telegram Bot"></a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/Ollama-000000?logo=ollama&logoColor=white" alt="Ollama">
    <img src="https://img.shields.io/badge/NVIDIA-CUDA-76B900?logo=nvidia&logoColor=white" alt="CUDA">
    <img src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white" alt="Docker">
    <img src="https://img.shields.io/badge/Ubuntu-22.04+-E95420?logo=ubuntu&logoColor=white" alt="Ubuntu">
    <img src="https://img.shields.io/github/license/DefinitelyN0tMe/ai-panel" alt="License">
    <img src="https://img.shields.io/github/stars/DefinitelyN0tMe/ai-panel?style=social" alt="Stars">
  </p>
</p>

---

## What is this?

A self-hosted web panel (`localhost:9000`) that puts your **entire local AI infrastructure** under one roof. No subscriptions, no API keys, no data leaving your machine.

```
┌─────────────────────────────── AI Control Panel ───────────────────────────────┐
│                                                                                │
│   Dashboard        Agents          RAG           Telegram        LoRA          │
│   ┌──────────┐    ┌──────────┐   ┌──────────┐  ┌──────────┐   ┌──────────┐   │
│   │ GPU/VRAM │    │ 13 Roles │   │ Qdrant + │  │ 14 Meme  │   │ Unsloth  │   │
│   │ Services │    │ Solo     │   │ ONNX GPU │  │ Personas │   │ LoRA     │   │
│   │ Metrics  │    │ Team     │   │ 1800/sec │  │ Voice    │   │ 16 base  │   │
│   │ Alerts   │    │ Orchestr │   │ Multi-DB │  │ Cloning  │   │ models   │   │
│   └──────────┘    └──────────┘   └──────────┘  └──────────┘   └──────────┘   │
│                                                                                │
│   Pipeline: Image ──→ Video ──→ 3D    │    MCP Server: 24 tools for Claude    │
│   (ComfyUI)  (Wan2GP)  (Hunyuan3D)    │    + Music, TTS, STT, Search...      │
└────────────────────────────────────────────────────────────────────────────────┘
```

<br>

## Features at a Glance

| | Feature | Description |
|:---:|---|---|
| **GPU** | Smart VRAM Management | Exclusive groups auto-stop conflicting services. Never OOM again |
| **Dashboard** | Real-time Monitoring | GPU temp, VRAM, RAM, CPU, disk — live metrics with health alerts |
| **Agents** | Multi-Agent Orchestration | 13 roles, 3 modes (Solo/Team/Orchestrator), shared memory, RAG tools |
| **RAG** | Vector Search at GPU Speed | ONNX embeddings at 1,800 docs/sec, Qdrant DB, multi-collection search |
| **Bot** | 14 Telegram Personas | Each with unique personality — from Philosopher to Crypto Maniac |
| **Voice** | Real-time Voice Cloning | Send voice → get reply in *your own voice* with AI-generated text |
| **LoRA** | Fine-Tuning UI | 16 base models, dataset upload, live training output, adapter export |
| **Gen** | Image→Video→3D Pipeline | Automated chain with smart VRAM switching between steps |
| **MCP** | Claude Code Integration | 24 tools — let Claude manage your entire AI stack |
| **Ext** | YAML Module System | Add any new service in 10 lines of YAML |

<br>

## Dashboard

The main hub. Everything starts here.

**Live Metrics:**
- GPU VRAM usage with free memory indicator
- GPU temperature and power draw
- RAM usage with available memory
- CPU load across all threads
- Disk usage with free space alerts

**Service Management:**
- Start/stop any service with one click
- **Exclusive GPU groups** — when you start ComfyUI, Wan2GP auto-stops (and vice versa). No more VRAM crashes
- Service health indicators (running/stopped/starting)
- Quick actions: "Start basics", "Stop heavy", "Free VRAM"

**Monitoring:**
- Active Ollama models with per-model VRAM usage
- GPU process list (what's eating your VRAM right now)
- Qdrant RAG collections with vector counts
- Storage breakdown by service (ComfyUI outputs, Wan2GP videos, etc.)
- Health alerts: GPU overheating, low disk, service down — all visible at a glance

**YAML Module System — add any service:**
```yaml
name: My New Service
category: generation
start_cmd: "python3 app.py --port 7777"
port: 7777
vram_estimate: "4-8 GB"
exclusive_group: heavy_gpu    # auto-stops conflicting services
```
Drop it in `modules/` → restart panel → it appears. That's it.

<br>

## AI Agents

A full multi-agent framework built into the panel.

**13 Role Presets:**

| Role | What it does | Default model |
|------|-------------|---------------|
| Researcher | Web search, source analysis, fact compilation | Qwen 3.5 35B |
| Analyst | Data analysis, pattern recognition, insights | Qwen 3.5 35B |
| Coder | Write, debug, refactor code in any language | Qwen 3.5 35B |
| Writer | Articles, reports, creative writing | Qwen 3.5 35B |
| Critic | Quality review, scoring, improvement suggestions | Qwen 3.5 35B |
| Summarizer | Condense long texts into key points | Mistral Small 24B |
| Translator | Multi-language translation with context | Mistral Small 24B |
| Email Writer | Professional emails from brief instructions | Mistral Small 24B |
| Tester | Generate test cases, find edge cases | Qwen 3.5 35B |
| Trade Analyst | Market analysis, trend identification | Qwen 3.5 35B |
| Tutor | Explain concepts at adjustable complexity | Qwen 3.5 35B |
| Security Auditor | Code/config security review, vulnerability scan | Qwen 3.5 35B |
| Image Analyst | Describe and analyze images | Qwen Vision 27B |

**3 Execution Modes:**

| Mode | How it works | Best for |
|------|-------------|----------|
| **Solo** | Single agent with tools | Quick tasks, Q&A |
| **Team** | Agent chain — each passes context to next | Complex multi-step tasks |
| **Orchestrator** | AI creates plan → delegates to agents → reviews result (retries if score < 7) | Ambitious tasks with quality control |

**15 Team Presets:**
Pre-configured agent chains for common workflows — "Research → Analyze → Write", "Code → Test → Review", "Translate → Edit", and more.

**Agent Tools:**
- `web_search` — search the internet
- `read_url` / `deep_scrape` — fetch and parse web pages
- `run_python` — execute Python code
- `read_file` / `write_file` — file operations
- `analyze_image` — vision model for images
- `rag_search` — search your vector database
- `analyze_file` — PDF/CSV/code analysis

**Memory System:**
- Shared memory between agents in a team
- Long-term memory with keyword tokenization and search
- Context passing modes: full chain or previous-agent-only

<br>

## RAG (Retrieval-Augmented Generation)

Ask questions about your documents. The AI retrieves relevant passages and answers with citations.

**Performance:**
| Method | Speed | GPU VRAM |
|--------|-------|----------|
| ONNX GPU (bge-m3) | **1,800 texts/sec** | ~2 GB |
| Ollama embeddings | 10 texts/sec | ~4 GB |

That's **180x faster** indexing with ONNX.

**Capabilities:**
- **Multi-format indexing** — PDF, TXT, MD, DOCX, CSV, HTML
- **Batch processing** — index entire directories recursively
- **Multi-collection** — separate databases for different topics (e.g., "laws", "docs", "codebase")
- **Smart search** — auto-detects which collection to search based on query
- **Context memory** — remembers previous Q&A in the same chat session
- **Embedding cache** — repeat queries are instant

**Built-in chat interface:**
- Markdown rendering with syntax highlighting
- Copy button on every response
- Export conversation to Markdown file
- Collection selector and search settings
- localStorage persistence — your chat survives page reload

**Example use case:**
> Indexed all 390 Estonian laws (52,314 vectors) — now ask legal questions in any language and get answers with article references.

<br>

## LoRA Fine-Tuning

Train custom model adapters directly from the panel UI.

**16 Base Models Ready to Fine-Tune:**

| Model | Size | Notes |
|-------|------|-------|
| Llama 3.1 | 8B | Great all-rounder |
| Llama 3.2 | 1B / 3B | Lightweight, fast |
| Mistral v0.3 | 7B | Strong reasoning |
| Qwen 2.5 | 7B / 32B | Multilingual |
| Gemma 2 | 2B / 9B / 27B | Google's latest |
| Phi 3.5 | 3.8B | Microsoft, compact |
| + custom | any | Enter any Unsloth-compatible model ID |

**Training UI Features:**
- Dataset upload (JSON, JSONL, CSV) or HuggingFace dataset ID
- Auto-format detection (instruction/output, messages, or raw text)
- Configurable: LoRA rank, alpha, epochs, batch size, learning rate, max sequence length
- **Live training output** — see loss, progress, ETA in real-time
- Timer showing elapsed training time
- Stop button to cancel mid-training
- Trained adapters listed with size and date

**Powered by [Unsloth](https://github.com/unslothai/unsloth)** — 2x faster training, 60% less memory than standard LoRA.

<br>

## Generation Pipeline

Automated **Image → Video → 3D** chain with smart VRAM management between steps.

| Step | Engine | VRAM | Automation |
|------|--------|------|------------|
| Image | ComfyUI (FLUX Klein 4B) | 8-12 GB | Fully automated API |
| Video | Wan2GP (Wan 2.2 / LTX) | 12-24 GB | Gradio API + manual fallback |
| 3D | Hunyuan3D | 13-20 GB | Gradio API + manual fallback |

VRAM is automatically freed between steps — only one heavy service runs at a time.

```bash
# 5 built-in examples
python3 pipeline.py --example robot     # chibi robot → animate → 3D model
python3 pipeline.py --example dragon    # crystal dragon → animate → 3D
python3 pipeline.py --example car       # cyberpunk car → animate → 3D
python3 pipeline.py --example cat       # cat astronaut → animate → 3D
python3 pipeline.py --example sword     # magic sword → 3D (skip video)

# Custom prompt
python3 pipeline.py "a golden crown with gems" --steps image,3d
python3 pipeline.py "a phoenix" --video-prompt "spreads wings and flies"
```

<br>

## Telegram AI Bot

Not a Telegram bot — responds **from your own account** via Telethon User API.

**14 Unique Personas:**

| | Persona | Style |
|:---:|---|---|
| 🧘 | **Philosopher** | *"You wrote 'hi', but what is a greeting if not a scream of loneliness into the void?"* |
| 🧢 | **Gopnik-Intellectual** | *"bro, your argument is logically inconsistent, purely by Kant"* |
| 👾 | **IT Demon** | *"segfault in your logic, recompile that thought"* |
| 👵 | **Granny from 2077** | *"sweetie, browsing without a firewall again? you'll catch a virus!"* |
| 🕵️ | **Noir Detective** | *"The message came at 3am. Like all bad news in this city"* |
| 🏴‍☠️ | **Pirate Nerd** | *"arrr, your meme is a true treasure!"* |
| 🐱 | **Cat Tyrant** | *"I'd help, but I need to lie down for 14 more hours"* |
| 🔺 | **Conspiracist** | *"Telegram was created by Masons to track memes"* |
| 🎭 | **Budget Shakespeare** | *"To be online or not to be — that is the question!"* |
| 🧟 | **Zombie Gentleman** | *"good evening, could you... share some brains?"* |
| 📋 | **Corporate Robot** | *"let's sync on this in the next sprint"* |
| 🫎 | **Capybara** | *"why stress when you can just... not"* + random capybara photo |
| 🚀 | **Crypto Maniac** | *"RED CANDLE, I'M BANKRUPT, wait... GREEN! I'M RICH!"* |
| 🛠️ | **Custom** | Write your own character |

**Voice Clone Pipeline:**
```
🎤 Voice in → ffmpeg (OGG→WAV) → Whisper STT → LLM response
  → unload LLM → Qwen3-TTS (clone voice) → ffmpeg (WAV→OGG) → 🔊 Voice out
```

**Features:**
- Auto-detects language → responds in same language
- Conversation memory (5 exchanges per user)
- Session-based logs grouped by contact
- Voice clone toggle from panel UI
- Capybara persona sends random capybara photos via [capy.lol](https://capy.lol) API

<br>

## MCP Server — Claude Code Integration

24 tools that let Claude Code directly manage your AI infrastructure:

| Category | Tools |
|----------|-------|
| **System** | `get_system_status` `get_gpu_processes` `ollama_loaded_models` `check_health` |
| **Services** | `start_service` `stop_service` `stop_all_and_free_vram` |
| **RAG** | `rag_search` `rag_list_collections` `rag_index_file` `rag_index_directory` `ask_rag` |
| **Agents** | `run_agent` `run_agent_team` `run_orchestrator` |
| **Generate** | `generate_image` `run_pipeline` |
| **Fine-tune** | `finetune_start` `finetune_status` `finetune_stop` |
| **Utils** | `get_storage_info` `cleanup_storage` `run_backup` `convert_audio` |

```json
// Add to your project's .mcp.json
{ "mcpServers": { "ai-panel": { "command": "/path/to/ai-panel/run_mcp.sh" } } }
```

Now Claude can: check GPU status, start services, search your RAG database, run agent teams, generate images, manage fine-tuning — all from natural language.

<br>

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/DefinitelyN0tMe/ai-panel.git
cd ai-panel
chmod +x install.sh
./install.sh
```

### 2. Get an LLM running

```bash
curl -fsSL https://ollama.com/install.sh | sh

# Pick a model for your VRAM
ollama pull qwen3.5:35b-a3b      # 20GB VRAM — powerful
ollama pull nemotron-3-nano:30b   # 18GB VRAM — balanced
ollama pull mistral-small:24b     # 14GB VRAM — lighter
```

### 3. Start support services

```bash
# Qdrant for RAG (optional)
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant
```

### 4. Open the panel

```
http://localhost:9000
```

<br>

## Requirements

| Component | Minimum | Recommended | Tested on |
|-----------|---------|-------------|-----------|
| **GPU** | NVIDIA 12GB VRAM | 24GB VRAM | RTX 3090 24GB |
| **RAM** | 16 GB | 64+ GB | 128 GB DDR4 |
| **Disk** | 50 GB free | 200+ GB | 2TB NVMe |
| **CPU** | 4 cores | 16+ cores | Threadripper PRO 5955WX |
| **OS** | Ubuntu 22.04 | Ubuntu 24.04 | Ubuntu 24.04.2 |
| **Python** | 3.10 | 3.12 | 3.12.3 |

Also needed: NVIDIA drivers, CUDA, Docker, ffmpeg, Ollama

<br>

## Architecture

```
Browser ◄──────► FastAPI server.py :9000 ◄──────► Ollama :11434
                      │                              (LLM inference)
                      ├──► Module Manager
                      │     ├── ComfyUI :8188        (image gen)
                      │     ├── Wan2GP :7860          (video gen)
                      │     ├── Hunyuan3D :7870       (3D gen)
                      │     ├── ACE-Step :7880        (music gen)
                      │     ├── Qwen3-TTS :7890       (voice clone)
                      │     ├── Whisper :7895          (speech-to-text)
                      │     └── ... (add your own via YAML)
                      │
                      ├──► Qdrant :6333               (vector DB for RAG)
                      ├──► Telegram Bot               (Telethon user API)
                      └──► MCP Server                 (Claude Code bridge)

telegram_bot.py ◄──► Ollama (text) + Whisper (STT) + Qwen3-TTS (voice clone)
pipeline.py     ◄──► ComfyUI → Wan2GP → Hunyuan3D (sequential, VRAM-managed)
mcp_server.py   ◄──► server.py API (24 tools exposed to Claude Code)
```

<br>

## Project Structure

```
ai-panel/
├── server.py                  # FastAPI backend — all API endpoints
├── telegram_bot.py            # Telegram bot — personas, voice clone, STT/TTS
├── pipeline.py                # Image → Video → 3D generation pipeline
├── mcp_server.py              # MCP server — 24 tools for Claude Code
├── templates/
│   └── index.html             # Single-page frontend (vanilla JS, no framework)
├── modules/                   # YAML service definitions (drop-in)
│   ├── ollama.yaml
│   ├── comfyui.yaml
│   ├── wan2gp.yaml
│   ├── hunyuan3d.yaml
│   ├── ace-step.yaml
│   ├── qwen3-tts.yaml
│   ├── whisper-webui.yaml
│   └── ...                    # add your own!
├── install.sh                 # Automated installer with path patching
├── run_mcp.sh                 # MCP server launcher
├── backup.sh                  # Backup script
├── telegram_config.example.json
├── LICENSE
└── README.md
```

<br>

## FAQ

<details>
<summary><b>Can I use this without a GPU?</b></summary>
Partially. Ollama can run on CPU (slow). RAG chat and Telegram text personas work fine. Image/video/3D generation and voice cloning need NVIDIA GPU.
</details>

<details>
<summary><b>Will this work on WSL2 / Windows?</b></summary>
Not tested. Designed for native Ubuntu. WSL2 with CUDA passthrough might work but YMMV.
</details>

<details>
<summary><b>Can I add my own Telegram persona?</b></summary>
Yes — use "Custom" in the panel UI, or add a new key to the personas dict in telegram_config.json.
</details>

<details>
<summary><b>How much disk space do I need?</b></summary>
Panel itself is ~1MB. Models are what take space: a 30B model ≈ 18GB. Budget 50-200GB depending on models and services.
</details>

<details>
<summary><b>Is my data private?</b></summary>
100%. Everything runs locally. No telemetry, no cloud calls, no external API keys required.
</details>

<details>
<summary><b>Can I use a different LLM provider?</b></summary>
The panel is built around Ollama, but any OpenAI-compatible API on localhost would work with minor code changes.
</details>

<br>

## Contributing

PRs welcome. The codebase is intentionally simple — vanilla JS frontend, single FastAPI backend, no build step.

Good first contributions:
- New Telegram personas
- New module YAML definitions
- UI improvements
- Automated Gradio API for Wan2GP / Hunyuan3D
- Documentation / translations

<br>

## License

MIT — do whatever you want with it.

<br>

## Credits

| Project | Used for |
|---------|----------|
| [Ollama](https://ollama.com/) | Local LLM inference |
| [FastAPI](https://fastapi.tiangolo.com/) | Backend API |
| [Telethon](https://github.com/LonamiWebs/Telethon) | Telegram User API |
| [Qdrant](https://qdrant.tech/) | Vector database for RAG |
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | Image generation |
| [Wan2GP](https://github.com/deepbeepmeep/Wan2GP) | Video generation |
| [Hunyuan3D](https://github.com/Tencent/Hunyuan3D-2) | 3D model generation |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Speech recognition |
| [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | Text-to-speech & voice cloning |
| [ACE-Step](https://github.com/ace-step/ACE-Step) | Music generation |
| [Unsloth](https://github.com/unslothai/unsloth) | LoRA fine-tuning |

---

<p align="center">
  <sub>Built with obsession by <a href="https://github.com/DefinitelyN0tMe">@DefinitelyN0tMe</a> and <a href="https://claude.ai/claude-code">Claude Code</a></sub>
</p>
