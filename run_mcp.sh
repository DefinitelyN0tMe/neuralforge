#!/bin/bash
# NeuralForge MCP Server launcher (stdio). Works from any install location.
# Add to .mcp.json: {"mcpServers": {"neuralforge": {"command": "/path/to/neuralforge/run_mcp.sh"}}}
# Nothing may be printed to stdout here — it is the MCP protocol channel.
PANEL_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$PANEL_DIR" || exit 1
exec "$PANEL_DIR/venv/bin/python3" "$PANEL_DIR/mcp_server.py" "$@"
