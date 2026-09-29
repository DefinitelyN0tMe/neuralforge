#!/bin/bash
set -euo pipefail

# ─── NeuralForge Installer ────────────────────────────────────────
# Safe to re-run. Does not install system packages or Ollama models; it checks
# for them, builds venv/, patches hardcoded paths and (optionally) installs a
# systemd USER unit. Never creates /etc/systemd/system/ai-panel.service: a
# system unit and a user unit both binding :9000 kill each other on restart.
PANEL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="ai-panel"
USER_UNIT_DIR="$HOME/.config/systemd/user"
USER_UNIT="$USER_UNIT_DIR/$SERVICE_NAME.service"
SYSTEM_UNIT="/etc/systemd/system/$SERVICE_NAME.service"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  NeuralForge — Installer"
echo "  Directory: $PANEL_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ "$(id -u)" -eq 0 ]; then
    echo "❌ Run as your normal user, not root (sudo is only used where needed)."
    exit 1
fi

# ─── Check requirements ──────────────────────────────────────────
echo ""
echo "Checking requirements..."

# Python
if ! command -v python3 &>/dev/null; then
    echo "❌ Python 3 not found. Install: sudo apt install python3 python3-venv python3-pip"
    exit 1
fi
PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"; then
    echo "❌ Python $PY_VER found, 3.10+ required"
    exit 1
fi
echo "  ✅ Python $PY_VER"

# GPU
if command -v nvidia-smi &>/dev/null; then
    if GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1) && [ -n "$GPU_NAME" ]; then
        GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1)
        echo "  ✅ GPU: $GPU_NAME (${GPU_MEM}MB)"
    else
        echo "  ⚠️  nvidia-smi failed (driver/library version mismatch? reboot after driver upgrades)"
    fi
else
    echo "  ⚠️  nvidia-smi not found — GPU features won't work"
fi

# Docker
if command -v docker &>/dev/null; then
    echo "  ✅ Docker $(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)"
    if ! docker info &>/dev/null; then
        echo "  ⚠️  Current user can't reach the Docker daemon — add yourself to the docker group:"
        echo "      sudo usermod -aG docker \"$USER\"  (then log out and back in)"
    fi
else
    echo "  ⚠️  Docker not found — Qdrant/SearXNG won't work (sudo apt install docker.io)"
fi

# ffmpeg
if command -v ffmpeg &>/dev/null; then
    echo "  ✅ ffmpeg"
else
    echo "  ⚠️  ffmpeg not found — voice features won't work (sudo apt install ffmpeg)"
fi

# Ollama
if command -v ollama &>/dev/null || curl -s --max-time 3 http://localhost:11434/api/version &>/dev/null; then
    echo "  ✅ Ollama"
else
    echo "  ⚠️  Ollama not found — install: curl -fsSL https://ollama.com/install.sh | sh"
fi

# ─── Create venv ─────────────────────────────────────────────────
echo ""
if [ ! -x "$PANEL_DIR/venv/bin/python3" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$PANEL_DIR/venv" || {
        echo "❌ venv creation failed. Install: sudo apt install python3-venv"
        exit 1
    }
fi

echo "Installing Python dependencies..."
"$PANEL_DIR/venv/bin/pip" install -q --upgrade pip
"$PANEL_DIR/venv/bin/pip" install -q -r "$PANEL_DIR/requirements.txt"
echo "  ✅ Dependencies installed"

# ─── Patch paths ─────────────────────────────────────────────────
echo ""
echo "Patching paths to $PANEL_DIR ..."

# The code ships with the author's absolute paths. Rewrite the panel dir first,
# then the remaining home-dir references (ComfyUI, agents, outputs, ...).
ORIG_PATH="/home/definitelynotme/Desktop/NeuralForge/panel"
ORIG_HOME="/home/definitelynotme"

sed_escape() { printf '%s' "$1" | sed -e 's/[\\|&]/\\&/g'; }

PATCH_FILES=(server.py telegram_bot.py mcp_server.py pipeline.py smm/routes.py)
for f in "$PANEL_DIR"/modules/*.yaml; do
    if [ -f "$f" ]; then PATCH_FILES+=("modules/$(basename "$f")"); fi
done

patch_all() {  # $1 = from, $2 = to
    local from to f
    from=$(sed_escape "$1"); to=$(sed_escape "$2")
    for f in "${PATCH_FILES[@]}"; do
        if [ -f "$PANEL_DIR/$f" ]; then sed -i "s|$from|$to|g" "$PANEL_DIR/$f"; fi
    done
}

if [ "$PANEL_DIR" != "$ORIG_PATH" ]; then
    patch_all "$ORIG_PATH" "$PANEL_DIR"
    echo "  ✅ Panel path patched"
else
    echo "  ✅ Panel path already correct"
fi
if [ "$HOME" != "$ORIG_HOME" ]; then
    patch_all "$ORIG_HOME/" "$HOME/"
    echo "  ✅ Home path patched ($ORIG_HOME → $HOME)"
fi

# ─── Config ──────────────────────────────────────────────────────
if [ ! -f "$PANEL_DIR/telegram_config.json" ]; then
    cp "$PANEL_DIR/telegram_config.example.json" "$PANEL_DIR/telegram_config.json"
    chmod 600 "$PANEL_DIR/telegram_config.json"
    echo "  ✅ Created telegram_config.json (set API ID/Hash in the panel → Telegram tab)"
fi

# ─── Directories ─────────────────────────────────────────────────
# static/ is empty in git (so not in a fresh clone) but server.py mounts it.
mkdir -p "$PANEL_DIR/static" "$PANEL_DIR/telegram_sessions"
mkdir -p "$HOME/Desktop/NeuralForge/data/pipeline_output"

# ─── Systemd user service (optional) ────────────────────────────
echo ""
REPLY=""
read -r -p "Create systemd user service for auto-start? [y/N] " -n 1 REPLY || true
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null || systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
        echo "  ⚠️  A system unit $SYSTEM_UNIT is enabled/active. It will fight the user unit for :9000."
        echo "      Disable it first:  sudo systemctl disable --now $SERVICE_NAME"
        echo "  Skipping user unit creation."
    else
        mkdir -p "$USER_UNIT_DIR"
        cat > "$USER_UNIT" << EOF
[Unit]
Description=NeuralForge
After=network.target

[Service]
Type=simple
WorkingDirectory=$PANEL_DIR
ExecStart=$PANEL_DIR/venv/bin/python3 -u $PANEL_DIR/server.py
KillMode=control-group
TimeoutStopSec=5
Restart=on-failure
RestartSec=5
StartLimitBurst=5
StartLimitIntervalSec=60
Environment=PATH=$PANEL_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=HOME=$HOME
Environment=DOCKER_HOST=unix:///var/run/docker.sock

[Install]
WantedBy=default.target
EOF
        systemctl --user daemon-reload
        systemctl --user enable --now "$SERVICE_NAME"
        echo "  ✅ User service created and started: $USER_UNIT"
        echo "     Manage: systemctl --user {start|stop|restart|status} $SERVICE_NAME"
        echo "     Logs:   journalctl --user -u $SERVICE_NAME -f"
        if [ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != "yes" ]; then
            echo "     To keep it running after logout / start at boot: sudo loginctl enable-linger $USER"
        fi
    fi
else
    echo "  To run manually: cd \"$PANEL_DIR\" && venv/bin/python3 server.py"
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
echo "    2. Pull models:     ollama pull qwen3.6:35b-a3b   # main workhorse (~23 GB)"
echo "                        ollama pull qwen3.5:9b        # light / Telegram bot"
echo "                        ollama pull bge-m3            # RAG embeddings"
echo "       (missing models fall back to the closest installed one — model_resolver.py)"
echo "    3. Start Qdrant:    docker run -d --name qdrant --restart unless-stopped \\"
echo "                          -p 6333:6333 -v qdrant_data:/qdrant/storage qdrant/qdrant"
echo "    4. Open panel:      http://localhost:9000"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
