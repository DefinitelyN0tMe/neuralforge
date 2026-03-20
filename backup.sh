#!/bin/bash
# AI Station Backup Script
# Бэкапит конфиги, память агентов, workflows, панель, RAG данные

BACKUP_DIR="/home/definitelynotme/Desktop/ai-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/backup_$TIMESTAMP"

mkdir -p "$BACKUP_PATH"

echo "🔄 AI Station Backup — $TIMESTAMP"
echo ""

# 1. AI Control Panel
echo "📦 Панель управления..."
cp -r /home/definitelynotme/Desktop/ai-panel/modules "$BACKUP_PATH/panel_modules"
cp -r /home/definitelynotme/Desktop/ai-panel/server.py "$BACKUP_PATH/panel_server.py"
cp -r /home/definitelynotme/Desktop/ai-panel/mcp_server.py "$BACKUP_PATH/panel_mcp.py"
cp -r /home/definitelynotme/Desktop/ai-panel/templates "$BACKUP_PATH/panel_templates"

# 2. Agent scripts + memory
echo "🤖 Агенты и память..."
cp -r /home/definitelynotme/Desktop/Claude_Test/agents "$BACKUP_PATH/agents"

# 3. ComfyUI workflows
echo "🎨 ComfyUI workflows..."
mkdir -p "$BACKUP_PATH/comfyui_workflows"
cp /home/definitelynotme/Desktop/ComfyUI/*.json "$BACKUP_PATH/comfyui_workflows/" 2>/dev/null

# 4. Claude settings
echo "⚙️ Claude Code настройки..."
mkdir -p "$BACKUP_PATH/claude_config"
cp ~/.claude/settings.json "$BACKUP_PATH/claude_config/" 2>/dev/null
cp ~/.claude.json "$BACKUP_PATH/claude_config/" 2>/dev/null
cp /home/definitelynotme/Desktop/Claude_Test/.mcp.json "$BACKUP_PATH/claude_config/" 2>/dev/null
cp -r ~/.claude/projects/-home-definitelynotme-Desktop-Claude-Test/memory "$BACKUP_PATH/claude_config/memory" 2>/dev/null

# 5. Systemd services
echo "🔧 Systemd конфиги..."
mkdir -p "$BACKUP_PATH/systemd"
cp /etc/systemd/system/ai-panel.service "$BACKUP_PATH/systemd/" 2>/dev/null
cp -r /etc/systemd/system/ollama.service.d "$BACKUP_PATH/systemd/" 2>/dev/null
cp /etc/systemd/system/docker-socket-fix.service "$BACKUP_PATH/systemd/" 2>/dev/null

# 6. PDF guides
echo "📄 PDF гайды..."
mkdir -p "$BACKUP_PATH/pdfs"
cp /home/definitelynotme/Desktop/Claude_Test/*.pdf "$BACKUP_PATH/pdfs/" 2>/dev/null
cp /home/definitelynotme/Desktop/Claude_Test/generate_*.py "$BACKUP_PATH/pdfs/" 2>/dev/null

# 7. Ollama modelfile list
echo "📋 Список моделей Ollama..."
ollama list > "$BACKUP_PATH/ollama_models.txt" 2>/dev/null

# 8. Docker container configs
echo "🐳 Docker конфиги..."
for container in open-webui perplexica searxng qdrant; do
    docker inspect $container > "$BACKUP_PATH/docker_${container}.json" 2>/dev/null
done

# 9. SearXNG config
echo "🔍 SearXNG настройки..."
cp /tmp/searxng/settings.yml "$BACKUP_PATH/searxng_settings.yml" 2>/dev/null

# Compress
echo ""
echo "📦 Сжимаю..."
cd "$BACKUP_DIR"
tar -czf "backup_$TIMESTAMP.tar.gz" "backup_$TIMESTAMP" 2>/dev/null
COMPRESSED_SIZE=$(du -sh "backup_$TIMESTAMP.tar.gz" 2>/dev/null | awk '{print $1}')
rm -rf "backup_$TIMESTAMP"

# Cleanup old backups (keep last 5)
ls -t "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null

TOTAL_BACKUPS=$(ls "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | wc -l)

echo ""
echo "✅ Бэкап завершён!"
echo "   Файл: $BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
echo "   Размер: $COMPRESSED_SIZE"
echo "   Всего бэкапов: $TOTAL_BACKUPS (хранятся последние 5)"
