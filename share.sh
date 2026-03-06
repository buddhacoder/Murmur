#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# Murmur — create a shareable zip for a friend or colleague
# Nothing sensitive is included.
# ──────────────────────────────────────────────────────────
set -e

MURMUR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PARENT_DIR="$(dirname "$MURMUR_DIR")"
ZIP_NAME="murmur-share.zip"
ZIP_PATH="$PARENT_DIR/$ZIP_NAME"

echo "🔇 Packaging Murmur for sharing..."

# Remove old zip if it exists
rm -f "$ZIP_PATH"

cd "$PARENT_DIR"

zip -r "$ZIP_PATH" Murmur \
  --exclude "Murmur/.venv/*" \
  --exclude "Murmur/sessions/*" \
  --exclude "Murmur/vault/*" \
  --exclude "Murmur/models/*" \
  --exclude "Murmur/*.pyc" \
  --exclude "Murmur/__pycache__/*" \
  --exclude "Murmur/.DS_Store" \
  --exclude "Murmur/murmur-share.zip" \
  --exclude "Murmur/run.sh"

echo ""
echo "✓ Created: $ZIP_PATH"
echo ""
echo "Share this zip with your friend/colleague."
echo "They should:"
echo "  1. Unzip it"
echo "  2. cd into the Murmur folder"
echo "  3. Run: bash install.sh"
echo "  4. Run: bash run.sh"
echo ""
echo "Everything runs locally on their Mac. No cloud calls. Ever."
