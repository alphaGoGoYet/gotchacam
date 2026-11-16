#!/bin/bash
# Installeur gotchacam pour Linux / Raspberry Pi (Raspberry Pi OS 64 bits ou Debian/Ubuntu).
#
#   bash linux/install.sh               installation complète (dépendances + assistant + service)
#   bash linux/install.sh --reconfigure relance seulement l'assistant de configuration
#   bash linux/install.sh --uninstall   retire le service systemd (garde le projet et le .env)
#
# À lancer en utilisateur normal (pas root) : sudo est demandé quand nécessaire.
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
SERVICE="gotchacam"
UNIT="/etc/systemd/system/$SERVICE.service"

info() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ask_yes_no() { # $1 = question, défaut oui
    local r; read -r -p "$1 (O/n) : " r
    [[ -z "$r" || "$r" =~ ^[OoYy] ]]
}

if [ "$(uname -s)" != "Linux" ]; then
    echo "Ce script est prévu pour Linux. Sur macOS : bash install_autostart.sh"; exit 1
fi
if [ "$(id -u)" -eq 0 ]; then
    echo "Ne lance pas ce script en root : le service tournerait sous root."
    echo "Lance-le avec ton utilisateur normal (sudo sera demandé au besoin)."; exit 1
fi

if [ "${1:-}" = "--uninstall" ]; then
    sudo systemctl disable --now "$SERVICE" 2>/dev/null || true
    sudo rm -f "$UNIT"
    sudo systemctl daemon-reload
    echo "Service $SERVICE retiré. Le dossier du projet et le .env sont conservés."
    exit 0
fi

if [ "${1:-}" = "--reconfigure" ]; then
    [ -x "$PYTHON" ] || { echo "Environnement absent : lance d'abord bash linux/install.sh"; exit 1; }
    "$PYTHON" "$PROJECT_DIR/linux/setup_wizard.py"
    echo; echo "Pour appliquer : sudo systemctl restart $SERVICE"
    exit 0
fi

info "1/5 Paquets système"
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg espeak-ng alsa-utils v4l-utils

info "2/5 Environnement Python"
[ -x "$PYTHON" ] || python3 -m venv "$PROJECT_DIR/.venv"
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r "$PROJECT_DIR/linux/requirements.txt"

info "3/5 Droits caméra et audio"
for grp in video audio; do
    if id -nG | tr ' ' '\n' | grep -qx "$grp"; then
        echo "✓ $USER est dans le groupe $grp"
    else
        sudo usermod -aG "$grp" "$USER"
        echo "+ $USER ajouté au groupe $grp (effectif à la prochaine connexion ;"
        echo "  si la caméra n'est pas détectée ci-dessous, déconnecte-toi, reconnecte-toi puis"
        echo "  relance : bash linux/install.sh --reconfigure)"
    fi
done

info "4/5 Configuration"
"$PYTHON" "$PROJECT_DIR/linux/setup_wizard.py"

info "5/5 Service systemd"
sudo tee "$UNIT" >/dev/null <<UNIT_EOF
[Unit]
Description=gotchacam (détection de mouvement → Telegram)
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=$USER
SupplementaryGroups=video audio
WorkingDirectory=$PROJECT_DIR
ExecStart=$PYTHON $PROJECT_DIR/cam.py
Environment=PYTHONUNBUFFERED=1
Environment=XDG_RUNTIME_DIR=/run/user/$(id -u)
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT_EOF
sudo systemctl daemon-reload
echo "✓ $UNIT écrit."

# Permet l'accès audio PipeWire/PulseAudio de l'utilisateur sans session ouverte.
sudo loginctl enable-linger "$USER" || true

echo
if ask_yes_no "Activer le démarrage automatique et lancer le service maintenant ?"; then
    sudo systemctl enable --now "$SERVICE"
    sleep 2
    systemctl --no-pager --lines=0 status "$SERVICE" || true
else
    echo "Service installé mais pas activé. Pour l'activer plus tard :"
    echo "  sudo systemctl enable --now $SERVICE"
fi

cat <<EOM

Commandes utiles :
  journalctl -u $SERVICE -f              suivre les logs
  sudo systemctl restart $SERVICE        redémarrer (après un changement de .env)
  sudo systemctl stop $SERVICE           arrêter
  bash linux/install.sh --reconfigure    refaire la configuration
  bash linux/install.sh --uninstall      retirer le service

Note : sans fichier alarm.m4a à la racine du projet, l'alarme utilise la synthèse vocale
(espeak-ng). Envoie /recordalarm au bot pour enregistrer ta propre voix.
EOM
