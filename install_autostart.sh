#!/usr/bin/env bash
# Install Murmur to launch automatically at login via launchd

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON="$DIR/.venv/bin/python"
SCRIPT="$DIR/daemon.py"
LOG="$DIR/murmur.log"
PLIST="$HOME/Library/LaunchAgents/com.murmur.daemon.plist"

cat > "$PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.murmur.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG</string>
    <key>StandardErrorPath</key>
    <string>$LOG</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
EOF

# Unload if already loaded, then load fresh
launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"

echo "✅ Murmur will now launch automatically at login."
echo "   To remove: launchctl unload $PLIST && rm $PLIST"
