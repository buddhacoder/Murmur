#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# Murmur — One-command installer for macOS (Apple Silicon)
# ──────────────────────────────────────────────────────────
set -e

MURMUR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_OLLAMA_MODEL="llama3.2:3b"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}  🔇 Murmur — local voice + AI copilot${NC}"
echo -e "${CYAN}  Installing on your Mac Studio...${NC}"
echo ""

# ── 1. Homebrew
if ! command -v brew &>/dev/null; then
  echo -e "${YELLOW}Installing Homebrew...${NC}"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
  echo -e "${GREEN}✓ Homebrew already installed${NC}"
fi

# ── 2. Ollama
if ! command -v ollama &>/dev/null; then
  echo -e "${YELLOW}Installing Ollama...${NC}"
  brew install ollama
else
  echo -e "${GREEN}✓ Ollama already installed${NC}"
fi

# ── 3. Ollama model
echo ""
echo -e "${CYAN}Which Ollama model do you want?${NC}"
echo "  1) llama3.2:3b   — fastest, great for most tasks (~2GB) ← good for 32GB Mac"
echo "  2) qwen2.5:7b    — more capable, better clinical notes (~4GB) ← good for 48GB+"
echo "  3) llama3.1:8b   — strong reasoning (~5GB) ← good for 64GB+"
echo "  4) Skip          — I'll pull a model manually later"
echo ""
read -rp "Enter choice [1-4, default=1]: " MODEL_CHOICE

case "${MODEL_CHOICE:-1}" in
  2) OLLAMA_MODEL="qwen2.5:7b"  ;;
  3) OLLAMA_MODEL="llama3.1:8b" ;;
  4) OLLAMA_MODEL=""             ;;
  *) OLLAMA_MODEL="$DEFAULT_OLLAMA_MODEL" ;;
esac

if [ -n "$OLLAMA_MODEL" ]; then
  echo -e "${YELLOW}Starting Ollama and pulling model: $OLLAMA_MODEL ...${NC}"
  if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    ollama serve &>/dev/null &
    sleep 3
  fi
  ollama pull "$OLLAMA_MODEL"
  echo -e "${GREEN}✓ Model ready: $OLLAMA_MODEL${NC}"
fi

# ── 4. Python venv + pip
echo ""
echo -e "${YELLOW}Setting up Python environment...${NC}"
python3 -m venv "$MURMUR_DIR/.venv"
source "$MURMUR_DIR/.venv/bin/activate"
pip install --upgrade pip --quiet
pip install -r "$MURMUR_DIR/requirements.txt" --quiet
echo -e "${GREEN}✓ Python environment ready${NC}"
echo -e "${GREEN}  (faster-whisper will download the Whisper model on first run, ~150MB)${NC}"

# ── 5. Create launch script
cat > "$MURMUR_DIR/run.sh" << 'LAUNCH'
#!/usr/bin/env bash
MURMUR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$MURMUR_DIR/.venv/bin/activate"

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
LAUNCH
chmod +x "$MURMUR_DIR/run.sh"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ Murmur is ready!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo -e "  To launch: ${CYAN}bash $MURMUR_DIR/run.sh${NC}"
echo ""
