#!/bin/bash
# AI Recovery Script — восстановление базовых сервисов
echo "🔄 AI Recovery — проверяю и восстанавливаю сервисы..."

# Ollama
if ! systemctl is-active --quiet ollama; then
    echo "  ⚠️ Ollama не работает, перезапускаю..."
    sudo systemctl restart ollama
    sleep 3
fi
echo "  ✅ Ollama: $(systemctl is-active ollama)"

# AI Control Panel
if ! systemctl is-active --quiet ai-panel; then
    echo "  ⚠️ AI Panel не работает, перезапускаю..."
    sudo systemctl restart ai-panel
    sleep 3
fi
echo "  ✅ AI Panel: $(systemctl is-active ai-panel)"

# Docker containers
for container in open-webui perplexica searxng qdrant; do
    status=$(sudo docker inspect -f '{{.State.Running}}' $container 2>/dev/null)
    if [ "$status" != "true" ]; then
        echo "  ⚠️ $container не работает, запускаю..."
        sudo docker start $container
        sleep 2
    fi
    echo "  ✅ $container: running"
done

# Fix Docker socket permissions
sudo chmod 666 /var/run/docker.sock 2>/dev/null

echo ""
echo "🎯 Все базовые сервисы запущены!"
echo "   Panel: http://localhost:9000"
echo "   Chat:  http://localhost:8080"
echo "   Search: http://localhost:3000"
