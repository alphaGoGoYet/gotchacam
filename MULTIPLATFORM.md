# Architecture multi-plateforme

Ce projet doit fonctionner sur macOS (implémentation Python actuelle) et Android (implémentation Kotlin native, à venir). Pour garantir un comportement **identique** entre les deux plateformes sans dupliquer le code, on isole tout ce qui peut être partagé dans le dossier [shared/](shared/).

## Principe

```
┌──────────────────────────────────────────────────────┐
│                shared/  (source de vérité)           │
│  ┌────────────────┐  ┌─────────────────────────┐    │
│  │ defaults.json  │  │ strings.fr.json         │    │
│  │ (constantes)   │  │ (messages Telegram)     │    │
│  └────────┬───────┘  └────────┬────────────────┘    │
│  ┌────────────────┐  ┌─────────────────────────┐    │
│  │ commands.json  │  │ BEHAVIOR_SPEC.md        │    │
│  │ (cmds bot)     │  │ (spec formelle)         │    │
│  └────────┬───────┘  └────────┬────────────────┘    │
│           │                   │                      │
│  ┌────────────────┐  ┌─────────────────────────┐    │
│  │ alarm-default  │  │ e2e-tests/              │    │
│  │ .m4a (asset)   │  │ (tests intégration)     │    │
│  └────────┬───────┘  └────────┬────────────────┘    │
└───────────┼────────────────────┼─────────────────────┘
            │                    │
   ┌────────┴───────┐   ┌────────┴────────┐
   │ macos/         │   │ android/        │
   │ (Python)       │   │ (Kotlin)        │
   │                │   │                 │
   │ cam.py lit les │   │ Gradle copie    │
   │ JSON au runtime│   │ les JSON dans   │
   │                │   │ assets/ au build│
   └────────────────┘   └─────────────────┘
```

## Inventaire de `shared/`

| Fichier | Format | Rôle | Lu par |
|---------|--------|------|--------|
| [shared/defaults.json](shared/defaults.json) | JSON | Constantes (motion threshold, burst count, alarm pitch, etc.) | runtime des deux impls |
| [shared/strings.fr.json](shared/strings.fr.json) | JSON | Messages Telegram en français, avec placeholders `{name}` | runtime des deux impls |
| [shared/commands.json](shared/commands.json) | JSON | Liste des commandes bot et descriptions | les deux impls pour enregistrer les handlers |
| [shared/BEHAVIOR_SPEC.md](shared/BEHAVIOR_SPEC.md) | Markdown | **Spec formelle** : la source de vérité du comportement | référence pour les devs et les tests |
| `shared/alarm-default.m4a` (à créer si besoin) | Audio M4A | Fichier d'alarme par défaut bundlé | les deux impls (macOS via fs, Android via raw resource) |
| `shared/e2e-tests/` (à créer plus tard) | Python | Tests d'intégration end-to-end | CI commune contre les deux impls |

## Côté Python (macOS)

Au démarrage, [cam.py](cam.py) charge les JSON :

```python
from pathlib import Path
import json

SHARED = Path(__file__).parent / "shared"
DEFAULTS = json.loads((SHARED / "defaults.json").read_text())
STRINGS = json.loads((SHARED / "strings.fr.json").read_text())
```

Ensuite chaque variable d'env surcharge la valeur par défaut :

```python
COOLDOWN_SECONDS = float(os.getenv("COOLDOWN_SECONDS", DEFAULTS["motion"]["cooldownSeconds"]))
```

Les messages Telegram utilisent `str.format()` avec les placeholders du JSON :

```python
await update.message.reply_text(
    STRINGS["alarm"]["started"].format(source=STRINGS["alarm"]["source_recording"])
)
```

## Côté Kotlin (Android, à venir)

Le plugin Gradle copiera `shared/*.json` dans le dossier `assets/` de l'APK au build. À l'exécution, on lit avec un parser JSON (kotlinx.serialization) :

```kotlin
val defaults = Json.decodeFromString<Defaults>(
    context.assets.open("defaults.json").bufferedReader().readText()
)
val cooldown = BuildConfig.COOLDOWN_SECONDS_OVERRIDE ?: defaults.motion.cooldownSeconds
```

Les strings utilisent un wrapper qui imite `str.format` :

```kotlin
fun s(key: String, vararg pairs: Pair<String, Any>): String {
    var template = STRINGS.getNested(key)
    for ((k, v) in pairs) template = template.replace("{$k}", v.toString())
    return template
}

reply(s("alarm.started", "source" to s("alarm.source_recording")))
```

## Discipline de modification

**Règle fondamentale** : si tu changes le comportement, tu modifies en cascade dans cet ordre :

1. **`shared/BEHAVIOR_SPEC.md`** d'abord — décris ce que ça doit faire
2. **`shared/defaults.json`** ou **`shared/strings.fr.json`** si concerné — change la valeur
3. **`cam.py`** (Python) — implémente
4. **App Android** — implémente
5. **`shared/e2e-tests/`** — ajoute/modifie le test
6. Vérifie que les deux implémentations passent le test

Si tu ne respectes pas cet ordre, tu vas inévitablement avoir une dérive entre les deux versions.

**Antipattern** : modifier `cam.py` directement sans toucher la spec. Au bout de 3 mois, tu te demandes pourquoi l'app Android n'a pas le même comportement, et tu n'as plus de référence claire.

## Ce qui reste **non partagé** (et c'est normal)

- Capture vidéo : OpenCV en Python, CameraX en Kotlin — APIs différentes
- Audio playback : `afplay` / `say` côté macOS, `MediaPlayer` / `TextToSpeech` côté Android
- Volume control : `osascript` côté macOS, `AudioManager.STREAM_*` côté Android
- Service en background : `launchd` côté macOS, `ForegroundService` côté Android
- Permissions : TCC côté macOS, runtime permissions côté Android

Ces couches s'**implémentent indépendamment** mais doivent toutes respecter la spec abstraite définie dans `BEHAVIOR_SPEC.md`.

## Workflow pour ajouter une feature

Exemple : ajouter une commande `/temperature` qui retourne la température CPU.

1. Éditer `shared/BEHAVIOR_SPEC.md` :
   ```markdown
   ### 4.9 `/temperature`
   - Réponse : `temperature.label` formaté avec `value = température CPU en °C, 1 décimale`
   ```
2. Éditer `shared/commands.json` : ajouter l'entrée
3. Éditer `shared/strings.fr.json` :
   ```json
   "temperature": { "label": "🌡️ {value}°C" }
   ```
4. Implémenter `cmd_temperature` dans `cam.py` (utilise `osx-cpu-temp` ou équivalent)
5. Implémenter `cmdTemperature` dans l'app Android (utilise `Sensor.TYPE_AMBIENT_TEMPERATURE` ou lecture `/sys/...`)
6. Ajouter le test e2e
7. Push, vérifier que CI passe sur les deux

À chaque étape, **les deux implémentations sont en synchro** parce qu'elles consomment les mêmes assets.

## Pourquoi ce niveau d'effort

Pour un projet solo de 1 implémentation, c'est de l'over-engineering. Pour un projet **2 implémentations** dans **2 langages**, c'est l'investissement minimum pour ne pas dériver à 6 mois.

Sans cette discipline :
- Tu changes `MIN_AREA` dans Python pour réduire les faux positifs
- Tu oublies de le faire dans Kotlin
- Pendant un mois, les utilisateurs Android ont 3x plus d'alertes que les macOS
- Tu cherches le bug en croyant que c'est un problème de capteur

Avec cette discipline :
- Tu changes `MIN_AREA` dans `defaults.json`
- Les deux apps reprennent la nouvelle valeur au prochain build
- Aucune dérive possible

## Coût d'entrée

L'extraction initiale du Python actuel vers `shared/` représente ~1 weekend (déjà fait dans le commit qui crée ce document). Toute évolution future bénéficie de l'investissement, sans coût récurrent.

## Référence

Tous les fichiers concrets sont dans le sous-dossier [shared/](shared/). Pour comprendre un comportement précis, lire [shared/BEHAVIOR_SPEC.md](shared/BEHAVIOR_SPEC.md). Pour comprendre la valeur d'une constante, lire [shared/defaults.json](shared/defaults.json). Pour le texte exact d'un message, lire [shared/strings.fr.json](shared/strings.fr.json).
