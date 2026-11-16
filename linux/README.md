# gotchacam sur Raspberry Pi / Linux

Testé pour : Raspberry Pi 4 sous Raspberry Pi OS **64 bits** (Bookworm), avec une **webcam USB**.
Devrait fonctionner sur toute Debian/Ubuntu avec `apt` et `systemd`.

## Installation

Sur le Raspberry Pi, avec ton utilisateur normal (pas root) :

```bash
git clone <url-du-repo> ~/cam && cd ~/cam
bash linux/install.sh
```

L'installeur :
1. installe les paquets (`ffmpeg`, `espeak-ng`, `alsa-utils`, `v4l-utils`, Python venv) ;
2. crée `.venv` et installe les dépendances (`linux/requirements.txt`, OpenCV *headless*) ;
3. lance l'assistant qui te demande : token du bot, chat ID (détecté automatiquement quand tu écris
   au bot), caméra (liste des webcams réellement utilisables + photo de test), résolution,
   haut-parleur (avec bip de test), profil de performance (charge CPU : économe / équilibré / précis), langue, nom du site, durée de conservation des photos,
   serveur HTTP optionnel ;
4. écrit `.env` (permissions 600) et le service systemd `gotchacam` ;
5. te demande si tu veux l'activer au démarrage et le lancer maintenant.

Avant de lancer l'installeur, crée ton bot avec **@BotFather** (`/newbot`) pour avoir le token.

## Commandes utiles

| Action | Commande |
|---|---|
| Suivre les logs | `journalctl -u gotchacam -f` |
| Redémarrer | `sudo systemctl restart gotchacam` |
| Refaire la configuration | `bash linux/install.sh --reconfigure` puis redémarrer |
| Retirer le service | `bash linux/install.sh --uninstall` |

## Différences avec la version macOS

- **Son** : lecture via `ffmpeg` vers ALSA (`AUDIO_DEVICE`), volume via `amixer` (`AUDIO_CARD`, `AUDIO_CONTROL`).
- **Alarme sans fichier** : synthèse vocale `espeak-ng` (voix = code langue) au lieu de `say`.
  Un fichier `alarm.m4a` à la racine, ou `/recordalarm` sur Telegram, la remplace.
- **Caméra** : V4L2 + MJPG ; `CAMERA_INDEX=N` correspond à `/dev/videoN`.
- **Logs** : dans journald (pas de `cam.log`/`cam.err`).

## Limites connues

- **Caméra nappe CSI du Pi (Camera Module) non prise en charge** : elle passe par libcamera/picamera2,
  pas par V4L2 classique. Utilise une webcam USB.
- Non testé sur Raspberry Pi OS 32 bits.
- Stockage : les photos sont sur la carte SD ; garde `RETENTION_DAYS` bas (14 par défaut).
