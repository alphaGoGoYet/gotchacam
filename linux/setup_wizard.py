#!/usr/bin/env python3
"""Assistant de configuration interactif (Linux / Raspberry Pi).

Pose les questions nécessaires (token Telegram, chat ID, caméra, sortie audio…)
et écrit le fichier .env à la racine du projet. Lancé par linux/install.sh avec
le Python du venv (pour pouvoir tester la caméra avec OpenCV), mais utilisable
seul : `.venv/bin/python linux/setup_wizard.py`.

Options :
  --offline   ne contacte pas Telegram (validation du token et détection du chat ID
              désactivées, saisie manuelle) — utile pour les tests.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = Path(os.environ.get("CAM_ENV_PATH", PROJECT_DIR / ".env"))
OFFLINE = "--offline" in sys.argv


# ── Saisie ────────────────────────────────────────────────────────────────

def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"{prompt}{suffix} : ").strip()
    except EOFError:
        print()
        sys.exit("Saisie interrompue.")
    return value or default


def ask_yes_no(prompt: str, default: bool = True) -> bool:
    hint = "O/n" if default else "o/N"
    while True:
        value = ask(f"{prompt} ({hint})").lower()
        if not value:
            return default
        if value in ("o", "oui", "y", "yes"):
            return True
        if value in ("n", "non", "no"):
            return False


def ask_int(prompt: str, default: int, minimum: int = 0) -> int:
    while True:
        raw = ask(prompt, str(default))
        try:
            value = int(raw)
            if value >= minimum:
                return value
        except ValueError:
            pass
        print(f"  Entre un nombre entier ≥ {minimum}.")


def choose(prompt: str, options: list[str], default: int = 0) -> int:
    """Affiche une liste numérotée, retourne l'index choisi."""
    for i, label in enumerate(options, 1):
        print(f"  {i}) {label}")
    while True:
        raw = ask(prompt, str(default + 1))
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print(f"  Entre un numéro entre 1 et {len(options)}.")


def title(text: str) -> None:
    print(f"\n── {text} " + "─" * max(3, 60 - len(text)))


def run(cmd: list[str], timeout: float = 10) -> str:
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        ).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


# ── .env existant ─────────────────────────────────────────────────────────

def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
    return values


# ── Telegram ──────────────────────────────────────────────────────────────

def telegram_call(token: str, method: str, timeout: float = 15) -> dict | None:
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except ValueError:
            return None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None


def step_telegram(old: dict[str, str]) -> tuple[str, list[int], str]:
    title("Telegram : le bot")
    print(
        "Il faut un bot Telegram. Si tu n'en as pas :\n"
        "  1. Ouvre Telegram, cherche @BotFather\n"
        "  2. Envoie /newbot et suis les instructions\n"
        "  3. Copie le token qu'il te donne (forme 123456789:ABC...)"
    )
    default_token = old.get("TELEGRAM_BOT_TOKEN", "")
    bot_name = ""
    while True:
        token = ask("Token du bot", default_token)
        if not re.fullmatch(r"\d+:[A-Za-z0-9_-]{20,}", token):
            print("  Format invalide (attendu : chiffres, ':', puis lettres/chiffres).")
            default_token = ""
            continue
        if OFFLINE:
            break
        reply = telegram_call(token, "getMe")
        if reply is None:
            print("  Telegram injoignable : vérifie la connexion internet du Raspberry Pi.")
            if ask_yes_no("  Continuer sans valider le token ?", False):
                break
        elif reply.get("ok"):
            bot_name = reply["result"].get("username", "")
            print(f"  ✓ Bot reconnu : @{bot_name}")
            break
        else:
            print(f"  ✗ Token refusé par Telegram ({reply.get('description', 'erreur inconnue')}).")
        default_token = ""

    title("Telegram : qui est autorisé")
    ids = detect_chat_ids(token, bot_name) if not OFFLINE else []
    old_ids = old.get("TELEGRAM_CHAT_IDS") or old.get("TELEGRAM_CHAT_ID", "")
    if not ids and old_ids:
        ids = [int(x) for x in re.findall(r"-?\d+", old_ids)]
        print(f"  IDs déjà configurés conservés : {', '.join(map(str, ids))}")
    while not ids:
        raw = ask("Chat ID (plusieurs possibles, séparés par des virgules)")
        ids = [int(x) for x in re.findall(r"-?\d+", raw)]
        if not ids:
            print("  Aucun ID valide.")
    while ask_yes_no("Autoriser une autre personne (autre chat ID) ?", False):
        extra = [int(x) for x in re.findall(r"-?\d+", ask("Chat ID supplémentaire"))]
        ids += [i for i in extra if i not in ids]
    return token, ids, bot_name


def detect_chat_ids(token: str, bot_name: str) -> list[int]:
    """Attend qu'un message arrive au bot et en déduit le chat ID de l'expéditeur."""
    who = f"@{bot_name}" if bot_name else "ton bot"
    print(f"Ouvre Telegram et envoie un message (ex. « salut ») à {who}.")
    print("J'attends jusqu'à 90 s ; laisse vide + Ctrl+C pour saisir l'ID à la main.")
    found: dict[int, str] = {}
    deadline = time.time() + 90
    try:
        while time.time() < deadline and not found:
            reply = telegram_call(token, "getUpdates?timeout=5&allowed_updates=%5B%22message%22%5D", 15)
            if reply is None:
                time.sleep(2)
                continue
            if not reply.get("ok"):
                if reply.get("error_code") == 409:
                    print("  Le service cam tourne déjà et utilise le bot : saisie manuelle.")
                    return []
                break
            for upd in reply.get("result", []):
                chat = upd.get("message", {}).get("chat", {})
                if "id" in chat:
                    name = chat.get("first_name") or chat.get("title") or chat.get("username") or "?"
                    found[chat["id"]] = name
    except KeyboardInterrupt:
        print()
    if not found:
        print("  Aucun message reçu.")
        return []
    ids = []
    for cid, name in found.items():
        if ask_yes_no(f"  Autoriser {name} (ID {cid}) ?", True):
            ids.append(cid)
    return ids


# ── Caméra ────────────────────────────────────────────────────────────────

def v4l_name(index: int) -> str:
    p = Path(f"/sys/class/video4linux/video{index}/name")
    return p.read_text().strip() if p.exists() else f"video{index}"


def probe_cameras() -> list[tuple[int, str, tuple[int, int]]]:
    """Retourne les caméras capables de fournir une image : (index, nom, (largeur, hauteur)).
    Sur un Raspberry Pi il y a beaucoup de /dev/video* (codec, ISP…) qui ne sont pas des caméras :
    on ne garde que ceux d'où OpenCV arrive vraiment à lire une image."""
    try:
        import cv2
    except ImportError:
        return []
    cams = []
    indexes = sorted(
        int(m.group(1)) for p in Path("/dev").glob("video*") if (m := re.fullmatch(r"video(\d+)", p.name))
    )
    for i in indexes:
        cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
        try:
            if cap.isOpened():
                for _ in range(3):  # les premières images sont souvent noires/vides
                    ok, frame = cap.read()
                if ok and frame is not None:
                    h, w = frame.shape[:2]
                    cams.append((i, v4l_name(i), (w, h)))
        finally:
            cap.release()
    return cams


def test_photo(index: int, width: int, height: int) -> Path | None:
    import cv2
    cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
    try:
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        if width and height:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        frame = None
        for _ in range(10):
            ok, frame = cap.read()
            time.sleep(0.1)
        if not ok or frame is None:
            return None
        path = PROJECT_DIR / "camera_test.jpg"
        cv2.imwrite(str(path), frame)
        return path
    finally:
        cap.release()


RESOLUTIONS = [("1280x720 (recommandé)", 1280, 720), ("640x480 (plus léger)", 640, 480), ("1920x1080 (lourd pour un Pi)", 1920, 1080)]


def step_camera(old: dict[str, str]) -> tuple[int, int, int]:
    title("Caméra")
    print("Recherche des caméras (quelques secondes)...")
    cams = probe_cameras()
    if cams:
        labels = [f"/dev/video{i} — {name} (image {w}x{h})" for i, name, (w, h) in cams]
        pick = choose("Quelle caméra utiliser ?", labels)
        index = cams[pick][0]
    else:
        print(
            "  Aucune caméra USB détectée. Branche une webcam USB (la caméra nappe CSI du Pi\n"
            "  n'est pas prise en charge pour l'instant) et vérifie que ton utilisateur est dans\n"
            "  le groupe « video ». Tu peux aussi saisir l'index à la main (0 = /dev/video0)."
        )
        index = ask_int("Index de la caméra", int(old.get("CAMERA_INDEX", "0")))

    res = choose("Résolution :", [r[0] for r in RESOLUTIONS])
    width, height = RESOLUTIONS[res][1], RESOLUTIONS[res][2]

    if cams and ask_yes_no("Prendre une photo de test ?", True):
        path = test_photo(index, width, height)
        if path:
            print(f"  ✓ Photo enregistrée : {path} (ouvre-la pour vérifier le cadrage)")
        else:
            print("  ✗ Impossible de lire une image avec ces réglages.")
    return index, width, height


# ── Audio ─────────────────────────────────────────────────────────────────

def list_sound_cards() -> list[tuple[int, str]]:
    cards = []
    for m in re.finditer(r"^card (\d+): (\S+) \[(.+?)\]", run(["aplay", "-l"]), re.M):
        cards.append((int(m.group(1)), f"{m.group(3)} ({m.group(2)})"))
    return cards


def pick_mixer_control(card: int) -> str:
    controls = re.findall(r"Simple mixer control '([^']+)'", run(["amixer", "-c", str(card), "scontrols"]))
    for preferred in ("Master", "PCM", "Speaker", "Headphone", "Headset"):
        if preferred in controls:
            return preferred
    return controls[0] if controls else "Master"


def play_test_sound(device: str) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("  ffmpeg introuvable, test sonore impossible.")
        return
    subprocess.run(
        [ffmpeg, "-nostdin", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=880:duration=1.5",
         "-f", "alsa", device],
        check=False,
    )


def step_audio(old: dict[str, str]) -> tuple[str, str, str]:
    title("Haut-parleur (alarme dissuasive et messages vocaux)")
    cards = list_sound_cards()
    if not cards:
        print("  Aucune carte son détectée : l'alarme sonore ne fonctionnera pas (la détection oui).")
        return "default", "", "Master"
    while True:
        labels = [f"{name} [carte {n}]" for n, name in cards]
        pick = choose("Sortie audio à utiliser ?", labels)
        card = cards[pick][0]
        device = f"plughw:{card},0"
        control = pick_mixer_control(card)
        if not ask_yes_no("Jouer un bip de test (baisse le volume avant !) ?", True):
            return device, str(card), control
        play_test_sound(device)
        if ask_yes_no("Tu as entendu le bip ?", True):
            return device, str(card), control
        print("  Essayons une autre sortie.")


# ── Performance ───────────────────────────────────────────────────────────

PROFILES = [
    ("Équilibré (recommandé) — analyse 320 px, 5 fois/s", 320, 5),
    ("Économe — analyse 240 px, 3 fois/s (Pi chargé ou ancien)", 240, 3),
    ("Précis — analyse 480 px, 8 fois/s (petits mouvements, plus de CPU)", 480, 8),
]


def step_perf(old: dict[str, str]) -> dict[str, str]:
    title("Performance (charge du processeur)")
    print(
        "La détection analyse une image réduite, un nombre limité de fois par seconde. Les photos\n"
        "envoyées restent en pleine résolution. Plus c'est élevé, plus c'est précis et plus le CPU travaille."
    )
    current = (old.get("DETECT_WIDTH"), old.get("ANALYSIS_FPS"))
    labels = [p[0] for p in PROFILES] + ["Personnalisé"]
    default = next((i for i, p in enumerate(PROFILES) if (str(p[1]), str(p[2])) == current), 0)
    if current != (None, None) and default == 0 and current != ("320", "5"):
        default = len(PROFILES)  # valeurs existantes hors profils → personnalisé
    pick = choose("Profil :", labels, default)
    if pick < len(PROFILES):
        width, fps = PROFILES[pick][1], PROFILES[pick][2]
    else:
        width = ask_int("Largeur d'analyse en pixels (0 = taille native, lourd)", int(old.get("DETECT_WIDTH") or 320))
        fps = ask_int("Analyses par seconde (1-30)", int(float(old.get("ANALYSIS_FPS") or 5)), 1)
    return {"DETECT_WIDTH": str(width), "ANALYSIS_FPS": str(fps)}


# ── Divers ────────────────────────────────────────────────────────────────

def step_misc(old: dict[str, str]) -> dict[str, str]:
    title("Réglages généraux")
    lang_default = 1 if old.get("LANGUAGE") == "fr" else 0
    language = ["en", "fr"][choose("Langue des messages Telegram :", ["English", "Français"], lang_default)]
    site = ask("Nom du site, ajouté devant chaque message (ex. « Maison » ; vide = aucun)", old.get("SITE_NAME", ""))
    retention = ask_int("Garder les photos combien de jours ? (0 = jamais effacer)", int(old.get("RETENTION_DAYS", "14")))

    http: dict[str, str] = {}
    print(
        "\nServeur HTTP optionnel : permet de mettre en pause / reprendre la caméra depuis un\n"
        "raccourci (iOS Raccourcis, domotique…). Protégé par un token, à n'exposer que via un\n"
        "VPN (Tailscale) — jamais directement sur internet."
    )
    if ask_yes_no("Activer le serveur HTTP ?", bool(old.get("HTTP_TOKEN"))):
        http["HTTP_PORT"] = str(ask_int("Port", int(old.get("HTTP_PORT", "8765")), 1))
        http["HTTP_TOKEN"] = old.get("HTTP_TOKEN") or secrets.token_urlsafe(24)
    return {"LANGUAGE": language, "SITE_NAME": site, "RETENTION_DAYS": str(retention), **http}


# ── Écriture ──────────────────────────────────────────────────────────────

MANAGED = [
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_IDS", "TELEGRAM_CHAT_ID", "LANGUAGE", "SITE_NAME",
    "CAMERA_INDEX", "CAMERA_WIDTH", "CAMERA_HEIGHT", "AUDIO_DEVICE", "AUDIO_CARD", "AUDIO_CONTROL",
    "RETENTION_DAYS", "HTTP_PORT", "HTTP_TOKEN", "DETECT_WIDTH", "ANALYSIS_FPS",
]


def write_env(values: dict[str, str], old: dict[str, str]) -> None:
    if ENV_PATH.exists():
        backup = ENV_PATH.with_name(".env.bak")
        shutil.copy2(ENV_PATH, backup)
        os.chmod(backup, 0o600)
    lines = ["# Généré par linux/setup_wizard.py — relancer l'assistant pour modifier.", ""]
    lines += [f"{k}={v}" for k, v in values.items()]
    extras = {k: v for k, v in old.items() if k not in MANAGED}
    if extras:
        lines += ["", "# Réglages conservés de l'ancien .env"]
        lines += [f"{k}={v}" for k, v in extras.items()]
    # Création en 0600 d'emblée : le fichier contient le token du bot.
    fd = os.open(ENV_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(ENV_PATH, 0o600)


def main() -> None:
    print("=== Configuration de gotchacam (Linux / Raspberry Pi) ===")
    old = load_env(ENV_PATH)
    if old:
        print(f"Un .env existe déjà : ses valeurs servent de défaut (sauvegarde dans .env.bak).")

    token, ids, _bot = step_telegram(old)
    index, width, height = step_camera(old)
    device, card, control = step_audio(old)
    perf = step_perf(old)
    misc = step_misc(old)

    values = {
        "TELEGRAM_BOT_TOKEN": token,
        "TELEGRAM_CHAT_IDS": ",".join(map(str, ids)),
        "CAMERA_INDEX": str(index),
        "CAMERA_WIDTH": str(width),
        "CAMERA_HEIGHT": str(height),
        "AUDIO_DEVICE": device,
        "AUDIO_CARD": card,
        "AUDIO_CONTROL": control,
        **perf,
        **misc,
    }
    title("Récapitulatif")
    for k, v in values.items():
        shown = v[:8] + "…" if k in ("TELEGRAM_BOT_TOKEN", "HTTP_TOKEN") else v
        print(f"  {k:<20} {shown}")
    if not ask_yes_no("Écrire ce fichier .env ?", True):
        sys.exit("Annulé, rien n'a été écrit.")
    write_env(values, old)
    print(f"✓ {ENV_PATH} écrit (permissions 600).")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nInterrompu, rien n'a été écrit.")
