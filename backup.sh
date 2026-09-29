#!/bin/bash
# NeuralForge Backup Script
# Backs up panel state (configs, secrets, Telegram session, SMM + metrics DBs,
# SMM profiles/queue/trends), panel code, agent scripts + memory, ComfyUI
# workflows, systemd units, container configs and the Ollama model list.
#
# Usage:   ./backup.sh                 (archives go to $NF_BACKUP_DIR, default ~/Desktop/ai-backups)
#          NF_BACKUP_KEEP=10 ./backup.sh
# Restore: see RESTORE.txt inside each archive.
#
# Archives contain API keys and a logged-in Telegram session — they are created
# with mode 600. Keep them private.
set -uo pipefail
umask 077

PANEL_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
BACKUP_DIR="${NF_BACKUP_DIR:-$HOME/Desktop/ai-backups}"
KEEP="${NF_BACKUP_KEEP:-5}"
AGENTS_DIR="${NF_AGENTS_DIR:-$HOME/Desktop/Claude_Test/agents}"
COMFYUI_DIR="${NF_COMFYUI_DIR:-$HOME/Desktop/ComfyUI}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
NAME="backup_$TIMESTAMP"
ARCHIVE="$BACKUP_DIR/$NAME.tar.gz"
PY="$PANEL_DIR/venv/bin/python3"
[ -x "$PY" ] || PY=python3

mkdir -p "$BACKUP_DIR" || { echo "❌ Cannot create $BACKUP_DIR"; exit 1; }
STAGE=$(mktemp -d "$BACKUP_DIR/.staging_XXXXXX") || { echo "❌ mktemp failed"; exit 1; }
OUT="$STAGE/$NAME"
mkdir -p "$OUT"
cleanup() { [ -n "${STAGE:-}" ] && [ -d "$STAGE" ] && rm -rf -- "$STAGE"; }
trap cleanup EXIT

echo "🔄 NeuralForge Backup — $TIMESTAMP"
echo ""

# Consistent copy of a SQLite DB (handles WAL / live writers) via the backup API.
sqlite_copy() {  # $1 = src, $2 = dest
    [ -f "$1" ] || return 0
    "$PY" - "$1" "$2" <<'PYEOF' || { echo "  ⚠️  sqlite backup failed for $1, copying raw files"; cp -p "$1"* "$(dirname "$2")/" 2>/dev/null; }
import sqlite3, sys
src = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True, timeout=30)
dst = sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close(); src.close()
PYEOF
}

copy_if() {  # copy file/dir if it exists: $1 = src, $2 = dest dir
    [ -e "$1" ] && cp -a -- "$1" "$2/"
    return 0
}

# 1. Panel state (runtime data that is NOT in git)
echo "🔐 Panel state (configs, secrets, sessions, DBs)..."
P="$OUT/panel"
mkdir -p "$P"
copy_if "$PANEL_DIR/telegram_config.json" "$P"
copy_if "$PANEL_DIR/secrets.json" "$P"
copy_if "$PANEL_DIR/telegram_sessions" "$P"
copy_if "$PANEL_DIR/smm_profiles" "$P"
copy_if "$PANEL_DIR/smm_queue" "$P"
copy_if "$PANEL_DIR/smm_trends" "$P"
copy_if "$PANEL_DIR/smm_images" "$P"
mkdir -p "$P/data/searxng"
copy_if "$PANEL_DIR/data/searxng/settings.yml" "$P/data/searxng"
sqlite_copy "$PANEL_DIR/telegram_session.session" "$P/telegram_session.session"
sqlite_copy "$PANEL_DIR/smm_data.db" "$P/smm_data.db"
sqlite_copy "$PANEL_DIR/metrics.db" "$P/metrics.db"

# 2. Panel code (tracked files incl. uncommitted edits) + git reference
echo "📦 Panel code..."
if git -C "$PANEL_DIR" rev-parse --git-dir &>/dev/null; then
    git -C "$PANEL_DIR" rev-parse HEAD > "$OUT/panel_git_head.txt" 2>/dev/null
    git -C "$PANEL_DIR" status --short > "$OUT/panel_git_status.txt" 2>/dev/null
    git -C "$PANEL_DIR" ls-files -z | tar -C "$PANEL_DIR" --null -T - -czf "$OUT/panel_code.tar.gz" 2>/dev/null \
        || echo "  ⚠️  code archive incomplete"
else
    tar -C "$PANEL_DIR" -czf "$OUT/panel_code.tar.gz" \
        --exclude=venv --exclude=__pycache__ --exclude='*.db*' --exclude='*.session*' \
        --exclude=secrets.json --exclude=telegram_config.json --exclude='smm_*' . 2>/dev/null
fi

# 3. Agent scripts + memory (live outside the repo)
echo "🤖 Agents and memory..."
if [ -d "$AGENTS_DIR" ]; then
    tar -C "$(dirname "$AGENTS_DIR")" -czf "$OUT/agents.tar.gz" --exclude=__pycache__ "$(basename "$AGENTS_DIR")" 2>/dev/null
fi

# 4. ComfyUI workflows
echo "🎨 ComfyUI workflows..."
mkdir -p "$OUT/comfyui_workflows"
for f in "$COMFYUI_DIR"/*.json; do
    [ -f "$f" ] && cp -p -- "$f" "$OUT/comfyui_workflows/"
done
copy_if "$COMFYUI_DIR/user/default/workflows" "$OUT/comfyui_workflows"

# 5. Claude Code settings + memory
echo "⚙️ Claude Code settings..."
mkdir -p "$OUT/claude_config"
copy_if "$HOME/.claude/settings.json" "$OUT/claude_config"
copy_if "$HOME/.claude.json" "$OUT/claude_config"
copy_if "$HOME/Desktop/Claude_Test/.mcp.json" "$OUT/claude_config"
for proj in "$HOME"/.claude/projects/*; do
    if [ -d "$proj/memory" ]; then
        mkdir -p "$OUT/claude_config/memory/$(basename "$proj")"
        cp -a -- "$proj/memory/." "$OUT/claude_config/memory/$(basename "$proj")/"
    fi
done

# 6. Systemd units (panel runs as a USER unit)
echo "🔧 Systemd configs..."
mkdir -p "$OUT/systemd/user" "$OUT/systemd/system"
for f in "$HOME"/.config/systemd/user/ai-*.service "$HOME"/.config/systemd/user/ai-*.timer; do
    [ -f "$f" ] && cp -p -- "$f" "$OUT/systemd/user/"
done
copy_if /etc/systemd/system/ollama.service.d "$OUT/systemd/system"
copy_if /etc/systemd/system/docker-socket-fix.service "$OUT/systemd/system"

# 7. Ollama model list
echo "📋 Ollama models list..."
ollama list > "$OUT/ollama_models.txt" 2>/dev/null || true

# 8. Docker container configs (not volumes — Qdrant vectors are NOT included)
echo "🐳 Docker configs..."
for container in open-webui perplexica searxng qdrant; do
    docker inspect "$container" > "$OUT/docker_${container}.json" 2>/dev/null || rm -f "$OUT/docker_${container}.json"
done

cat > "$OUT/RESTORE.txt" <<EOF
NeuralForge backup $TIMESTAMP (from $PANEL_DIR)

Restore (stop the panel first: systemctl --user stop ai-panel):
  1. Code:   git clone https://github.com/DefinitelyN0tMe/neuralforge.git <dir>
             (or: mkdir <dir> && tar -xzf panel_code.tar.gz -C <dir>); run ./install.sh
             panel_git_head.txt / panel_git_status.txt show the exact commit / local edits.
  2. State:  cp -a panel/. <dir>/
             (telegram_config.json, secrets.json, telegram_session.session, telegram_sessions/,
              smm_data.db, metrics.db, smm_profiles/, smm_queue/, smm_trends/, smm_images/,
              data/searxng/settings.yml)
             Remove stale smm_data.db-wal/-shm and metrics.db-wal/-shm in <dir> before starting.
  3. Agents: tar -xzf agents.tar.gz -C ~/Desktop/Claude_Test/
  4. Units:  cp systemd/user/* ~/.config/systemd/user/ && systemctl --user daemon-reload
             (system/ files need sudo; do NOT restore a system ai-panel.service)
  5. Models: ollama pull <each name in ollama_models.txt>
  6. Start:  systemctl --user start ai-panel
Not included: Qdrant vectors (use Qdrant snapshots), Ollama model blobs, Docker volumes.
EOF

# Compress
echo ""
echo "📦 Compressing..."
if ! tar -C "$STAGE" -czf "$ARCHIVE.part" "$NAME"; then
    rm -f -- "$ARCHIVE.part"
    echo "❌ Backup FAILED (tar error) — nothing written"
    exit 1
fi
mv -- "$ARCHIVE.part" "$ARCHIVE"
chmod 600 "$ARCHIVE"
COMPRESSED_SIZE=$(du -sh "$ARCHIVE" 2>/dev/null | awk '{print $1}')

# Cleanup old backups (keep last $KEEP). Names are backup_YYYYmmdd_HHMMSS so
# lexical order == chronological order.
mapfile -t ALL < <(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'backup_*.tar.gz' | sort)
if [ "${#ALL[@]}" -gt "$KEEP" ]; then
    for old in "${ALL[@]:0:${#ALL[@]}-KEEP}"; do
        rm -f -- "$old"
    done
fi
TOTAL_BACKUPS=$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'backup_*.tar.gz' | wc -l)

echo ""
echo "✅ Backup complete!"
echo "   File: $ARCHIVE"
echo "   Size: $COMPRESSED_SIZE"
echo "   Total backups: $TOTAL_BACKUPS (keeping last $KEEP)"
