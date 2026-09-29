#!/bin/bash
# NeuralForge Recovery Script — check base services and restart what is down.
# Run as your normal user (not with sudo): the panel is a systemd USER unit.
set -u

SERVICE_NAME="ai-panel"

if [ "$(id -u)" -eq 0 ]; then
    echo "❌ Run as your normal user, not root — the panel is a user unit (systemctl --user)."
    exit 1
fi

echo "🔄 NeuralForge Recovery — checking and restarting services..."
FAILED=0

# Ollama (system service installed by the Ollama installer)
if ! systemctl is-active --quiet ollama; then
    echo "  ⚠️ Ollama is down, restarting..."
    sudo systemctl restart ollama
    sleep 3
fi
if systemctl is-active --quiet ollama; then
    echo "  ✅ Ollama: active"
else
    echo "  ❌ Ollama: $(systemctl is-active ollama)"; FAILED=1
fi

# NeuralForge Panel — user unit only. A system unit with the same name would
# fight it for :9000, so warn instead of starting that one.
if systemctl is-enabled --quiet "$SERVICE_NAME" 2>/dev/null || systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    echo "  ⚠️ System unit /etc/systemd/system/$SERVICE_NAME.service is enabled/active — it conflicts"
    echo "     with the user unit on :9000. Disable it: sudo systemctl disable --now $SERVICE_NAME"
fi
if ! systemctl --user is-active --quiet "$SERVICE_NAME"; then
    echo "  ⚠️ Panel is down, restarting..."
    systemctl --user reset-failed "$SERVICE_NAME" 2>/dev/null
    systemctl --user restart "$SERVICE_NAME"
    sleep 3
fi
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    echo "  ✅ Panel: active"
else
    echo "  ❌ Panel: $(systemctl --user is-active "$SERVICE_NAME") — see: journalctl --user -u $SERVICE_NAME -n 50"
    FAILED=1
fi

# Docker containers — use the docker group; fall back to sudo only if needed.
DOCKER=(docker)
if ! docker info &>/dev/null; then
    echo "  ⚠️ No access to the Docker socket as $USER (add yourself to the 'docker' group); using sudo"
    DOCKER=(sudo docker)
fi
for container in open-webui perplexica searxng qdrant; do
    status=$("${DOCKER[@]}" inspect -f '{{.State.Running}}' "$container" 2>/dev/null)
    if [ -z "$status" ]; then
        echo "  ⚠️ $container: container not found (skipped)"
        continue
    fi
    if [ "$status" != "true" ]; then
        echo "  ⚠️ $container is down, starting..."
        "${DOCKER[@]}" start "$container" >/dev/null
        sleep 2
        status=$("${DOCKER[@]}" inspect -f '{{.State.Running}}' "$container" 2>/dev/null)
    fi
    if [ "$status" = "true" ]; then
        echo "  ✅ $container: running"
    else
        echo "  ❌ $container: failed to start"; FAILED=1
    fi
done

echo ""
if [ "$FAILED" -eq 0 ]; then
    echo "🎯 All base services are running!"
else
    echo "⚠️ Some services failed to start — see messages above."
fi
echo "   Panel:  http://localhost:9000"
echo "   Chat:   http://localhost:8080"
echo "   Search: http://localhost:3000"
exit "$FAILED"
