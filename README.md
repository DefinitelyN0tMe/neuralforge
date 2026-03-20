# AI Control Panel

**Local AI workstation dashboard** — manage LLMs, agents, RAG, image/video/3D generation, Telegram AI bot, and LoRA fine-tuning from a single web interface.

Built for Ubuntu machines with NVIDIA GPU. Runs entirely on your hardware, no cloud APIs needed.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Ubuntu%2022.04%2B-orange)

---

## What is this?

A unified control panel (`localhost:9000`) for managing a full local AI stack:

- **Dashboard** — real-time GPU/VRAM/RAM/CPU monitoring, service management, VRAM-aware exclusive groups
- **Agents** — multi-agent orchestration (Solo / Team / Orchestrator) with 13 role presets
- **RAG** — vector search over your documents via Qdrant + ONNX GPU embeddings
- **Telegram** — AI-powered auto-responder from your own account with 14 meme personas, voice cloning, multilingual support
- **LoRA** — fine-tuning UI for LLMs via Unsloth
- **Pipeline** — Image → Video → 3D generation chain with smart VRAM switching
- **MCP Server** — 24 tools for Claude Code integration

## Features

### Service Management
- Start/stop services with one click (Ollama, ComfyUI, Wan2GP, Hunyuan3D, ACE-Step, Whisper, TTS, etc.)
- **Exclusive GPU groups** — heavy services auto-stop each other to prevent VRAM overflow
- Real-time VRAM/GPU temperature/RAM monitoring with alerts
- YAML-based module system — add new services in seconds

### Telegram AI Bot
- Responds **from your own account** (Telethon User API, not a bot)
- **14 unique meme personas**: Philosopher, Gopnik-Intellectual, IT Demon, Granny from 2077, Noir Detective, Pirate Nerd, Cat Tyrant, Conspiracist, Budget Shakespeare, Zombie Gentleman, Corporate Robot, Capybara (sends random capybara photos!), Crypto Maniac, + custom
- **Multilingual** — auto-detects language and responds in the same language
- **Voice clone mode** — receives voice message → STT (Whisper) → AI response → TTS with sender's cloned voice (Qwen3-TTS) → sends back as voice message
- Conversation context (remembers last 5 exchanges per user)
- Session-based message logs grouped by contact
- Configurable cooldown, response length, blacklist/whitelist

### AI Agents
- 13 role presets: researcher, analyst, coder, writer, critic, translator, and more
- 3 execution modes: **Solo** (single agent), **Team** (agent chain with shared memory), **Orchestrator** (AI plans → delegates → reviews)
- RAG-aware tools, web search, file analysis, image recognition
- Long-term memory with keyword search

### RAG (Retrieval-Augmented Generation)
- ONNX GPU embeddings (bge-m3, 1024 dims) — 1,800 texts/sec
- Qdrant vector database
- Multi-collection search with context memory
- PDF/TXT/MD/DOCX file indexing

### Generation Pipeline
- **Image** → ComfyUI (FLUX Klein 4B) — fully automated via API
- **Video** → Wan2GP (Wan 2.2 / LTX-Video) — Gradio API with manual fallback
- **3D** → Hunyuan3D — Gradio API with manual fallback
- Smart VRAM management between pipeline steps
- 5 ready-to-use example prompts

### MCP Server (Claude Code Integration)
24 tools accessible from Claude Code:
- System monitoring, service management, VRAM control
- RAG search/indexing, agent execution
- Image generation, pipeline orchestration
- Storage management, backups

## Requirements

### Hardware
- **GPU**: NVIDIA with 12+ GB VRAM (tested on RTX 3090 24GB)
- **RAM**: 32+ GB recommended (tested on 128GB)
- **Disk**: 100+ GB free for models
- **CPU**: any modern multi-core

### Software
- Ubuntu 22.04+ (or compatible Linux)
- Python 3.10+
- NVIDIA drivers + CUDA
- Docker (for Qdrant, Searxng, etc.)
- Ollama
- ffmpeg

## Installation

```bash
# Clone
git clone https://github.com/DefinitelyN0tMe/ai-panel.git
cd ai-panel

# Run installer
chmod +x install.sh
./install.sh
```

The installer will:
1. Check system requirements (GPU, Python, Docker, ffmpeg)
2. Create Python virtual environment and install dependencies
3. Patch all paths to your installation directory
4. Create systemd service for auto-start
5. Generate config templates

### Post-install

```bash
# Install Ollama (if not installed)
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model
ollama pull qwen3.5:35b-a3b    # or any model you prefer
ollama pull nemotron-3-nano:30b  # lighter alternative

# Start Qdrant (for RAG)
docker run -d --name qdrant -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant

# Open the panel
xdg-open http://localhost:9000
```

### Telegram Bot Setup

1. Get API credentials at https://my.telegram.org/apps
2. Copy and edit the config:
   ```bash
   cp telegram_config.example.json telegram_config.json
   # Edit api_id and api_hash
   ```
3. Run the bot once manually to authenticate:
   ```bash
   source venv/bin/activate
   python3 telegram_bot.py
   # Enter your phone number and code when prompted
   ```
4. After that, start/stop from the panel UI

## Usage

### Web Panel
Open `http://localhost:9000` — everything is managed from here.

### Pipeline CLI
```bash
# Full pipeline with example
source venv/bin/activate
python3 pipeline.py --example robot

# Just image generation
python3 pipeline.py "a dragon in crystal cave" --steps image

# List examples
python3 pipeline.py --list-examples
```

### MCP Server (for Claude Code)
Add to your project's `.mcp.json`:
```json
{
  "mcpServers": {
    "ai-panel": {
      "command": "/path/to/ai-panel/run_mcp.sh"
    }
  }
}
```

## Project Structure

```
ai-panel/
├── server.py              # FastAPI backend — all API endpoints
├── telegram_bot.py        # Telegram auto-responder with personas
├── pipeline.py            # Image → Video → 3D pipeline
├── mcp_server.py          # MCP server for Claude Code (24 tools)
├── templates/
│   └── index.html         # Single-page frontend (vanilla JS)
├── modules/               # YAML service definitions
│   ├── ollama.yaml
│   ├── comfyui.yaml
│   ├── wan2gp.yaml
│   ├── hunyuan3d.yaml
│   ├── ace-step.yaml
│   ├── qwen3-tts.yaml
│   ├── whisper-webui.yaml
│   └── ...
├── install.sh             # Automated installer
├── run_mcp.sh             # MCP server launcher
├── backup.sh              # Backup script
└── telegram_config.example.json
```

## Adding New Services

Create a YAML file in `modules/`:

```yaml
name: My Service
category: generation
icon: sparkles
description: "What it does"
type: process
work_dir: "/path/to/service"
venv: "/path/to/service/venv"
start_cmd: "python3 app.py --port 7777"
process_pattern: "app.py.*7777"
port: 7777
url: "http://localhost:7777"
vram_estimate: "4-8 GB"
exclusive_group: heavy_gpu    # or null
autostart: false
```

Restart the panel — the service appears automatically.

## License

MIT — use it however you want.

## Credits

Built with:
- [Ollama](https://ollama.com/) — local LLM inference
- [Telethon](https://github.com/LonamiWebs/Telethon) — Telegram User API
- [Qdrant](https://qdrant.tech/) — vector database
- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) — image generation
- [Wan2GP](https://github.com/deepbeepmeep/Wan2GP) — video generation
- [Hunyuan3D](https://github.com/Tencent/Hunyuan3D-2) — 3D generation
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — speech recognition
- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS) — text-to-speech & voice cloning
- [Unsloth](https://github.com/unslothai/unsloth) — LoRA fine-tuning
