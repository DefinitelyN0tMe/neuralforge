<p align="center">
  <h1 align="center">🧠 NeuralForge</h1>
  <p align="center">
    <strong>Self-hosted AI command center. 11 services. 69 APIs. Zero cloud.</strong>
  </p>
  <p align="center">
    <em>LLM agents, SMM autopilot for 7 platforms, image/video/3D/music generation,<br>RAG, LoRA fine-tuning, voice cloning, Telegram bot with vision — all from localhost:9000</em>
  </p>
  <p align="center">
    <a href="#-quick-start"><img src="https://img.shields.io/badge/Quick_Start-blue?style=for-the-badge" alt="Quick Start"></a>
    <a href="#-features-at-a-glance"><img src="https://img.shields.io/badge/Features-purple?style=for-the-badge" alt="Features"></a>
    <a href="#smm-ai-department"><img src="https://img.shields.io/badge/SMM_Module-orange?style=for-the-badge" alt="SMM"></a>
    <a href="#-telegram-ai-bot"><img src="https://img.shields.io/badge/Telegram_Bot-green?style=for-the-badge" alt="Telegram Bot"></a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white" alt="FastAPI">
    <img src="https://img.shields.io/badge/Ollama-000000?logo=ollama&logoColor=white" alt="Ollama">
    <img src="https://img.shields.io/badge/NVIDIA-CUDA-76B900?logo=nvidia&logoColor=white" alt="CUDA">
    <img src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white" alt="Docker">
    <img src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white" alt="SQLite">
    <img src="https://img.shields.io/badge/Ubuntu-22.04+-E95420?logo=ubuntu&logoColor=white" alt="Ubuntu">
    <img src="https://img.shields.io/github/license/DefinitelyN0tMe/neuralforge" alt="License">
    <img src="https://img.shields.io/github/stars/DefinitelyN0tMe/neuralforge?style=social" alt="Stars">
  </p>
</p>

---

> **Why another AI dashboard?** Because no other open-source project gives you LLM orchestration, automated SMM for 7 platforms, image/video/3D generation, RAG, fine-tuning, Telegram bot with 14 personas, voice cloning, and MCP integration for Claude — all in a single self-hosted panel with zero cloud dependencies.

---

### Highlights

- **🤖 11 AI Services** managed from one UI — Ollama, ComfyUI, Whisper, Qdrant, SearXNG, and more
- **📱 SMM AI Department** — discover trends → generate posts → create images → auto-publish to Telegram, Twitter, Facebook, Instagram, Threads, LinkedIn, Discord simultaneously
- **🧠 Multi-Agent System** — 13 roles, 3 modes (Solo/Team/Orchestrator), 9 tools including web search, code execution, RAG
- **🎨 Full Generation Pipeline** — Image (FLUX) → Video (Wan2.2) → 3D (Hunyuan3D) with smart VRAM management
- **📊 69 API Endpoints** — everything is programmable, extensible, and automatable
- **🔒 100% Local** — your data never leaves your machine. No API keys required for core features

---

### Table of Contents

[What is this?](#what-is-this) · [AI Model Stack](#ai-model-stack) · [Features](#features-at-a-glance) · [Dashboard](#dashboard) · [Agents](#ai-agents) · [RAG](#rag-retrieval-augmented-generation) · [LoRA](#lora-fine-tuning) · [Pipeline](#generation-pipeline) · [Telegram Bot](#telegram-ai-bot) · [SMM](#smm-ai-department) · [MCP Server](#mcp-server--claude-code-integration) · [Quick Start](#quick-start) · [Requirements](#requirements) · [FAQ](#faq)

---

## What is this?

A self-hosted web panel (`localhost:9000`) that unifies your **entire local AI infrastructure** into one powerful dashboard. No subscriptions, no cloud APIs, no data leaving your machine.

```
┌──────────────────────────────── NeuralForge ──────────────────────────────────┐
│                                                                                │
│  Dashboard     Agents       RAG        Telegram     LoRA        SMM           │
│  ┌────────┐   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐    │
│  │GPU/VRAM│   │13 Roles│  │Qdrant +│  │14 Meme │  │Unsloth │  │7 Socials│   │
│  │Services│   │Solo    │  │ONNX GPU│  │Personas│  │LoRA    │  │Trend AI │   │
│  │Metrics │   │Team    │  │1800/sec│  │Voice   │  │16 base │  │Post Gen │   │
│  │Alerts  │   │Orchestr│  │Multi-DB│  │Cloning │  │models  │  │Analytics│   │
│  └────────┘   └────────┘  └────────┘  └────────┘  └────────┘  └────────┘    │
│                                                                                │
│  Pipeline: Image ──→ Video ──→ 3D   │   MCP Server: 24 tools for Claude      │
│  (ComfyUI)  (Wan2GP)  (Hunyuan3D)   │   + Music, TTS, STT, Search...        │
└────────────────────────────────────────────────────────────────────────────────┘
```

<br>

## AI Model Stack

Every model runs **locally via Ollama** — no API keys, no cloud, no subscriptions.

### LLMs (Text Generation & Reasoning)

| Model | Size | VRAM | Used for |
|-------|------|------|----------|
| **Qwen 3.5** | 35B (A3B MoE) | ~20 GB | Primary workhorse — agents, SMM posts, trend analysis |
| **Nemotron 3 Nano** | 30B | ~18 GB | RAG answers, balanced quality/speed |
| **Mistral Small** | 24B | ~14 GB | Summarization, translation, email |
| **Qwen 3.5** | 9B | ~6 GB | Telegram bot — fast persona responses |
| **Gemma 3** | 27B | ~16 GB | Alternative general-purpose |
| **DeepSeek R1** | 14B | ~9 GB | Math, reasoning, code |
| + 9 more | 1B–35B | 1–20 GB | User-selectable per task |

### Vision (Image Understanding)

| Model | Size | VRAM | Used for |
|-------|------|------|----------|
| **MiniCPM-V** | 8B | ~5 GB | **Telegram bot photo analysis** — describes images, answers questions about photos sent to your account |
| **Qwen2.5-VL** | 27B | ~16 GB | Agent image analysis tool — detailed visual Q&A |

### Embeddings (RAG Search)

| Model | Size | Speed | Used for |
|-------|------|-------|----------|
| **bge-m3** (ONNX) | 560M | **1,800 docs/sec** | GPU-accelerated document indexing |
| **bge-m3** (Ollama) | 560M | 10 docs/sec | Fallback CPU embedding |

### Audio (Speech & Music)

| Model | Size | VRAM | Used for |
|-------|------|------|----------|
| **Whisper** (faster-whisper) | base/large | 2-10 GB | Speech-to-text, 99 languages, diarization |
| **Qwen3-TTS** | ~4 GB | ~4 GB | Text-to-speech, **3-second voice cloning** |
| **ACE-Step 1.5** | ~4 GB | 4-6 GB | AI music generation — lyrics + style → full song |

### Image / Video / 3D Generation

| Model | Engine | VRAM | Used for |
|-------|--------|------|----------|
| **FLUX Klein** | ComfyUI | 8-12 GB | Image generation (SMM posts, pipeline) |
| **Wan 2.2** | Wan2GP | 12-24 GB | Video generation from image + prompt |
| **Hunyuan3D v2** | Gradio | 13-20 GB | 3D model generation from image |

### LoRA Fine-Tuning (16 base models)

| Model | Size | Training time |
|-------|------|---------------|
| NVIDIA Nemotron 3 Nano | 4B | ~30 min |
| Llama 3.1 / 3.2 | 1B–8B | 30 min – 2h |
| Qwen 2.5 | 7B / 32B | 1–4h |
| Gemma 2 | 2B–27B | 30 min – 3h |
| Mistral v0.3 | 7B | ~1h |
| Phi 3.5 | 3.8B | ~40 min |

> **Total unique AI models available: 30+** — all running locally, swappable per task, with automatic VRAM management.

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
| **SMM** | 7-Platform Social Media | Trend Scout → AI Post Writer → Image Gen → Auto-Publish to all platforms |
| **Ext** | YAML Module System | Add any new service in 10 lines of YAML |

<br>

## Dashboard

The main hub. Everything starts here.

<p align="center">
  <img src="screenshots/dashboard-top.png" alt="NeuralForge Dashboard — metrics, services, monitoring" width="100%">
  <img src="screenshots/dashboard-modules.png" alt="NeuralForge — 11 AI services with VRAM management" width="100%">
</p>

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

<p align="center">
  <img src="screenshots/agents.png" alt="NeuralForge Agent Constructor — 13 roles, team presets, tools" width="100%">
</p>

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

<p align="center">
  <img src="screenshots/rag.png" alt="NeuralForge RAG — document search with Qdrant and ONNX embeddings" width="100%">
</p>

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

<p align="center">
  <img src="screenshots/lora.png" alt="NeuralForge LoRA — fine-tune LLMs with Unsloth" width="100%">
</p>

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

<p align="center">
  <img src="screenshots/telegram.png" alt="NeuralForge Telegram — 14 AI personas with voice cloning and vision" width="100%">
</p>

**14 Unique Personas:**

| | Persona | Style |
|:---:|---|---|
| 🧘 | **Philosopher** | *"You wrote 'hi', but what is a greeting if not a scream of loneliness into the void?"* |
| 🧢 | **Street Philosopher** | *"bro, your argument is logically inconsistent, purely by Kant"* |
| 👾 | **IT Demon** | *"segfault in your logic, recompile that thought"* |
| 👵 | **Granny from 2077** | *"sweetie, browsing without a firewall again? you'll catch a virus!"* |
| 🕵️ | **Noir Detective** | *"The message came at 3am. Like all bad news in this city"* |
| 🏴‍☠️ | **Nerd Pirate** | *"arrr, your meme is a true treasure!"* |
| 🐱 | **Cat Overlord** | *"I'd help, but I need to lie down for 14 more hours"* |
| 🔺 | **Conspiracy Nut** | *"Telegram was created by Masons to track memes"* |
| 🎭 | **Budget Shakespeare** | *"To be online or not to be — that is the question!"* |
| 🧟 | **Polite Zombie** | *"good evening, could you... share some brains?"* |
| 📋 | **Corporate Robot** | *"let's sync on this in the next sprint"* |
| 🫎 | **Capybara** | *"why stress when you can just... not"* + random capybara photo |
| 🚀 | **Crypto Maniac** | *"RED CANDLE, I'M BANKRUPT, wait... GREEN! I'M RICH!"* |
| 🛠️ | **Custom** | Write your own character |

**Voice Clone Pipeline:**
```
🎤 Voice in → ffmpeg (OGG→WAV) → Whisper STT → LLM response
  → unload LLM → Qwen3-TTS (clone voice) → ffmpeg (WAV→OGG) → 🔊 Voice out
```

**Vision — Photo Analysis (MiniCPM-V 8B):**
```
📸 Photo in → MiniCPM-V (image description) → LLM (persona-styled response) → 💬 Reply
```
Send a photo to your account → the bot describes it through the vision model → responds in character. Toggle on/off from panel UI.

**Features:**
- **Vision mode** — understands photos via MiniCPM-V 8B (auto VRAM swap: unload LLM → load vision → analyze → unload → reload LLM)
- Auto-detects language → responds in same language
- Conversation memory (5 exchanges per user)
- Session-based logs grouped by contact
- Voice clone toggle from panel UI
- Capybara persona sends random capybara photos via [capy.lol](https://capy.lol) API

<br>

## SMM AI Department

Fully automated social media management system — from trend discovery to publishing across 7 platforms.

<p align="center">
  <img src="screenshots/smm.png" alt="NeuralForge SMM — trend scout, 7 platforms, AI post generation" width="100%">
</p>

**Complete Workflow:**
```
Trend Scout → Post Writer → Image Gen → Content Queue → Auto-Publish
    │              │             │              │              │
    ▼              ▼             ▼              ▼              ▼
 6 Sources     2-Pass LLM    ComfyUI FLUX   Schedule +     7 Platforms
 (Reddit,HN,  (Scrape→       + ffmpeg      Calendar       simultaneously
  GitHub,RSS,  Summary→       resize        view           with retry
  SearXNG,     Platform
  GoogTrends)  posts)
```

**7 Connected Platforms:**
| Platform | Auth Method | Features |
|---|---|---|
| Telegram | Bot API | Text + Photo, channel posting |
| Discord | Webhook | Text + File upload |
| Twitter/X | OAuth 1.0a | Text + Media upload (Pay-Per-Use) |
| Facebook | Page Token (permanent) | Text + Photo, Page posting |
| Instagram | Graph API via FB | Photo + Caption (via imgur) |
| Threads | Threads API | Text + Image |
| LinkedIn | OAuth 2.0 | Text + Image (3-step upload) |

**Key Features:**
- **Trend Scout v2** — Multi-source intelligence with niche routing (tech, crypto, food, fitness, art, gaming, education, business), geo-detection, CJK filtering
- **GitHub Trending** — Hybrid search (API + trending page scrape), categories (Agent/LLM/RAG/Tool), velocity ranking, "already posted" markers
- **Post Writer** — 2-pass generation: scrapes source article → LLM summary → platform-specific posts with correct tone/length/hashtags. Custom context support
- **Image Generation** — AI-generated prompts → ComfyUI FLUX Klein → auto-resize for each platform. ComfyUI auto-starts and stops (VRAM management)
- **Content Queue** — SQLite-backed, edit/duplicate/regenerate posts, schedule with date/time picker, auto-publish via background scheduler
- **Content Calendar** — Weekly view with navigation, color-coded by status
- **Batch Generation** — Generate N days of content in one click with auto-scheduling
- **Analytics** — Metrics collection from FB/IG/Threads/LinkedIn APIs, per-platform breakdown, top posts ranking
- **Token Health** — Auto-refresh for expiring tokens (Threads, LinkedIn), dashboard monitoring
- **Hashtag Manager** — Per-platform limits (Instagram 28, Twitter 3, Discord 0), auto-trim at publish
- **Publish Preview** — Review all posts + image before publishing with platform selection

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
{ "mcpServers": { "neuralforge": { "command": "/path/to/neuralforge/run_mcp.sh" } } }
```

Now Claude can: check GPU status, start services, search your RAG database, run agent teams, generate images, manage fine-tuning — all from natural language.

<br>

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/DefinitelyN0tMe/neuralforge.git
cd neuralforge
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

### 5. Set up Telegram Bot (optional)

The Telegram AI Bot runs entirely from the panel UI — no code editing required.

1. Open [t.me/BotFather](https://t.me/BotFather) → `/newbot` → get your **Bot Token**
2. Get your Telegram **API ID** and **API Hash** from [my.telegram.org](https://my.telegram.org)
3. In the panel → **Telegram** tab → paste your credentials → click **Start**
4. The bot comes with 14 pre-configured personas (Philosopher, Crypto Maniac, etc.) — customize or create your own

### 6. Set up SMM Publishing (optional)

Publish AI-generated posts to 7 social networks. All configuration is done through the panel UI.

1. In the panel → **SMM** tab → **+ New Profile** → follow the 4-step wizard
2. On Step 2 (Platforms), each platform has built-in setup instructions:
   - **Telegram**: Create bot via @BotFather → paste token + channel
   - **Discord**: Server Settings → Integrations → Webhooks → copy URL
   - **Twitter/X**: [developer.x.com](https://developer.x.com) → Create App → OAuth 1.0a keys
   - **Facebook**: [developers.facebook.com](https://developers.facebook.com) → Create App (Business) → Page Token
   - **Instagram**: Same Meta app → connect IG Business Account to FB Page
   - **Threads**: Meta Developer App → Threads API → authorize
   - **LinkedIn**: [linkedin.com/developers](https://linkedin.com/developers) → Create App → OAuth 2.0
3. Scan trends → Generate posts → Publish to all platforms with one click

> **Tip:** Start with just Telegram + Discord (easiest, no API keys needed beyond bot token/webhook). Add other platforms later.

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
neuralforge/
├── server.py                  # FastAPI backend (69 API endpoints)
├── telegram_bot.py            # Telegram bot — 14 personas, voice clone, vision
├── pipeline.py                # Image → Video → 3D generation pipeline
├── mcp_server.py              # MCP server — 24 tools for Claude Code
├── smm/                       # SMM AI Department (modular package)
│   ├── __init__.py            # Router registration
│   ├── routes.py              # All SMM routes + scheduler + publishing
│   └── db.py                  # SQLite: queue, trends, analytics
├── templates/
│   └── index.html             # Single-page frontend (vanilla JS, no framework)
├── modules/                   # YAML service definitions (drop-in)
│   ├── ollama.yaml            # LLM inference
│   ├── comfyui.yaml           # Image generation
│   ├── wan2gp.yaml            # Video generation
│   ├── hunyuan3d.yaml         # 3D model generation
│   ├── ace-step.yaml          # Music generation
│   ├── qwen3-tts.yaml         # Text-to-speech + voice cloning
│   ├── whisper-webui.yaml     # Speech recognition
│   └── ...                    # add your own!
├── install.sh                 # Automated installer with path patching
├── requirements.txt           # Python dependencies
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

<details>
<summary><b>Which LLM models are supported?</b></summary>
Any model available through Ollama — Qwen, Mistral, Llama, Gemma, DeepSeek, Phi, Nemotron, and 100+ more. The panel ships with 15 pre-configured models. You can add any Ollama model through the UI.
</details>

<details>
<summary><b>How does the Telegram bot analyze photos?</b></summary>
When Vision mode is enabled, the bot uses MiniCPM-V (8B) to understand photos sent to your account. It automatically swaps VRAM: unloads the chat LLM → loads the vision model → analyzes the image → unloads vision → reloads the chat LLM. All automatic.
</details>

<details>
<summary><b>Can I use this for commercial social media management?</b></summary>
Yes. The SMM module supports 7 platforms, batch content generation, scheduled publishing, and analytics. It's designed for professional use — but you'll need API access for each platform (some are free, some require developer accounts).
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
| [Ollama](https://ollama.com/) | Local LLM inference (Qwen, Mistral, Gemma, DeepSeek, Nemotron) |
| [FastAPI](https://fastapi.tiangolo.com/) | Backend API (69 endpoints) |
| [Telethon](https://github.com/LonamiWebs/Telethon) | Telegram User API |
| [Qdrant](https://qdrant.tech/) | Vector database for RAG |
| [bge-m3](https://huggingface.co/BAAI/bge-m3) | Multilingual embeddings (ONNX GPU-accelerated) |
| [MiniCPM-V](https://huggingface.co/openbmb/MiniCPM-V-2_6) | Vision model — Telegram photo analysis |
| [ComfyUI](https://github.com/comfyanonymous/ComfyUI) | Image generation (FLUX Klein) |
| [Wan2GP](https://github.com/deepbeepmeep/Wan2GP) | Video generation (Wan 2.2, LTX-Video) |
| [Hunyuan3D](https://github.com/Tencent/Hunyuan3D-2) | 3D model generation |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Speech recognition (99 languages) |
| [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) | Text-to-speech & 3-second voice cloning |
| [ACE-Step](https://github.com/ace-step/ACE-Step) | Music generation |
| [Unsloth](https://github.com/unslothai/unsloth) | LoRA fine-tuning (2x faster, 60% less memory) |
| [SearXNG](https://github.com/searxng/searxng) | Privacy-first meta-search for AI agents |
| [Perplexica](https://github.com/ItzCrazyKns/Perplexica) | AI-powered search engine |
| [Open WebUI](https://github.com/open-webui/open-webui) | Chat interface for LLM models |

---

<p align="center">
  <sub>Built with obsession by <a href="https://github.com/DefinitelyN0tMe">@DefinitelyN0tMe</a> and <a href="https://claude.ai/claude-code">Claude Code</a></sub>
  <br><br>
  <sub><b>Keywords:</b> self-hosted AI, local LLM, AI dashboard, Ollama GUI, AI agents, multi-agent system, social media automation, SMM AI, Telegram bot, voice cloning, RAG, vector search, LoRA fine-tuning, image generation, video generation, 3D generation, MCP server, Claude Code, FLUX, ComfyUI, Whisper, text-to-speech, VRAM management, GPU dashboard, AI control panel, open source AI platform</sub>
</p>
