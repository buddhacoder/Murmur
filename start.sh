#!/usr/bin/env bash
# Murmur — start the push-to-talk daemon
# After this runs, hold ⌥ + Space anywhere on your Mac to dictate.

MURMUR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$MURMUR_DIR/.venv/bin/activate"

echo ""
echo "🔇 Starting Murmur daemon…"
echo "   Hold  ⌥ + Space  to record."
echo "   Release to transcribe + paste into whatever's focused."
echo "   Press  Ctrl+C  to stop."
echo ""
echo "   NOTE: First run will grant Accessibility + Mic permissions."
echo "         If a dialog appears, click Allow/OK, then re-run this script."
echo ""

python "$MURMUR_DIR/daemon.py"
