# Behavior Specification

Spécification formelle du comportement de `gotchacam`. Cette spec est la **source de vérité** ; toute implémentation (Python sur macOS, Kotlin sur Android) doit s'y conformer. Si le comportement réel diverge de la spec, c'est l'implémentation qui est en faute, jamais l'inverse.

Toute évolution du comportement doit être :
1. D'abord écrite ici
2. Puis implémentée dans chaque plateforme
3. Validée par les tests d'intégration end-to-end (`shared/e2e-tests/`)

---

## 1. Cycle de vie du service

### 1.1 Démarrage
1. Lire `.env` (variables runtime, dont `TELEGRAM_BOT_TOKEN` obligatoire)
2. Charger `shared/defaults.json` pour les constantes ; les variables d'environnement présentes dans `.env` ont la priorité sur les défauts
3. Charger `shared/strings.fr.json` pour les messages Telegram
4. Connecter au bot Telegram (call `getMe`)
5. Envoyer le message `service.started` (préfixé par `site_prefix` si `SITE_NAME` non vide), suivi du `help` complet
6. Démarrer la boucle caméra (cf. §2)
7. Démarrer le polling des updates Telegram

### 1.2 Arrêt
- Déclencheurs : SIGINT/SIGTERM (Mac), arrêt par l'OS (Android)
- Effet :
  1. Libérer la caméra si ouverte
  2. Couper l'alarme si en cours et restaurer le volume
  3. Envoyer `service.stopped` au chat configuré (best-effort)
  4. Arrêter le polling Telegram proprement

---

## 2. Cycle de vie de la caméra

La caméra est liée au flag `paused` interne :

- `paused = false` → caméra ouverte, frames lues à ~20 fps
- `paused = true` → caméra **libérée** (LED hardware éteinte sur macOS, équivalent Android), pas de capture

### 2.1 Ouverture
- Au passage `paused = false` (ou au démarrage du service si non en pause)
- Ouvrir le device caméra à `camera.index`
- Attendre `camera.warmupSeconds` pour la stabilisation auto-exposition
- Réinitialiser `prev_gray` (référence pour la diff)

### 2.2 Boucle (paused = false)
À chaque itération (~50 ms) :
1. Lire une frame
2. Stocker dans `latest_frame` (utilisé par `/snapshot`)
3. Convertir en niveaux de gris + Gaussian blur 21×21
4. Calculer la diff absolue avec `prev_gray`
5. Seuiller à `motion.threshold`
6. Trouver le plus grand contour
7. Si `area >= motion.minArea` ET `now - last_alert >= motion.cooldownSeconds` :
   - Déclencher un burst (cf. §7) en tâche concurrente
   - Mettre à jour `last_alert = now`
8. Mettre à jour `prev_gray = gray`

### 2.3 Pause (paused = true)
- Libérer la caméra immédiatement (`cap.release` ou équivalent)
- Réinitialiser `prev_gray = null` et `latest_frame = null`
- Boucle dort à intervalles courts en attendant la sortie de pause

### 2.4 Erreur de lecture
- Si `cap.read()` échoue : log warning, sleep 500 ms, retry
- Si l'ouverture échoue : log error, sleep 2 s, retry à la prochaine itération

---

## 3. Algorithme de détection de mouvement

Les paramètres viennent de `defaults.json` ou des variables d'env qui les surchargent.

```
gray = grayscale(frame)
gray = gaussianBlur(gray, kernel=21x21)
delta = absDiff(prev_gray, gray)
thresh = threshold(delta, T = motion.threshold)  // binaire
thresh = dilate(thresh, iterations=2)
contours = findContours(thresh, RETR_EXTERNAL, CHAIN_APPROX_SIMPLE)
largest_area = max(areaOf(c) for c in contours, default=0)
motion = (largest_area >= motion.minArea)
```

L'implémentation doit utiliser une bibliothèque équivalente à OpenCV (Python: `opencv-python`, Android: `org.opencv:opencv-android` ou `ML Kit Vision`).

---

## 4. Commandes Telegram

Toutes les commandes sont **réservées** au `chat_id` du compte propriétaire (auth via `update.effective_chat.id == CHAT_ID`). Les commandes envoyées par d'autres utilisateurs sont silencieusement ignorées.

### 4.1 `/pause`
- Effet : `paused = true`
- Conséquence : caméra libérée à la prochaine itération
- Réponse : `pause.paused`

### 4.2 `/resume`
- Effet : `paused = false`
- Conséquence : caméra réouverte avec warmup à la prochaine itération
- Réponse : `pause.resumed`

### 4.3 `/status`
- Réponse : `status.label` avec `state = status.active` si `paused = false`, sinon `status.paused`

### 4.4 `/snapshot`
- Préconditions :
  - Si `paused = true` → réponse `snapshot.paused`, retour
  - Si `latest_frame == null` → réponse `snapshot.not_ready`, retour
- Effet :
  1. Sauver `latest_frame` dans `captures/snapshot_<timestamp>.jpg`
  2. Envoyer la photo à Telegram avec caption `snapshot.caption` formatée avec `time = HH:MM:SS`
- Erreur d'envoi : réponse `snapshot.send_failed`

### 4.5 `/alarm`
- Précondition : `alarm_active = false` (sinon réponse `alarm.already_running` et retour)
- Effet :
  1. Sauvegarder le volume actuel dans `prev_volume`
  2. Forcer le volume à 100%
  3. `alarm_active = true`
  4. Envoyer `alarm.started` avec `source` valant `alarm.source_recording` si fichier audio configuré et présent, sinon `alarm.source_tts`
  5. Lancer `alarm_loop` en tâche concurrente (cf. §6)

### 4.6 `/stopalarm`
- Précondition : `alarm_active = true` (sinon réponse `alarm.no_alarm_running` et retour)
- Effet :
  1. `alarm_active = false`
  2. Tuer le subprocess de lecture en cours (SIGTERM, fallback SIGKILL après 2s)
  3. Restaurer le volume à `prev_volume` si sauvegardé
  4. Réponse : `alarm.stopped_with_volume` si volume restauré, sinon `alarm.stopped_no_volume`

### 4.7 `/recordalarm`
- Effet :
  1. Ouvrir une fenêtre d'enregistrement de 5 minutes (deadline = now + 300s)
  2. Réponse : `record_alarm.prompt` avec `max = alarm.recordMaxSeconds` et un suffix `pitch_note` non vide si `alarm.pitch != 1.0`
- Le traitement effectif se fait dans le handler de message vocal (cf. §5.2)

### 4.8 `/help` et `/start`
- Réponse : message construit à partir de `help.header` + `help.commands` + `help.footer`

### 4.9 `/sensitivity [valeur]`
- Sans argument : retourne `sensitivity.current` formaté avec `value = MIN_AREA actuel`
- Avec argument valide (entier > 0) : met à jour `MIN_AREA` à chaud (modification de la variable globale, prise en compte immédiate par la boucle de détection en cours), retourne `sensitivity.updated` avec `value` et `previous`
- Avec argument invalide : retourne `sensitivity.invalid` avec `input = la chaîne reçue`
- Le changement n'est **pas persistant** : au prochain redémarrage, la valeur revient à celle de `.env` ou `defaults.json`. Pour persister, l'utilisateur doit éditer son `.env`.

### 4.10 `/history [N]`
- Liste les timestamps des **N dernières détections de mouvement** (défaut 5, clamp à `[1, 20]`)
- Source de vérité : les fichiers `captures/motion_*_1.jpg` (premier frame de chaque burst). Trier par mtime décroissant.
- Si aucune détection : retourne `history.empty`
- Sinon : retourne `history.header` formaté avec `count = nb réel d'items`, suivi d'une ligne `history.item` par détection avec `timestamp = "YYYY-MM-DD HH:MM:SS"` extrait du nom de fichier

### 4.11 `/clean`
- Effet :
  1. Supprimer tous les fichiers de `captures/` (motion, snapshot, voice, audio)
  2. Pour chaque `(chat_id, message_id)` stocké dans `_sent_message_ids` : appeler `delete_message`. Les erreurs (message trop vieux, déjà supprimé) sont silencieusement ignorées
  3. Vider `_sent_message_ids`
- Si rien à supprimer (aucun fichier, aucun message) : réponse `clean.empty`
- Sinon : réponse `clean.done` formatée avec `count` (fichiers supprimés), `msgs` (messages Telegram effacés), `mb` (Mo libérés, 1 décimale)
- Log : `clean: N files deleted (X.X MB), M Telegram messages removed`

---

## 5. Gestion des messages vocaux et audio

### 5.1 Hors fenêtre d'enregistrement (par défaut)

Tout message vocal (`update.message.voice`) ou fichier audio (`update.message.audio`) reçu :
1. Si la durée dépasse `alarm.voicePlaybackMaxSeconds` → réponse `voice.too_long`, retour
2. Télécharger le fichier dans `captures/voice_<timestamp>.<ext>` (ext = `ogg` pour voice, `audio` pour audio)
3. Convertir en WAV via `ffmpeg` (Android : équivalent FFmpegKit)
4. Lire le WAV via `afplay` (macOS) ou `MediaPlayer` (Android) **une seule fois**, à volume actuel
5. Supprimer le WAV temporaire
6. Réponse : `voice.diffused`

### 5.2 Pendant la fenêtre d'enregistrement (5 min après /recordalarm)

Le même handler, mais branche différente :
1. Si la durée dépasse `alarm.recordMaxSeconds` → réponse `voice.too_long`, retour
2. Télécharger le fichier
3. Convertir avec ffmpeg en `alarm.m4a` (chemin = `ALARM_SOUND` ou défaut `alarm.m4a` à côté du script) :
   - Si `alarm.pitch == 1.0` : conversion simple
   - Sinon : appliquer le filtre `asetrate=44100*pitch,aresample=44100,atempo=1/pitch` (modifie le pitch sans modifier la durée)
4. Fermer la fenêtre (`recording_alarm_deadline = 0`)
5. Réponse : `record_alarm.replaced` avec `pitch_note` formaté et `filename`

---

## 6. Comportement de l'alarme (`alarm_loop`)

L'alarme tourne en boucle infinie tant que `alarm_active = true` :

```
while alarm_active:
    if file_exists(alarm_path):
        run [audio_player, alarm_path] until exit
    else:
        run [tts_command, alarm_voice, alarm_text] until exit
```

- `alarm_path` = `ALARM_SOUND` si défini, sinon défaut (`alarm.m4a` à côté du script)
- `audio_player` = `afplay` (macOS) / `MediaPlayer` (Android)
- `tts_command` = `say -v <voice>` (macOS) / `TextToSpeech` (Android)
- L'alarme **n'interrompt pas** la détection ni l'envoi de photos. Si un mouvement est détecté pendant l'alarme, le burst part normalement.
- Volume : 100% pendant `alarm_active`, restauré à `prev_volume` à la sortie

---

## 7. Burst de photos (`capture_burst`)

À chaque détection de mouvement (cf. §2.2) :

```
paths = []
for i in 0..burst.count - 1:
    if i > 0:
        sleep(burst.intervalSeconds)
    if latest_frame == null:
        continue
    save latest_frame to captures/motion_<timestamp_ms>_<i+1>.jpg
    paths.append(...)

if paths is empty:
    return

caption = motion.caption formaté avec time, area, count = len(paths), span = burst.intervalSeconds * (burst.count - 1)
msgs = send_media_group(chat_id=CHAT_ID, photos=paths, caption=caption sur la 1ère photo)
for m in msgs:
    _sent_message_ids.append((CHAT_ID, m.message_id))
```

Le timestamp inclut les millisecondes pour éviter les collisions de noms quand plusieurs frames du burst tombent dans la même seconde.

Les `message_id` retournés par `send_media_group` sont stockés dans `_sent_message_ids` (liste en mémoire) pour permettre à `/clean` de les effacer ultérieurement (cf. §4.11). Même logique pour `/snapshot` (cf. §4.4).

---

## 8. Configuration et défauts

### 8.1 Fichiers
- `shared/defaults.json` : valeurs par défaut, lu au démarrage
- `.env` (chaque machine) : surcharges runtime (token, chat_id, et toute variable de la spec ci-dessous)

### 8.2 Variables (en plus de celles de defaults.json)

| Variable env | Défaut | Description |
|--------------|--------|-------------|
| `TELEGRAM_BOT_TOKEN` | (requis) | Token du bot |
| `TELEGRAM_CHAT_IDS` | `""` | Liste d'IDs autorisés séparés par des virgules (ex: `111,222`). Si défini, remplace `TELEGRAM_CHAT_ID` |
| `TELEGRAM_CHAT_ID` | (requis si `CHAT_IDS` absent) | Fallback rétrocompat : un seul ID autorisé |
| `HTTP_PORT` | `8765` | Port du serveur HTTP local (raccourcis iOS). Ignoré si `HTTP_TOKEN` est vide |
| `HTTP_TOKEN` | `""` | Token secret protégeant le serveur HTTP. Si vide, le serveur ne démarre pas |
| `LANGUAGE` | `defaults.json/language` (`en`) | Langue des messages Telegram. Détermine quel `strings.<lang>.json` charger. Fallback sur `en` si la langue demandée n'existe pas |
| `SITE_NAME` | `""` | Préfixe ajouté à tous les messages, ex `maison` → `📍 maison — ` |
| `ALARM_SOUND` | `""` | Chemin du fichier audio. Si vide, défaut = `alarm.m4a` à côté du script |
| `ALARM_TEXT` | `strings.<lang>.json/alarm.default_text` | Texte TTS de fallback |
| `ALARM_VOICE` | `defaults.json/alarm.voicesByLanguage[LANGUAGE]` | Nom de la voix TTS (varie selon la langue : Daniel en `en`, Thomas en `fr`) |
| `ALARM_PITCH` | `defaults.json/alarm.pitch` | Multiplicateur de pitch sur enregistrements |
| `FFMPEG_BIN` | `"ffmpeg"` | Chemin du binaire ffmpeg (utile si pas dans le PATH du service) |
| `CAMERA_INDEX` | `defaults.json/camera.index` | Index OpenCV de la caméra |

### 8.3 Surcharge par variable d'environnement

Chaque champ de `defaults.json` peut être surchargé par une variable d'env nommée en `SCREAMING_SNAKE_CASE`. Exemple : `defaults.motion.cooldownSeconds` peut être surchargé par `MOTION_COOLDOWN_SECONDS` ou `COOLDOWN_SECONDS` (compat ascendante avec l'ancien `.env`).

L'implémentation doit accepter les deux noms pour rester rétrocompatible avec les `.env` existants.

---

## 8.4 Rétention des captures

Au démarrage du service, supprimer tous les fichiers de `captures/` plus vieux que `captures.retentionDays` jours (par défaut 30, surchargé par la variable d'env `RETENTION_DAYS`). Si la valeur est `0`, désactiver le nettoyage.

Les fichiers concernés sont les `motion_*.jpg`, `snapshot_*.jpg`, `voice_*.ogg`, `voice_*.audio`, et leurs WAV temporaires éventuellement orphelins.

L'opération doit être tolérante aux erreurs (un fichier locké, un permission denied) : log warning, continuer.

## 9. Sécurité

- La liste `CHAT_IDS` (peuplée depuis `TELEGRAM_CHAT_IDS` ou en fallback depuis `TELEGRAM_CHAT_ID`) est l'unique critère d'auth. Tout message dont ni `effective_chat.id` ni `effective_user.id` n'est dans la liste est silencieusement ignoré
- `CHAT_IDS` peut contenir indifféremment des chat_ids humains (conversation privée) et des user_ids de bots tiers (ex : bot raccourci Apple)
- Tous les IDs humains de la liste reçoivent les alertes de mouvement (burst), les messages de démarrage/arrêt, et les erreurs d'alarme
- `/snapshot` répond uniquement à l'utilisateur qui l'a demandé (son chat_id), pas à tous
- Le token Telegram doit être stocké hors du code source, dans `.env` ou équivalent secure storage de la plateforme
- Aucune commande ne permet l'arrêt distant du service par construction (pas de `/stop`) — mesure anti-foot-gun pour éviter de désactiver à distance la surveillance par accident
- Les fichiers téléchargés depuis Telegram (voice, audio) sont stockés sous `captures/` avec timestamp, pas de validation de contenu (l'auth chat_id est jugée suffisante)

---

## 10. Serveur HTTP local (raccourcis iOS)

Si `HTTP_TOKEN` est non vide au démarrage, le service expose un serveur HTTP sur `0.0.0.0:HTTP_PORT`.

### 10.1 Authentification

Chaque requête doit fournir le token en query param : `?token=<HTTP_TOKEN>`. Si le token est absent ou incorrect → HTTP 401 `{"ok": false, "error": "unauthorized"}`.

### 10.2 Endpoints

| Méthode | Chemin | Effet | Réponse succès |
|---------|--------|-------|----------------|
| GET | `/cmd/pause` | `paused = true` + broadcast `pause.paused` | `{"ok": true, "state": "paused"}` |
| GET | `/cmd/resume` | `paused = false` + broadcast `pause.resumed` | `{"ok": true, "state": "active"}` |
| GET | `/cmd/status` | Aucun | `{"ok": true, "state": "active"\|"paused"}` |

Commande inconnue → HTTP 400 `{"ok": false, "error": "unknown command: <cmd>"}`.

### 10.3 Sécurité

- Le serveur écoute sur `0.0.0.0` (toutes interfaces) mais n'est **pas exposé sur internet** : il est destiné à être atteint via un réseau privé (ex : Tailscale)
- Le `HTTP_TOKEN` doit être un secret long aléatoire (recommandé : `openssl rand -hex 20`)
- Les commandes `pause`/`resume` via HTTP envoient aussi une confirmation sur Telegram à tous les `CHAT_IDS`

---

## 12. Tests d'intégration end-to-end

Les tests sous `shared/e2e-tests/` utilisent un bot Telegram dédié au test et vérifient la conformité d'une implémentation à cette spec. Ils doivent passer sur Python ET sur l'app Android (via émulateur + ADB) avant tout merge.

Chaque section de cette spec correspond à au moins un test e2e. Voir `shared/e2e-tests/README.md` quand cela sera implémenté.
