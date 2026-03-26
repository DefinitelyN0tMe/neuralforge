#!/bin/bash
set -e

# ─── NeuralForge Installer ────────────────────────────────────────
PANEL_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  NeuralForge — Installer"
echo "  Directory: $PANEL_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── Check requirements ──────────────────────────────────────────
echo ""
echo "Checking requirements..."

# Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 not found. Install: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  ✅ Python $PY_VER"

# GPU
if command -v nvidia-smi &>/dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
    echo "  ✅ GPU: $GPU_NAME (${GPU_MEM}MB)"
else
    echo "  ⚠️  nvidia-smi not found — GPU features won't work"
fi

# Docker
if command -v docker &>/dev/null; then
    echo "  ✅ Docker $(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)"
else
    echo "  ⚠️  Docker not found — Qdrant/Searxng won't work (sudo apt install docker.io)"
fi

# ffmpeg
if command -v ffmpeg &>/dev/null; then
    echo "  ✅ ffmpeg"
else
    echo "  ⚠️  ffmpeg not found — voice features won't work (sudo apt install ffmpeg)"
fi

# Ollama
if command -v ollama &>/dev/null || curl -s http://localhost:11434/api/version &>/dev/null; then
    echo "  ✅ Ollama"
else
    echo "  ⚠️  Ollama not found — install: curl -fsSL https://ollama.com/install.sh | sh"
fi

# ─── Create venv ─────────────────────────────────────────────────
echo ""
if [ ! -d "$PANEL_DIR/venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PANEL_DIR/venv"
fi

echo "Installing Python dependencies..."
"$PANEL_DIR/venv/bin/pip" install -q --upgrade pip
"$PANEL_DIR/venv/bin/pip" install -q \
    fastapi uvicorn[standard] pyyaml psutil docker pillow fpdf2 \
    telethon cryptography gradio_client faster-whisper mcp

echo "  ✅ Dependencies installed"

# ─── Patch paths ─────────────────────────────────────────────────
echo ""
echo "Patching paths to $PANEL_DIR ..."

# Replace the original dev paths with current install dir
ORIG_PATH="/home/definitelynotme/Desktop/ai-panel"
if [ "$PANEL_DIR" != "$ORIG_PATH" ]; then
    for f in server.py telegram_bot.py mcp_server.py pipeline.py smm/routes.py run_mcp.sh backup.sh; do
        if [ -f "$PANEL_DIR/$f" ]; then
            sed -i "s|$ORIG_PATH|$PANEL_DIR|g" "$PANEL_DIR/$f"
        fi
    done
    # Patch module YAML configs
    for f in "$PANEL_DIR"/modules/*.yaml; do
        if [ -f "$f" ]; then
            sed -i "s|$ORIG_PATH|$PANEL_DIR|g" "$f"
        fi
    done
    echo "  ✅ Paths patched"
else
    echo "  ✅ Paths already correct"
fi

# ─── Config ──────────────────────────────────────────────────────
if [ ! -f "$PANEL_DIR/telegram_config.json" ]; then
    cp "$PANEL_DIR/telegram_config.example.json" "$PANEL_DIR/telegram_config.json"
    echo "  ✅ Created telegram_config.json (edit api_id and api_hash)"
fi

# ─── Directories ─────────────────────────────────────────────────
mkdir -p "$PANEL_DIR/telegram_sessions"
mkdir -p "/home/$USER/Desktop/pipeline_output" 2>/dev/null || true

# ─── Systemd service (optional) ─────────────────────────────────
echo ""
read -p "Create systemd service for auto-start? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    SERVICE_FILE="/etc/systemd/system/ai-panel.service"
    sudo tee "$SERVICE_FILE" > /dev/null << EOF
[Unit]
Description=NeuralForge
After=network.target docker.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$PANEL_DIR
ExecStart=$PANEL_DIR/venv/bin/python3 -u server.py
Restart=on-failure
RestartSec=5
Environment=HOME=/home/$USER

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl daemon-reload
    sudo systemctl enable ai-panel
    sudo systemctl start ai-panel
    echo "  ✅ Service created and started"
    echo "     Manage: sudo systemctl {start|stop|restart|status} ai-panel"
else
    echo "  To run manually: source venv/bin/activate && python3 server.py"
fi

# ─── Done ────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ Installation complete!"
echo ""
echo "  Panel:     http://localhost:9000"
echo "  Config:    $PANEL_DIR/telegram_config.json"
echo "  Modules:   $PANEL_DIR/modules/*.yaml"
echo ""
echo "  Next steps:"
echo "    1. Install Ollama:  curl -fsSL https://ollama.com/install.sh | sh"
echo "    2. Pull a model:    ollama pull qwen3.5:35b-a3b"
echo "    3. Start Qdrant:    docker run -d -p 6333:6333 qdrant/qdrant"
echo "    4. Open panel:      http://localhost:9000"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
