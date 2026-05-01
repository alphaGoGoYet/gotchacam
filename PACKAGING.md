# Packaging et installation assistée

Note de continuation possible : transformer le projet en application packagée avec **wizard d'installation** (notamment pour la partie Telegram qui est aujourd'hui la plus pénible), de manière à ce qu'un non-développeur puisse l'installer en double-cliquant.

## Objectif

Aujourd'hui, installer le projet sur une nouvelle machine demande :
1. Installer Python + venv + dépendances (CLI)
2. Créer un bot Telegram via BotFather (manuel)
3. Récupérer son chat_id (CLI : `python get_chat_id.py`)
4. Éditer manuellement `.env`
5. Configurer le démarrage automatique (`launchd`, Task Scheduler, etc.)
6. Accorder la permission caméra

Cible avec un installeur packagé :
1. Double-clic sur `cam.dmg` / `cam-setup.exe` / `cam.apk`
2. Wizard guidé qui automatise tout sauf la création du bot (irréductible — Telegram n'a pas d'API pour ça)
3. À la fin, l'app tourne, démarre au boot, prête à recevoir des commandes

## Toolchain par plateforme

| OS | Bundler Python → app | Installeur | Format livré |
|----|---------------------|-----------|--------------|
| **macOS** | `briefcase` (BeeWare), `py2app`, ou `PyInstaller` | `create-dmg` | `cam.dmg` |
| **Windows** | `PyInstaller --onefile` | **Inno Setup** (gratuit, scripté) ou MSIX | `cam-setup.exe` |
| **Linux** | `PyInstaller` ou Nuitka | AppImage / Flatpak / `.deb` | `cam.AppImage` |
| **Android** | déjà natif via Android Studio | APK signé | `cam.apk` ou Play Store |

### Recommandation Mac/Win
Sur les deux, **PyInstaller** est le plus simple et bien documenté. `briefcase` est plus moderne et natif (produit un vrai `.app` Mac, plutôt qu'un script wrappé), mais plus jeune.

## La pièce maîtresse : le wizard de configuration

C'est là où le gain UX est énorme. Aujourd'hui le user doit suivre 5 étapes manuelles décrites dans le README. Le wizard les automatise toutes.

### Architecture proposée

Cross-platform en **PySide6** (Qt for Python) — un seul code pour Mac, Windows et Linux. Sur Android c'est l'app native qui héberge le même flux en Compose.

### Flow utilisateur en 5 écrans

```
┌──────────────────────────────────────────────────────────────────┐
│ [1/5] Bienvenue                                                  │
│       Présente ce que fait l'app, le matériel requis             │
│       → bouton "Suivant"                                         │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│ [2/5] Créer ton bot Telegram                                     │
│       Texte : "Tu vas créer un bot personnel via BotFather"      │
│       Bouton "Ouvrir BotFather dans Telegram"                    │
│         → deep link `tg://resolve?domain=BotFather`              │
│         → ouvre l'app/le web Telegram avec la conversation déjà  │
│           démarrée                                               │
│       Champ "Colle le token reçu de BotFather"                   │
│         → validation live via getMe API                          │
│         → ✓ vert si valide, ✗ rouge sinon                        │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│ [3/5] Lier ton compte                                            │
│       Texte : "Envoie n'importe quel message à ton bot"          │
│       Bouton "Ouvrir mon bot dans Telegram"                      │
│         → deep link `tg://resolve?domain=ton_bot_username`       │
│       Status spinner : "En attente de ton message..."            │
│         → l'app polle getUpdates en boucle (1 fois/seconde)      │
│         → dès qu'un message arrive de toi : chat_id capturé      │
│         → écran passe en vert : "✓ Connecté à @ton_username"     │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│ [4/5] Permissions caméra et test                                 │
│       Bouton "Tester la caméra"                                  │
│         → trigger TCC (Mac) / dialog Win / runtime perm Android  │
│         → prend une photo, l'envoie sur Telegram                 │
│         → "✓ Photo envoyée — vérifie ton chat Telegram"          │
└──────────────────────────────────────────────────────────────────┘
┌──────────────────────────────────────────────────────────────────┐
│ [5/5] Démarrage automatique                                      │
│       Choix : "Lancer cam au démarrage de l'ordinateur ?"        │
│         ○ Oui (recommandé)                                       │
│         ○ Non, je lancerai manuellement                          │
│       Bouton "Terminer"                                          │
│         → écrit le LaunchAgent / la tâche planifiée / boot recv  │
│         → démarre le service immédiatement                       │
└──────────────────────────────────────────────────────────────────┘
```

À la fin, l'utilisateur a une app installée, configurée, démarrée, qui tournera toute seule au prochain reboot. **Zéro CLI, zéro édition de `.env`.**

### Code skeleton du flow Telegram (PySide6)

```python
# wizard/telegram_setup.py
import asyncio
import httpx

API = "https://api.telegram.org"


async def validate_token(token: str) -> dict | None:
    """Returns bot info dict if token valid, None otherwise."""
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.get(f"{API}/bot{token}/getMe")
            data = r.json()
            return data["result"] if data.get("ok") else None
        except Exception:
            return None


async def wait_for_first_message(token: str, timeout: float = 600) -> int | None:
    """Polls getUpdates until any user sends a message. Returns their chat_id."""
    offset = None
    deadline = asyncio.get_event_loop().time() + timeout
    async with httpx.AsyncClient(timeout=30) as client:
        while asyncio.get_event_loop().time() < deadline:
            params = {"timeout": 25}
            if offset is not None:
                params["offset"] = offset
            try:
                r = await client.get(f"{API}/bot{token}/getUpdates", params=params)
                data = r.json()
                if data.get("ok") and data["result"]:
                    for upd in data["result"]:
                        if "message" in upd:
                            return upd["message"]["chat"]["id"]
                        offset = upd["update_id"] + 1
            except Exception:
                await asyncio.sleep(2)
    return None
```

C'est ~30 lignes de logique brute. Le reste du wizard est de l'UI Qt (formulaires, transitions entre écrans).

## Structure du projet packagé

```
cam_packaged/
├── cam.py                       # le code actuel (cross-platform après refactor)
├── audio_backend.py             # nouveau (cf. WINDOWS_PORT.md)
├── wizard/                      # nouveau
│   ├── __main__.py              # point d'entrée du wizard
│   ├── ui_main.py               # PySide6 — fenêtre + steps
│   ├── telegram_setup.py        # validation token + wait_for_first_message
│   ├── autostart.py             # abstrait launchd / Task Scheduler / systemd
│   └── permissions.py           # déclenche les prompts OS
├── installer/                   # nouveau
│   ├── macos/
│   │   ├── build_dmg.sh         # briefcase + create-dmg
│   │   └── entitlements.plist   # pour la signature
│   ├── windows/
│   │   └── setup.iss            # script Inno Setup
│   └── linux/
│       └── AppImage.sh
└── ci/                          # nouveau
    └── github-actions.yml       # build des 3 OS à chaque tag git
```

CI/CD : un workflow GitHub Actions qui à chaque tag git produit `cam-1.2.0.dmg`, `cam-1.2.0-setup.exe` et `cam-1.2.0.AppImage` automatiquement.

## Coût des certificats de signature

Sans signature, les OS modernes affichent des avertissements effrayants au premier lancement. Les certificats permettent de les supprimer.

### Apple Developer Program — ~90 €/an (99 $)

**Sans** : l'utilisateur double-clique l'app, reçoit le message :
> *Apple n'a pas pu vérifier que cette app ne contient pas de logiciel malveillant susceptible d'endommager votre Mac.*

Le seul bouton est **« Déplacer vers la corbeille »**. Il faut savoir faire **clic droit → Ouvrir** pour avoir un bouton « Ouvrir quand même ».

**Avec** :
- Certificat Developer ID Application (signature)
- Service de notarisation Apple (scan anti-malware automatique, illimité)
- Accès à TestFlight et au Mac App Store en bonus

### Windows Code Signing Certificate — 300-400 €/an pour EV

**Sans signature** : SmartScreen affiche
> *Windows a protégé votre PC. Microsoft Defender SmartScreen a empêché le démarrage d'une application non reconnue.*

L'utilisateur doit cliquer **« Plus d'infos »** puis **« Exécuter quand même »** (bouton parfois caché).

**Avec un certificat standard** (~60-100 €/an, Sectigo, DigiCert...) : SmartScreen affiche **encore l'avertissement** jusqu'à ce que l'app accumule de la « réputation » (~10 000 téléchargements selon les heuristiques Microsoft). Au début, expérience identique à sans signature.

**Avec un certificat EV (Extended Validation)** : réputation **immédiate** dès le premier téléchargement. Plus aucun avertissement. C'est le seul moyen d'avoir un parcours user propre du jour 1.

**Alternative récente** : depuis 2024, Microsoft propose **Azure Trusted Signing** à ~10 $/mois (~120 €/an), bien moins cher qu'un EV traditionnel. Pas encore mainstream mais viable.

### Android — 25 $ une seule fois (Play Store)

Pas annuel, c'est un frais d'inscription unique au Google Play Console. Sinon F-Droid ou sideload APK : **0 €**.

### Total annuel récurrent

| Plateforme | Coût |
|------------|------|
| macOS (Apple Developer) | 90 € |
| Windows (EV cert) | 300 € |
| Android (Play Store) | 25 $ une fois, 0 récurrent |
| **Total annuel** | **~390 €** |

## Quand tu peux totalement t'en passer

**Usage perso ou cercle restreint** (toi + famille + 2-3 amis) : **0 €**. Tu fournis l'app non-signée et tu écris dans le README :

> *Au premier lancement, macOS / Windows va afficher un avertissement parce que l'app n'est pas signée. C'est normal — fais clic droit sur l'app → Ouvrir, puis dans le pop-up clique sur Ouvrir quand même. Une fois fait, plus jamais d'avertissement.*

Avec deux screenshots, c'est largement faisable pour des proches. **L'app fonctionne strictement à l'identique** une fois passé l'avertissement initial.

**Distribution publique** (forums, Reddit, blog, etc.) : là les avertissements provoquent un taux d'abandon massif (~80% des utilisateurs cliquent « Annuler » à l'écran SmartScreen). À ce stade-là les certificats deviennent indispensables.

## Difficultés à anticiper

1. **Bundling OpenCV** — `pip install opencv-python` pèse ~100 MB. Une fois bundlé en `.app`/`.exe`, on monte à **80-150 MB**. Acceptable pour une app de surveillance, mais bien plus gros qu'un installeur classique. Alternative : `opencv-python-headless` qui est ~30% plus léger
2. **Updates** — l'installeur fait l'install initial, pas les MAJ. Solutions :
   - `Sparkle` (Mac, gratuit, standard de fait)
   - `WinSparkle` (Windows, port de Sparkle)
   - In-app updater maison (~1 weekend)
   - Ou simplement « ré-installer la nouvelle version » à chaque release
3. **Antivirus tiers (Windows)** — certains AV (Bitdefender, Norton…) flaggent les binaires PyInstaller comme suspects. Signature EV résout. Sans signature : whitelisting manuel par utilisateur
4. **Auto-désactivation des optimisations batterie (Android, Samsung surtout)** — pas atteignable par programme sur certains OEM. Le wizard peut afficher les screenshots du chemin manuel pour ces cas
5. **Gatekeeper sur Mac M1/M2 avec app non signée** — encore plus strict que sur Intel. Le `clic droit → Ouvrir` reste possible mais peut nécessiter l'option supplémentaire « Ouvrir quand même » dans Réglages → Confidentialité après le 1er essai
6. **Code-signing macOS et notarisation** — workflow complexe (signature → upload à Apple → attendre la notarisation → stapling). Compter ~half-day pour le mettre en place la 1ère fois, ensuite c'est CI

## Phasage suggéré

**Phase 1 — refactor cross-platform** (~3 h) : extraire `audio_backend.py` (cf. WINDOWS_PORT.md)

**Phase 2 — wizard PySide6 fonctionnel** (~2 weekends) :
- 5 écrans
- Validation token + auto-détection chat_id
- Trigger des permissions
- Écriture autostart par OS

**Phase 3 — bundling Mac** (~1 weekend, sans signature) : `briefcase build` + DMG

**Phase 4 — bundling Windows** (~1 weekend) : PyInstaller + Inno Setup

**Phase 5 — CI build** (~1 weekend) : GitHub Actions → 3 binaires automatiquement à chaque tag

**Phase 6 — code signing** (~1 weekend, optionnel) : Apple Developer + soit Sectigo standard soit Azure Trusted Signing

Total **5-6 weekends** pour un produit propre, **+1 weekend** si signature nécessaire.

## Verdict pour ton cas

Pour une distribution à **moins de 5 personnes que tu connais** : **0 € budget cert**, fournis l'app non-signée + screenshots du contournement. Le wizard d'install reste pertinent (gain UX énorme).

Pour **publication publique** : prévoir 390 €/an de certificats + ~6 weekends de dev + un mécanisme d'updates. À ce stade, le projet est devenu un produit.

## Référence du code Python actuel

Au moment du packaging, le code à embarquer reste celui présent dans :
- `cam.py` (logique principale, après refactor cross-platform)
- `audio_backend.py` (nouveau, cf. WINDOWS_PORT.md)
- `requirements.txt` (à compléter avec `pyside6`, `httpx`, `pycaw` (Win), `pyttsx3` (Win))
- `README.md` pour la doc utilisateur post-install
