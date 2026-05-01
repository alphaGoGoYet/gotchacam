"""Motion detection on Mac webcam → snapshot pushed to Telegram.

Telegram commands (réservées au CHAT_ID configuré) :
  /pause       — mettre la détection en pause
  /resume      — reprendre la détection
  /status      — afficher l'état actuel
  /snapshot    — envoyer une photo immédiate (même en pause)
  /alarm       — déclencher l'alarme dissuasive en boucle (volume max)
  /stopalarm   — arrêter l'alarme en cours et restaurer le volume
  /recordalarm — enregistrer un nouveau message vocal pour remplacer l'alarme
  /help        — afficher cette aide

Tout message vocal envoyé au bot est diffusé une fois sur les haut-parleurs
(intercom à distance). Pendant les 5 min suivant /recordalarm, il devient
en plus la nouvelle alarme.

Pour arrêter le programme : Ctrl+C en local sur la machine qui le fait tourner.
Volontairement pas de /stop distant : un appui accidentel depuis le boulot
laisserait la caméra hors service jusqu'au retour à la maison.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from telegram import InputMediaPhoto, Update
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

SHARED_DIR = Path(__file__).parent / "shared"
DEFAULTS = json.loads((SHARED_DIR / "defaults.json").read_text())
STRINGS = json.loads((SHARED_DIR / "strings.fr.json").read_text())

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", DEFAULTS["camera"]["index"]))
MOTION_THRESHOLD = int(os.getenv("MOTION_THRESHOLD", DEFAULTS["motion"]["threshold"]))
MIN_AREA = int(os.getenv("MIN_AREA", DEFAULTS["motion"]["minArea"]))
COOLDOWN_SECONDS = float(os.getenv("COOLDOWN_SECONDS", DEFAULTS["motion"]["cooldownSeconds"]))
WARMUP_SECONDS = float(os.getenv("WARMUP_SECONDS", DEFAULTS["camera"]["warmupSeconds"]))
BURST_COUNT = int(os.getenv("BURST_COUNT", DEFAULTS["burst"]["count"]))
BURST_INTERVAL = float(os.getenv("BURST_INTERVAL", DEFAULTS["burst"]["intervalSeconds"]))
SITE_NAME = os.getenv("SITE_NAME", "").strip()
SITE_PREFIX = STRINGS["site_prefix"].format(site=SITE_NAME) if SITE_NAME else ""
ALARM_TEXT = os.getenv("ALARM_TEXT", STRINGS["alarm"]["default_text"])
ALARM_SOUND = os.getenv("ALARM_SOUND", "").strip()
ALARM_VOICE = os.getenv("ALARM_VOICE", DEFAULTS["alarm"]["voice"]).strip()
ALARM_PITCH = float(os.getenv("ALARM_PITCH", DEFAULTS["alarm"]["pitch"]))
ALARM_RECORD_MAX_SECONDS = int(os.getenv("ALARM_RECORD_MAX_SECONDS", DEFAULTS["alarm"]["recordMaxSeconds"]))
FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
VOICE_PLAYBACK_MAX_SECONDS = int(os.getenv("VOICE_PLAYBACK_MAX_SECONDS", DEFAULTS["alarm"]["voicePlaybackMaxSeconds"]))
RETENTION_DAYS = int(os.getenv("RETENTION_DAYS", DEFAULTS["captures"]["retentionDays"]))
DEFAULT_ALARM_PATH = Path(__file__).parent / "alarm.m4a"

CAPTURES_DIR = Path(__file__).parent / "captures"
CAPTURES_DIR.mkdir(exist_ok=True)


def _cleanup_old_captures() -> None:
    """Supprime les fichiers de captures/ plus vieux que RETENTION_DAYS jours."""
    if RETENTION_DAYS <= 0:
        return
    cutoff = time.time() - RETENTION_DAYS * 86400
    deleted = 0
    freed = 0
    for f in CAPTURES_DIR.iterdir():
        if not f.is_file():
            continue
        try:
            if f.stat().st_mtime < cutoff:
                size = f.stat().st_size
                f.unlink()
                deleted += 1
                freed += size
        except OSError as e:
            logging.warning("could not delete %s: %s", f.name, e)
    if deleted:
        logging.info("captures cleanup: deleted %d files (%.1f MB freed)", deleted, freed / 1024 / 1024)


_cleanup_old_captures()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("cam")

paused = False
stop_event: asyncio.Event | None = None
latest_frame: np.ndarray | None = None
alarm_active = False
alarm_proc: asyncio.subprocess.Process | None = None
alarm_prev_volume: int | None = None
recording_alarm_deadline: float = 0.0

HELP_TEXT = (
    STRINGS["help"]["header"]
    + "\n"
    + "\n".join(STRINGS["help"]["commands"])
    + "\n\n"
    + STRINGS["help"]["footer"]
)


def detect_motion(prev_gray, gray) -> tuple[bool, int]:
    delta = cv2.absdiff(prev_gray, gray)
    thresh = cv2.threshold(delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, iterations=2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    largest = max((cv2.contourArea(c) for c in contours), default=0)
    return largest >= MIN_AREA, int(largest)


def is_authorized(update: Update) -> bool:
    return update.effective_chat is not None and update.effective_chat.id == CHAT_ID


async def cmd_pause(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    global paused
    paused = True
    log.info("paused via Telegram")
    await update.message.reply_text(STRINGS["pause"]["paused"])


async def cmd_resume(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    global paused
    paused = False
    log.info("resumed via Telegram")
    await update.message.reply_text(STRINGS["pause"]["resumed"])


async def cmd_status(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    state = STRINGS["status"]["paused"] if paused else STRINGS["status"]["active"]
    await update.message.reply_text(SITE_PREFIX + STRINGS["status"]["label"].format(state=state))


async def cmd_snapshot(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    if paused:
        await update.message.reply_text(SITE_PREFIX + STRINGS["snapshot"]["paused"])
        return
    if latest_frame is None:
        await update.message.reply_text(STRINGS["snapshot"]["not_ready"])
        return
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = CAPTURES_DIR / f"snapshot_{ts}.jpg"
    cv2.imwrite(str(path), latest_frame)
    log.info("snapshot requested → %s", path.name)
    caption = SITE_PREFIX + STRINGS["snapshot"]["caption"].format(time=f"{datetime.now():%H:%M:%S}")
    try:
        with path.open("rb") as f:
            await ctx.bot.send_photo(chat_id=CHAT_ID, photo=f, caption=caption)
    except TelegramError as e:
        log.error("snapshot send failed: %s", e)
        await update.message.reply_text(STRINGS["snapshot"]["send_failed"].format(error=e))


async def cmd_recordalarm(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Ouvre une fenêtre de 5 minutes pendant laquelle un message vocal Telegram remplacera l'alarme."""
    if not is_authorized(update):
        return
    global recording_alarm_deadline
    recording_alarm_deadline = time.time() + 300
    if ALARM_PITCH != 1.0:
        pitch_pct = f"{int((ALARM_PITCH - 1) * 100):+d}%"
        pitch_note = STRINGS["record_alarm"]["pitch_note"].format(pitch_pct=pitch_pct)
    else:
        pitch_note = ""
    await update.message.reply_text(
        SITE_PREFIX + STRINGS["record_alarm"]["prompt"].format(
            max=ALARM_RECORD_MAX_SECONDS,
            pitch_note=pitch_note,
        )
    )


async def _save_as_alarm(src: Path, voice_duration: int, update: Update) -> None:
    """Convertit l'OGG reçu en alarm.m4a (avec pitch shift si configuré)."""
    global recording_alarm_deadline
    dest = _current_alarm_path()
    dest.parent.mkdir(parents=True, exist_ok=True)

    if ALARM_PITCH == 1.0:
        ffmpeg_args = [FFMPEG_BIN, "-y", "-i", str(src), str(dest)]
    else:
        ffmpeg_args = [
            FFMPEG_BIN, "-y", "-i", str(src),
            "-af", f"asetrate=44100*{ALARM_PITCH},aresample=44100,atempo={1 / ALARM_PITCH}",
            str(dest),
        ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *ffmpeg_args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
    except FileNotFoundError:
        await update.message.reply_text(
            STRINGS["record_alarm"]["ffmpeg_missing"].format(path=FFMPEG_BIN)
        )
        return

    if proc.returncode != 0:
        log.error("ffmpeg failed (rc=%d): %s", proc.returncode, stderr.decode()[:500])
        await update.message.reply_text(STRINGS["record_alarm"]["conversion_failed"])
        return

    recording_alarm_deadline = 0.0
    if ALARM_PITCH != 1.0:
        pitch_pct = f"{int((ALARM_PITCH - 1) * 100):+d}%"
        pitch_note = STRINGS["record_alarm"]["replaced_pitch_note"].format(pitch_pct=pitch_pct)
    else:
        pitch_note = ""
    await update.message.reply_text(
        SITE_PREFIX + STRINGS["record_alarm"]["replaced"].format(
            pitch_note=pitch_note,
            filename=dest.name,
        ),
        parse_mode="Markdown",
    )


async def _play_voice_once(src: Path, update: Update) -> None:
    """Convertit l'OGG/Opus en WAV via ffmpeg puis joue le WAV via afplay (built-in macOS)."""
    wav = src.with_suffix(".wav")
    try:
        conv = await asyncio.create_subprocess_exec(
            FFMPEG_BIN, "-y", "-i", str(src), str(wav),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await conv.communicate()
    except FileNotFoundError:
        await update.message.reply_text(
            STRINGS["record_alarm"]["ffmpeg_missing"].format(path=FFMPEG_BIN)
        )
        return

    if conv.returncode != 0:
        log.error("voice conversion failed: %s", stderr.decode()[:300])
        await update.message.reply_text(STRINGS["voice"]["audio_conversion_failed"])
        return

    try:
        play = await asyncio.create_subprocess_exec(
            "afplay", str(wav),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await play.wait()
    finally:
        try:
            wav.unlink()
        except OSError:
            pass

    if play.returncode == 0:
        await update.message.reply_text(SITE_PREFIX + STRINGS["voice"]["diffused"])
    else:
        await update.message.reply_text(STRINGS["voice"]["diffusion_failed"].format(code=play.returncode))


async def on_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Tout message vocal OU fichier audio est joué une fois sur les haut-parleurs.
    Pendant la fenêtre /recordalarm, il devient en plus la nouvelle alarme."""
    if not is_authorized(update):
        return
    media = update.message.voice or update.message.audio
    if media is None:
        return

    duration = getattr(media, "duration", 0) or 0
    is_recording_alarm = time.time() < recording_alarm_deadline
    max_seconds = ALARM_RECORD_MAX_SECONDS if is_recording_alarm else VOICE_PLAYBACK_MAX_SECONDS
    if duration > max_seconds:
        await update.message.reply_text(
            STRINGS["voice"]["too_long"].format(duration=duration, max=max_seconds)
        )
        return

    file = await ctx.bot.get_file(media.file_id)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ext = "ogg" if update.message.voice else "audio"
    src = CAPTURES_DIR / f"voice_{ts}.{ext}"
    await file.download_to_drive(str(src))
    log.info("voice received: %s (%ds, recording=%s)", src.name, duration, is_recording_alarm)

    if is_recording_alarm:
        await _save_as_alarm(src, duration, update)
    else:
        await _play_voice_once(src, update)


async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Liste les timestamps des N dernières détections de mouvement (défaut 5, max 20)."""
    if not is_authorized(update):
        return
    n = 5
    if ctx.args:
        try:
            n = max(1, min(20, int(ctx.args[0])))
        except ValueError:
            pass
    files = sorted(CAPTURES_DIR.glob("motion_*_1.jpg"), key=lambda f: f.stat().st_mtime, reverse=True)[:n]
    if not files:
        await update.message.reply_text(STRINGS["history"]["empty"])
        return
    lines = [STRINGS["history"]["header"].format(count=len(files))]
    for f in files:
        # filename pattern : motion_YYYYMMDD_HHMMSS_mmm_1.jpg
        parts = f.stem.split("_")
        try:
            date = parts[1]
            ts = parts[2]
            formatted = f"{date[:4]}-{date[4:6]}-{date[6:8]} {ts[:2]}:{ts[2:4]}:{ts[4:6]}"
        except (IndexError, ValueError):
            formatted = f.stem
        lines.append(STRINGS["history"]["item"].format(timestamp=formatted))
    await update.message.reply_text("\n".join(lines))


async def cmd_sensitivity(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Affiche ou ajuste MIN_AREA à chaud. Sans argument : affiche la valeur courante."""
    if not is_authorized(update):
        return
    global MIN_AREA
    if not ctx.args:
        await update.message.reply_text(
            STRINGS["sensitivity"]["current"].format(value=MIN_AREA),
            parse_mode="Markdown",
        )
        return
    raw = ctx.args[0]
    try:
        new_value = int(raw)
        if new_value <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(
            STRINGS["sensitivity"]["invalid"].format(input=raw),
            parse_mode="Markdown",
        )
        return
    previous = MIN_AREA
    MIN_AREA = new_value
    log.info("MIN_AREA changed via Telegram: %d → %d", previous, new_value)
    await update.message.reply_text(
        STRINGS["sensitivity"]["updated"].format(value=new_value, previous=previous)
    )


async def cmd_help(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update):
        return
    await update.message.reply_text(HELP_TEXT)


async def _get_output_volume() -> int | None:
    """Retourne le volume actuel (0-100) ou None si la lecture échoue."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", "output volume of (get volume settings)",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        return int(out.decode().strip())
    except (FileNotFoundError, ValueError):
        return None


async def _set_output_volume(level: int) -> None:
    level = max(0, min(100, int(level)))
    try:
        proc = await asyncio.create_subprocess_exec(
            "osascript", "-e", f"set volume output volume {level}",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    except FileNotFoundError:
        pass


def _current_alarm_path() -> Path:
    """Retourne le chemin du fichier d'alarme effectif : ALARM_SOUND si défini, sinon le défaut."""
    return Path(ALARM_SOUND) if ALARM_SOUND else DEFAULT_ALARM_PATH


async def _alarm_loop(bot) -> None:
    """Joue le fichier d'alarme en boucle (ou TTS si pas de fichier) tant que alarm_active est True."""
    global alarm_proc
    alarm_path = _current_alarm_path()
    use_file = alarm_path.exists()
    cmd = ["afplay", str(alarm_path)] if use_file else ["say", "-v", ALARM_VOICE, ALARM_TEXT]

    while alarm_active:
        try:
            alarm_proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await alarm_proc.wait()
        except FileNotFoundError as e:
            log.error("alarm command missing: %s", e)
            try:
                await bot.send_message(
                    chat_id=CHAT_ID,
                    text=STRINGS["alarm"]["executable_missing"].format(error=e),
                )
            except TelegramError:
                pass
            break
        finally:
            alarm_proc = None


async def cmd_alarm(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Démarre l'alarme dissuasive en boucle. /stopalarm pour arrêter."""
    if not is_authorized(update):
        return
    global alarm_active, alarm_prev_volume
    if alarm_active:
        await update.message.reply_text(SITE_PREFIX + STRINGS["alarm"]["already_running"])
        return

    log.warning("ALARM started via Telegram")
    alarm_prev_volume = await _get_output_volume()
    await _set_output_volume(100)
    alarm_active = True

    source = (
        STRINGS["alarm"]["source_recording"]
        if _current_alarm_path().exists()
        else STRINGS["alarm"]["source_tts"]
    )
    await update.message.reply_text(
        SITE_PREFIX + STRINGS["alarm"]["started"].format(source=source)
    )

    asyncio.create_task(_alarm_loop(ctx.bot))


async def cmd_stopalarm(update: Update, _ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Stoppe l'alarme en cours et restaure le volume."""
    if not is_authorized(update):
        return
    global alarm_active, alarm_proc, alarm_prev_volume
    if not alarm_active:
        await update.message.reply_text(SITE_PREFIX + STRINGS["alarm"]["no_alarm_running"])
        return

    log.warning("ALARM stop requested via Telegram")
    alarm_active = False

    proc = alarm_proc
    if proc is not None:
        try:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=2)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        except ProcessLookupError:
            pass

    if alarm_prev_volume is not None:
        await _set_output_volume(alarm_prev_volume)
        msg = SITE_PREFIX + STRINGS["alarm"]["stopped_with_volume"].format(volume=alarm_prev_volume)
    else:
        msg = SITE_PREFIX + STRINGS["alarm"]["stopped_no_volume"]
    alarm_prev_volume = None

    await update.message.reply_text(msg)


async def capture_burst(bot, area: int) -> None:
    """Capture BURST_COUNT frames spaced by BURST_INTERVAL and send as a Telegram album."""
    paths: list[Path] = []
    for i in range(BURST_COUNT):
        if i > 0:
            await asyncio.sleep(BURST_INTERVAL)
        if latest_frame is None:
            continue
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        path = CAPTURES_DIR / f"motion_{ts}_{i + 1}.jpg"
        cv2.imwrite(str(path), latest_frame)
        paths.append(path)
        log.info("burst frame %d/%d → %s", i + 1, BURST_COUNT, path.name)

    if not paths:
        return

    caption = SITE_PREFIX + STRINGS["motion"]["caption"].format(
        time=f"{datetime.now():%H:%M:%S}",
        area=area,
        count=len(paths),
        span=f"{BURST_INTERVAL * (BURST_COUNT - 1):.1f}",
    )
    try:
        files = [p.open("rb") for p in paths]
        try:
            media = [
                InputMediaPhoto(media=f, caption=caption if i == 0 else None)
                for i, f in enumerate(files)
            ]
            await bot.send_media_group(chat_id=CHAT_ID, media=media)
        finally:
            for f in files:
                f.close()
        log.info("burst sent: %d photos", len(paths))
    except TelegramError as e:
        log.error("telegram send failed: %s", e)


async def camera_loop(bot) -> None:
    """Boucle principale. Le cycle de vie de la caméra est lié au flag `paused` :
    pendant la pause la caméra est libérée (LED éteinte, pas de capture) et
    réouverte au resume avec warmup et reset de la frame de référence."""
    global latest_frame
    cap: cv2.VideoCapture | None = None
    prev_gray = None
    last_alert = 0.0

    try:
        while not stop_event.is_set():
            if paused:
                if cap is not None:
                    cap.release()
                    cap = None
                    prev_gray = None
                    latest_frame = None
                    log.info("camera released (paused)")
                await asyncio.sleep(0.5)
                continue

            if cap is None:
                cap = cv2.VideoCapture(CAMERA_INDEX)
                if not cap.isOpened():
                    log.error("could not open camera index %d, retry in 2s", CAMERA_INDEX)
                    cap = None
                    await asyncio.sleep(2)
                    continue
                log.info("camera opened, warming up for %.1fs...", WARMUP_SECONDS)
                await asyncio.sleep(WARMUP_SECONDS)

            ok, frame = cap.read()
            if not ok:
                log.warning("frame read failed, retrying...")
                await asyncio.sleep(0.5)
                continue

            latest_frame = frame
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if prev_gray is None:
                prev_gray = gray
                await asyncio.sleep(0.05)
                continue

            motion, area = detect_motion(prev_gray, gray)
            now = time.time()
            if motion and now - last_alert >= COOLDOWN_SECONDS:
                last_alert = now
                log.info("motion! area=%d → starting burst of %d", area, BURST_COUNT)
                asyncio.create_task(capture_burst(bot, area))

            prev_gray = gray
            await asyncio.sleep(0.05)
    finally:
        if cap is not None:
            cap.release()
        log.info("camera released")


async def main() -> None:
    global stop_event
    stop_event = asyncio.Event()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("snapshot", cmd_snapshot))
    app.add_handler(CommandHandler("alarm", cmd_alarm))
    app.add_handler(CommandHandler("stopalarm", cmd_stopalarm))
    app.add_handler(CommandHandler("recordalarm", cmd_recordalarm))
    app.add_handler(CommandHandler("sensitivity", cmd_sensitivity))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        try:
            await app.bot.send_message(
                chat_id=CHAT_ID,
                text=f"{SITE_PREFIX}{STRINGS['service']['started']}\n\n{HELP_TEXT}",
            )
            await camera_loop(app.bot)
        finally:
            try:
                await app.bot.send_message(
                    chat_id=CHAT_ID,
                    text=SITE_PREFIX + STRINGS["service"]["stopped"],
                )
            except TelegramError:
                pass
            await app.updater.stop()
            await app.stop()
        log.info("stopped")


if __name__ == "__main__":
    asyncio.run(main())
