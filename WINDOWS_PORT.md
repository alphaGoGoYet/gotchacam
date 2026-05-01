# Portage Windows

Note de continuation possible : faire tourner `cam.py` sur un PC Windows (Windows 10/11). Beaucoup plus simple que le portage Android : Python, OpenCV et `python-telegram-bot` sont déjà cross-platform — seules trois primitives macOS-only sont à remplacer.

## Ce qui fonctionne sans modification

- `cam.py` (toute la logique asyncio, capture, détection, burst, commandes Telegram, lifecycle caméra avec pause)
- `requirements.txt` (les 3 paquets s'installent pareil avec `pip`)
- `get_chat_id.py`
- `.env`, structure du projet, conventions de captures
- Le format `alarm.m4a` (lu par `ffplay` ou `playsound` sans souci)

## Ce qui doit être adapté

| Bloc actuel (macOS) | Équivalent Windows | Effort |
|---------------------|---------------------|--------|
| `subprocess afplay alarm.m4a` | `subprocess ffplay -nodisp -autoexit alarm.m4a` *(ffmpeg dispo via `winget install ffmpeg`)*, ou bibliothèque `playsound` / `winsound` (WAV uniquement) | trivial |
| `osascript` pour volume sortie | **`pycaw`** — `pip install pycaw` — accède à Windows Core Audio API | ~15 lignes |
| `say -v Thomas "..."` | **`pyttsx3`** — `pip install pyttsx3` — wrapper cross-platform qui utilise SAPI5 sur Windows | trivial |
| `launchd` LaunchAgent | **Planificateur de tâches Windows** *(Task Scheduler)* avec déclencheur "À l'ouverture de session" + redémarrage automatique en cas d'arrêt | une fois |
| Permission caméra (TCC) | Paramètres → Confidentialité et sécurité → Caméra → activer pour les applications de bureau / Python | trivial |
| Empêcher la mise en veille | **`powercfg`** ou Paramètres → Alimentation → Jamais en veille | trivial |

## Architecture cible : `cam.py` cross-platform

Plutôt que de dupliquer le projet, on isole les 3 opérations macOS-only dans un module `audio_backend.py` qui sélectionne l'implémentation au runtime :

```python
# audio_backend.py
import sys, asyncio

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")


async def play_file(path: str) -> asyncio.subprocess.Process:
    if IS_MAC:
        return await asyncio.create_subprocess_exec("afplay", path)
    if IS_WIN:
        return await asyncio.create_subprocess_exec(
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path
        )
    if IS_LINUX:
        return await asyncio.create_subprocess_exec("ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path)
    raise RuntimeError(f"unsupported platform: {sys.platform}")


async def get_volume() -> int | None:
    if IS_MAC:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", "output volume of (get volume settings)",
            stdout=asyncio.subprocess.PIPE,
        )
        out, _ = await proc.communicate()
        return int(out.decode().strip())
    if IS_WIN:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        return int(volume.GetMasterVolumeLevelScalar() * 100)
    return None


async def set_volume(level: int) -> None:
    level = max(0, min(100, level))
    if IS_MAC:
        await (await asyncio.create_subprocess_exec(
            "osascript", "-e", f"set volume output volume {level}",
        )).wait()
    elif IS_WIN:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100, None)


async def speak(text: str, voice: str | None = None) -> None:
    if IS_MAC:
        args = ["say"]
        if voice:
            args += ["-v", voice]
        args.append(text)
        await (await asyncio.create_subprocess_exec(*args)).wait()
    elif IS_WIN:
        # pyttsx3 est synchrone — on le pousse dans un thread pour ne pas bloquer la loop
        import pyttsx3
        loop = asyncio.get_running_loop()
        def _say():
            engine = pyttsx3.init()
            if voice:
                for v in engine.getProperty("voices"):
                    if voice.lower() in v.name.lower():
                        engine.setProperty("voice", v.id)
                        break
            engine.say(text)
            engine.runAndWait()
        await loop.run_in_executor(None, _say)
```

Ensuite dans `cam.py` on remplace les appels directs par :

```python
from audio_backend import play_file, get_volume, set_volume, speak
```

→ environ **50 lignes** à factoriser, après quoi le projet tourne sur Mac, Windows et Linux indifféremment.

## Setup d'une machine Windows (à documenter le jour J)

### 1. Installer les pré-requis
```powershell
winget install Python.Python.3.12
winget install Gyan.FFmpeg
```

### 2. Cloner / copier le projet
```powershell
cd $HOME\Development
# copier le dossier cam ici
cd cam
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install pycaw pyttsx3 comtypes  # extras Windows
copy .env.example .env
notepad .env  # remplir TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, etc.
```

### 3. Démarrage automatique via Task Scheduler

Créer une tâche planifiée qui :
- Se déclenche **« À l'ouverture de session »** de l'utilisateur
- Lance `C:\path\to\cam\.venv\Scripts\python.exe C:\path\to\cam\cam.py`
- Coche **« Redémarrer en cas d'échec, jusqu'à 99 fois, toutes les 1 minutes »** (équivalent KeepAlive)
- Coche **« Exécuter même si l'utilisateur n'est pas connecté »** ✗ → laisse décoché (on a besoin de la session pour la caméra)

Script PowerShell d'installation possible :

```powershell
$action = New-ScheduledTaskAction -Execute "$PWD\.venv\Scripts\python.exe" -Argument "$PWD\cam.py" -WorkingDirectory $PWD
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -RestartCount 99 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "cam" -Action $action -Trigger $trigger -Settings $settings
```

### 4. Empêcher la mise en veille
```powershell
powercfg /change standby-timeout-ac 0
powercfg /change monitor-timeout-ac 5  # éteindre l'écran après 5 min, OK
```

### 5. SSH (optionnel, pour kickstart à distance comme on a fait sur le Mac)
- Paramètres → Applications → Fonctionnalités facultatives → ajouter **« OpenSSH Server »**
- `Set-Service -Name sshd -StartupType Automatic; Start-Service sshd`
- Ouvrir le port 22 dans le pare-feu Windows
- Copier la clé publique dans `C:\Users\<user>\.ssh\authorized_keys` (créer le dossier si absent, attention aux ACL)

## Difficultés Windows-spécifiques à anticiper

1. **`pycaw` setup** — nécessite `comtypes` et un Windows récent (10/11). Sur certaines builds OEM ou versions LTSC il peut y avoir des soucis ; le fallback est de tomber dans un mode "no volume control" plutôt que de planter
2. **Volume = volume maître** — pycaw modifie le volume système global, pas un canal d'alarme dédié comme `STREAM_ALARM` sur Android. Si l'utilisateur a Spotify qui joue en parallèle, le volume change pour tout
3. **Voix SAPI françaises** — qualité inférieure à celles de macOS (Thomas/Audrey). Il existe quelques voix premium tierces (Acapela, Cereproc) payantes si la qualité importe vraiment. Sinon, l'alarme se base déjà sur `alarm.m4a` (enregistrement perso) → la voix de synthèse n'est qu'un fallback
4. **Antivirus** — certains AV signalent les scripts Python qui prennent des photos en arrière-plan. Whitelister le dossier au cas où
5. **Caméra sur portable Windows** — souvent une LED qui s'allume, parfois désactivable via le BIOS/UEFI selon le constructeur (Lenovo, Dell ont un toggle "Privacy LED")

## Verdict d'effort

- **Phase 1 — refactor cross-platform de `cam.py`** : ~3 heures (extraction des 3 primitives audio dans `audio_backend.py`, tests sur Mac que rien ne casse)
- **Phase 2 — installation sur une machine Windows + script d'autostart** : ~2 heures
- **Phase 3 — tests bout-en-bout** : 1 heure

Total : **un weekend tranquille** vs ~5 weekends pour Android natif.

## Avantages d'un PC Windows comme cible

- Énormément de vieux PC dorment dans les placards (réutilisation gratuite)
- Hardware caméra varié (souvent objectifs corrects, parfois LED désactivable au BIOS)
- Aucune permission TCC à débloquer (Windows demande l'autorisation caméra une fois, point)
- Task Scheduler beaucoup plus prévisible que `launchd` pour le démarrage
- Si c'est un Mini PC NUC ou équivalent fanless : conso 5-15 W en idle, parfait 24/7
- SSH activable nativement depuis Windows 10 → workflow distant identique à ce qu'on a fait sur Mac

## Référence du code Python actuel

À conserver à l'identique pendant le refactor cross-platform :
- Toute la logique de `cam.py` autour de `camera_loop`, `capture_burst`, `cmd_alarm`/`cmd_stopalarm`, `_alarm_loop`
- Variables d'environnement de `.env.example`
- Structure des commandes Telegram documentée dans `README.md` (compatibilité user-facing)
