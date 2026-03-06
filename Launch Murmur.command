#!/bin/bash
# Murmur Background Launcher
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"
pkill -f daemon.py 2>/dev/null
nohup "$DIR/.venv/bin/python" daemon.py > /tmp/murmur.log 2>&1 &
echo ""
echo "🎙️ Murmur has been started in the background!"
echo "   You can close this window. Hold RIGHT ⌥ to dictate."
echo ""
sleep 3
