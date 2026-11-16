# gotchacam sur Raspberry Pi / Linux

Utilisé sur : Raspberry Pi 4 avec une **webcam USB**, Raspberry Pi OS **64 bits** recommandé.
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

## Mettre à jour

```bash
cd ~/cam && git pull && sudo systemctl restart gotchacam
```
Le `.env` n'est pas touché. Relance `bash linux/install.sh` seulement si les dépendances changent.

## Commandes utiles

| Action | Commande |
|---|---|
| Suivre les logs | `journalctl -u gotchacam -f` |
| Redémarrer | `sudo systemctl restart gotchacam` |
| Refaire la configuration | `bash linux/install.sh --reconfigure` puis redémarrer |
| Retirer le service | `bash linux/install.sh --uninstall` |

## Réglages (fichier `.env`)

Tout se règle dans `~/cam/.env` (ou via `bash linux/install.sh --reconfigure`), puis
`sudo systemctl restart gotchacam`. Les principaux :

| Réglage | Rôle | Défaut |
|---|---|---|
| `CAMERA_INDEX` | caméra utilisée (`N` = `/dev/videoN`) | 0 |
| `CAMERA_WIDTH` / `CAMERA_HEIGHT` | résolution des photos (doit être gérée par la caméra : `v4l2-ctl -d /dev/video0 --list-formats-ext`) | 1280×720 |
| `DETECT_WIDTH` | largeur de l'image analysée ; plus bas = moins de CPU, moins précis | 320 |
| `ANALYSIS_FPS` | analyses par seconde | 5 |
| `MIN_AREA` | taille minimale d'un mouvement (pixels de l'image native) | 5000 |
| `COOLDOWN_SECONDS` | délai minimum entre deux alertes | 3 |
| `RETENTION_DAYS` | durée de conservation des photos | 14 |
| `AUDIO_DEVICE`, `AUDIO_CARD`, `AUDIO_CONTROL` | sortie audio ALSA et volume | `default`, –, `Master` |

La liste complète est dans [.env.example](../.env.example).

## Dépannage

- **Caméra non détectée** : vérifie `ls /dev/video*` et `groups` (il faut `video`). Si le groupe vient
  d'être ajouté, déconnecte-toi puis reconnecte-toi. Une caméra CSI (nappe) n'est pas prise en charge.
- **Pas de son** : `aplay -l` liste les cartes ; relance `bash linux/install.sh --reconfigure` pour choisir
  la bonne sortie (bip de test). Si le volume ne change pas, vérifie `AUDIO_CONTROL` avec `amixer -c <carte> scontrols`.
- **Erreur 409 / « Conflict » dans les logs** : le même bot est utilisé par un autre programme
  (par exemple ton Mac). Crée un bot par machine.
- **CPU trop élevé** : baisse `CAMERA_WIDTH`/`CAMERA_HEIGHT` à 640×480, puis `ANALYSIS_FPS` à 3.
- **Détections ratées** : monte `DETECT_WIDTH` (480) ou baisse `MIN_AREA`.
- **Logs** : `journalctl -u gotchacam -n 50`.

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
