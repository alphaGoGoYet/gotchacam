#!/bin/bash
# Installe (ou réinstalle) le LaunchAgent qui démarre cam.py à l'ouverture de session.
# À lancer depuis le dossier du projet : `bash install_autostart.sh`
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
SCRIPT="$PROJECT_DIR/cam.py"
LABEL="com.goyet.cam"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ ! -x "$PYTHON" ]; then
    echo "Erreur : $PYTHON introuvable."
    echo "Crée d'abord le venv :"
    echo "  cd \"$PROJECT_DIR\" && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "Erreur : .env manquant dans $PROJECT_DIR (token Telegram absent)."
    exit 1
fi

mkdir -p "$(dirname "$PLIST")"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>$SCRIPT</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$PROJECT_DIR/cam.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT_DIR/cam.err</string>
</dict>
</plist>
EOF

echo "plist écrit : $PLIST"

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

if launchctl list | grep -q "$LABEL"; then
    echo "service chargé et actif."
else
    echo "service non listé — consulte cam.err pour diagnostiquer."
    exit 1
fi

echo ""
echo "Suivre les logs :"
echo "  tail -f \"$PROJECT_DIR/cam.log\" \"$PROJECT_DIR/cam.err\""
echo "Arrêter sans désinstaller :"
echo "  launchctl unload \"$PLIST\""
echo "Désinstaller complètement :"
echo "  launchctl unload \"$PLIST\" && rm \"$PLIST\""
