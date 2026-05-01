# Portage Android (vraie app native)

Note de continuation possible : refaire le projet en application Android native, pour pouvoir transformer un vieux téléphone en station de surveillance autonome (sans Mac qui tourne en permanence).

## Objectif

Reproduire les fonctionnalités actuelles du `cam.py` macOS dans une application Android **native Kotlin**, déployable sur un téléphone laissé branché chez soi.

## Pourquoi pas Termux ou hybride

- **Termux** : plug-in `Termux:API` permet `termux-camera-photo` mais pas de flux continu pour de la détection de mouvement fiable. Background tué par Android. Bricolé.
- **Hybride (phone as IP cam + serveur Python)** : déjà décrit comme l'option pragmatique pour multiplier les caméras. Mais nécessite un serveur tiers qui tourne 24/7. L'app native rend le téléphone vraiment autonome.

## Stack technique cible

| Bloc | Technologie | Équivalent Mac actuel |
|------|-------------|----------------------|
| Langage | Kotlin (Jetpack Compose pour l'UI) | Python |
| Capture vidéo | **CameraX** ou Camera2 API | `cv2.VideoCapture` |
| Détection mouvement | **ML Kit Object Detection** ou **TensorFlow Lite** (modèle léger pré-entraîné) | frame-diff OpenCV |
| Background | **ForegroundService** + notification persistante | `launchd` + KeepAlive |
| Lecture audio | **MediaPlayer** + `AudioManager.STREAM_ALARM` à 100% | `afplay` + `osascript` |
| TTS | **TextToSpeech** Android (intégré) | `say -v Thomas` |
| HTTP / Telegram | **OkHttp** ou **Ktor** appelant directement Bot API REST | `python-telegram-bot` |
| Persistance config | `SharedPreferences` ou DataStore | `.env` |
| Stockage photos | `MediaStore` ou app-specific dir | `captures/` |

## Architecture

```
┌──────────────────────────────────────────────────────┐
│  ForegroundService (toujours actif, notif visible)   │
│  ├─ CameraX preview + analyseur frame-by-frame       │
│  ├─ MotionDetector (ML Kit ou diff custom)           │
│  ├─ TelegramPoller (long-polling getUpdates)         │
│  └─ AlarmController (MediaPlayer en boucle, max vol) │
└──────────────────────────────────────────────────────┘
        │                                    │
        ▼                                    ▼
   Telegram Bot API                     Stockage local
```

Un seul `ForegroundService` qui héberge la boucle caméra et le polling Telegram en parallèle (coroutines Kotlin = équivalent direct d'`asyncio`).

## Fonctionnalités à reproduire

### Détection / capture
- [ ] Boucle caméra continue avec analyseur de frames CameraX
- [ ] Détection de mouvement (frame-diff comme aujourd'hui, ou upgrade ML Kit "personne")
- [ ] Burst de N photos espacées (réutiliser la logique Python)
- [ ] Cooldown configurable
- [ ] Pause/resume libérant la caméra (équivalent `cap.release()` → CameraX `unbind`)

### Telegram
- [ ] Long-polling `getUpdates` ou webhook (préférer polling pour rester derrière NAT)
- [ ] Restriction au `CHAT_ID` configuré (auth)
- [ ] Commandes : `/pause`, `/resume`, `/status`, `/snapshot`, `/alarm`, `/stopalarm`, `/help`
- [ ] Envoi `sendMediaGroup` pour les rafales
- [ ] Préfixe `SITE_NAME` sur tous les messages

### Alarme
- [ ] Lecture en boucle du fichier audio configuré (asset bundlé OU sélectionné par l'utilisateur via `Storage Access Framework`)
- [ ] Forcer `STREAM_ALARM` à `getStreamMaxVolume()` pendant la lecture
- [ ] Sauvegarder/restaurer le volume précédent
- [ ] Fallback TTS via `TextToSpeech` français
- [ ] Annulation propre via `/stopalarm` (kill du MediaPlayer + restore volume)

### UI minimale (l'app n'a pas besoin d'être belle, juste configurable)
- [ ] Champ token Telegram
- [ ] Champ chat_id (avec un bouton "récupérer mon chat_id" qui call `getUpdates`)
- [ ] Champ `SITE_NAME`
- [ ] Sliders : `MIN_AREA`, `BURST_COUNT`, `BURST_INTERVAL`, `COOLDOWN_SECONDS`
- [ ] Sélecteur de fichier audio pour l'alarme
- [ ] Bouton "Démarrer le service" → lance le `ForegroundService`
- [ ] État live : caméra ouverte/fermée, dernière détection, alarme active oui/non

## Difficultés Android-spécifiques à anticiper

1. **Battery optimizations** — Android (surtout Samsung, Xiaomi, Huawei) tue agressivement les services en arrière-plan. Il faut :
   - Demander à l'utilisateur de désactiver les optimisations batterie pour l'app (`ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`)
   - Utiliser un `ForegroundService` (notification permanente obligatoire) — cadre légal du `FOREGROUND_SERVICE_TYPE_CAMERA` depuis Android 14
2. **Permissions runtime** — caméra, micro (si on ajoute audio), notifications (Android 13+), storage (pour photos)
3. **Permission `FOREGROUND_SERVICE_CAMERA`** dans le manifest (Android 14+)
4. **Lock screen** — la cam doit pouvoir tourner écran éteint, OK avec ForegroundService bien configuré
5. **Réveil au reboot** — `BOOT_COMPLETED` receiver pour relancer le service au démarrage du tel
6. **Tap-to-wake** ou écran qui s'éteint complètement : à tester selon constructeur
7. **Connectivité** — gérer la perte de réseau gracieusement (retry exponentiel sur les calls Bot API)

## Phasage suggéré (si on s'y met un jour)

**Phase 1 — squelette (1 weekend)**
- Projet Android Studio, manifest avec permissions
- ForegroundService minimal qui ouvre la caméra et envoie une photo de test à Telegram

**Phase 2 — détection + commandes (1-2 weekends)**
- Frame-diff motion detection
- Polling Telegram + handlers `/pause`, `/resume`, `/snapshot`, `/status`
- Burst de photos

**Phase 3 — alarme (1 weekend)**
- MediaPlayer en boucle, max volume STREAM_ALARM
- Commandes `/alarm`, `/stopalarm`
- Fallback TTS

**Phase 4 — UI de config (1 weekend)**
- Settings screen Compose
- DataStore pour persistance
- Bouton démarrage / arrêt service

**Phase 5 — polish**
- Détection upgrade vers ML Kit (filtrer les ombres / animaux)
- Alertes si caméra inaccessible
- Boot receiver
- Vidéo (au lieu de photo) pour les alertes si bande passante OK

## Avantages d'un téléphone vs MacBook

| Critère | MacBook Air actuel | Téléphone Android (objectif) |
|---------|-------------------|------------------------------|
| Conso au mur | ~3 W | ~2-4 W (selon écran éteint) |
| Coût hardware | ~1000€ neuf | un vieux téléphone qui traîne, 0€ |
| Caméra | webcam frontale fixe | objectif souvent meilleur, orientable |
| Position | encombrant, capot fermé | scotchable n'importe où |
| Réseau | WiFi stable | WiFi ou 4G (résilience hors-coupure) |
| Audio | haut-parleurs corrects | haut-parleur tel souvent puissant pour la voix |
| LED activité | impossible à désactiver | logiciel, désactivable en app native |

→ La LED non-désactivable du Mac est le principal argument en faveur du portage Android : sur un téléphone on contrôle tout en logiciel, donc on peut faire une vraie surveillance discrète.

## Référence du code Python actuel

À la migration, garder en tête les fichiers et constantes du projet existant :
- `cam.py` : architecture asyncio, lifecycle caméra, détection, burst, alarme en boucle, gestion du volume
- `.env.example` : toutes les variables paramétrables (`MIN_AREA`, `BURST_COUNT`, `BURST_INTERVAL`, `COOLDOWN_SECONDS`, `WARMUP_SECONDS`, `SITE_NAME`, `ALARM_SOUND`, `ALARM_VOICE`, `ALARM_TEXT`)
- `README.md` : description fonctionnelle des commandes Telegram à reproduire à l'identique pour rester compatible avec l'usage actuel
