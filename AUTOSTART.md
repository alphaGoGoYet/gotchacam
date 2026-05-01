# Démarrage automatique sur macOS

Le script peut être lancé automatiquement à chaque ouverture de session via `launchd` (le système d'init de macOS), avec redémarrage automatique en cas de crash.

## Installation (sur chaque Mac)

Pré-requis :
- `.venv/` créé et `requirements.txt` installé
- `.env` rempli (token Telegram + chat_id)

Une seule commande, depuis le dossier du projet :

```bash
bash install_autostart.sh
```

Le script :
1. Génère un fichier `~/Library/LaunchAgents/com.goyet.cam.plist` adapté au chemin du projet
2. Charge le service via `launchctl`
3. Vérifie qu'il tourne

Tu reçois ensuite `🎥 cam started` sur Telegram (préfixé par `SITE_NAME` si défini).

## Vérifier l'état

```bash
launchctl list | grep com.goyet.cam
```

Affiche `<PID>  <exit_code>  com.goyet.cam` si le service tourne. Un PID `-` indique qu'il a planté ou n'est pas démarré.

## Suivre les logs

```bash
tail -f cam.log cam.err
```

Les deux fichiers sont écrits dans le dossier du projet par `launchd`.

## Arrêter / redémarrer / désinstaller

| Action | Commande |
|--------|----------|
| Arrêter (jusqu'au prochain login) | `launchctl unload ~/Library/LaunchAgents/com.goyet.cam.plist` |
| Relancer après arrêt | `launchctl load ~/Library/LaunchAgents/com.goyet.cam.plist` |
| Forcer un redémarrage immédiat | `launchctl kickstart -k gui/$(id -u)/com.goyet.cam` |
| Désinstaller | `launchctl unload ~/Library/LaunchAgents/com.goyet.cam.plist && rm ~/Library/LaunchAgents/com.goyet.cam.plist` |

## Comportement à connaître

### KeepAlive
Le service redémarre **automatiquement** :
- s'il plante (webcam débranchée, erreur réseau...)
- s'il s'arrête tout seul, même via `Ctrl+C` ou `kill`

C'est volontaire : un appui accidentel ou un plantage ne te laisse pas sans surveillance. Pour vraiment l'arrêter (ex: tu rentres chez toi le soir et tu veux ta vie privée), utilise `launchctl unload`.

### Permission caméra
Au tout premier démarrage par `launchd`, macOS affiche une popup demandant l'accès caméra pour Python. **Accepte**.

Si la popup n'apparaît pas et que `cam.err` contient une erreur d'accès caméra :
1. **Réglages Système → Confidentialité et sécurité → Caméra**
2. Active l'interrupteur pour `python` (le binaire du venv)
3. Si Python n'apparaît pas dans la liste, force un redémarrage du service : `launchctl kickstart -k gui/$(id -u)/com.goyet.cam`

### Mise en veille
`launchd` ne réveille pas le Mac. Si la machine dort, le script ne tourne pas. Pour qu'il reste actif quand tu n'es pas à la maison :
- **Réglages Système → Batterie** (ou Énergie) → coche **« Empêcher la mise en veille automatique quand l'écran est éteint »**
- Sur portable : reste sur secteur, ou ferme le capot avec écran/clavier externe branché

### Mises à jour du code ou du `.env`
Le fichier `.env` est lu **une seule fois au démarrage du script** (idem pour le code de `cam.py`). Si tu modifies n'importe quel réglage — `SITE_NAME`, `MIN_AREA`, `BURST_COUNT`, `TELEGRAM_BOT_TOKEN`, etc. — il faut forcer un redémarrage pour que la nouvelle valeur soit prise en compte :

```bash
launchctl kickstart -k gui/$(id -u)/com.goyet.cam
```

Cette commande tue l'instance courante ; `KeepAlive` en relance immédiatement une nouvelle qui re-lit `.env`. Tu sauras que c'est pris en compte si le message `🎥 cam started` sur Telegram reflète tes changements (par exemple le nouveau préfixe `📍 …`).
