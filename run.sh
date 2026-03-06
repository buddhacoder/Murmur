#!/usr/bin/env bash
# Murmur — launch script (auto-generated, safe to re-run)
MURMUR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$MURMUR_DIR/.venv/bin/activate"

# Start Ollama if not running
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
  echo "Starting Ollama server..."
  ollama serve &>/dev/null &
  sleep 2
fi

echo ""
echo "🔇 Murmur is starting at http://localhost:8501"
echo "   Press Ctrl+C to stop."
echo ""
cd "$MURMUR_DIR"
streamlit run app.py --server.headless false --theme.base dark
