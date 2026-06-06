# gotchacam

> *Self-hosted home surveillance — your footage stays at home, and an intruder gets blasted by your own voice on loop.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Made for macOS](https://img.shields.io/badge/macOS-Apple%20Silicon-lightgrey)](#requirements)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue)](#requirements)

🇫🇷 [Version française disponible](README.fr.md)

![gotchacam in action](docs/demo.gif)

---

## Why gotchacam is different

🔒 **100% local** — your images never transit through any third-party cloud. Everything lives on your Mac at home + Telegram (which you already use).

🗣️ **Deterrent alarm in YOUR voice** — record a voice message directly through Telegram, get an automatic "movie villain" pitch shift applied, and trigger it on a loop at max volume with a simple `/alarm` when an intruder is in your apartment.

💬 **Fully Telegram-controlled** — no separate app to install. Pause, resume, snapshot on demand, alarm — everything goes through your usual messaging.

💸 **Free and open source** — no subscriptions, no ads. Reuse that old Mac sleeping in your closet.

---

## How it works

```
┌─────────────────┐  motion detected  ┌──────────────┐
│   Mac webcam    │ ────────────────► │   Telegram   │
│  (your home)    │   3-photo burst   │  (your phone)│
└────────┬────────┘                   └──────┬───────┘
         │                                   │
         │           commands: /pause, /alarm, etc.
         │ ◄─────────────────────────────────┤
         │                                   │
         │           voice messages          │
         │ ◄─────────────────────────────────┤
         ▼                                   │
   plays your message                        │
   on loop at 100%                           │
   to scare them off                         │
```

## Available commands

| Command | Effect |
|---------|--------|
| `/pause` | Pauses detection **and releases the camera** (LED off, lower power) |
| `/resume` | Resumes detection |
| `/status` | Shows current state (active / paused) |
| `/snapshot` | Sends an immediate photo |
| `/alarm` | Triggers the deterrent alarm on loop at max volume |
| `/stopalarm` | Stops the alarm and restores the original volume |
| `/recordalarm` | Records a new Telegram voice message that becomes the new alarm (with auto pitch shift) |
| `/sensitivity [value]` | Shows or changes the detection threshold on the fly (no restart) |
| `/history [N]` | Lists the last N detections (5 by default) |
| `/clean` | Deletes all captures from disk **and** removes the corresponding Telegram messages |
| `/help` | Shows the command list |

Any **voice message sent to the bot** is played once on the speakers (remote intercom mode). During the 5 minutes following `/recordalarm`, it also becomes the new alarm.

There is no remote stop command on purpose — an accidental tap would leave the camera dead until you got home. To stop, hit `Ctrl+C` locally or `launchctl unload` (see [AUTOSTART.md](AUTOSTART.md)).

## iOS Shortcuts integration

gotchacam includes a built-in HTTP server for use with Apple Shortcuts (auto-pause when you leave home, auto-resume when you arrive). Configure it in `.env`:

```env
HTTP_PORT=8765
HTTP_TOKEN=<a_strong_random_secret>   # openssl rand -hex 20
```

Then use [Tailscale](https://tailscale.com) (free) to reach the Mac securely from anywhere without exposing anything to the internet. See [SHORTCUTS_IOS.md](SHORTCUTS_IOS.md) for the full setup guide.

## Requirements

- macOS (tested on Sequoia, Apple Silicon recommended for power efficiency)
- Python 3.8+
- A webcam (built-in or USB)
- A Telegram account (free)
- `ffmpeg` (for the `/recordalarm` command) — `brew install ffmpeg` or `conda install -c conda-forge ffmpeg`

## Quick install

### 1. Clone and install

```bash
git clone https://github.com/alphaGoGoYet/gotchacam.git
cd gotchacam
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Create the Telegram bot

1. On Telegram, talk to **@BotFather** → `/newbot`
2. Get the **token** (format `123456789:ABC...`)
3. Send any message to your newly created bot

### 3. Configure

```bash
cp .env.example .env
# edit .env: paste your token on the TELEGRAM_BOT_TOKEN= line
```

Get your chat_id:

```bash
python get_chat_id.py
```

Paste the value on the `TELEGRAM_CHAT_ID=` line of `.env`.

### 4. Run

```bash
python cam.py
```

macOS will request camera permission on first launch → accept. You'll receive `🎥 cam started` on Telegram. Move in front of the camera → you'll get 3 photos as an album.

## Auto-start on login

To keep it running without manual intervention:

```bash
bash install_autostart.sh
```

See [AUTOSTART.md](AUTOSTART.md) for details (logs, stopping, etc.).

## Configuration

All variables are documented in [.env.example](.env.example). The most useful ones:

| Variable | Default | Role |
|----------|---------|------|
| `LANGUAGE` | `en` | Telegram message language. Use `fr` for French. |
| `MIN_AREA` | `5000` | Detection threshold (higher = ignores small motions) |
| `BURST_COUNT` | `3` | Number of photos per detection |
| `COOLDOWN_SECONDS` | `3` | Minimum delay between two alerts |
| `ALARM_PITCH` | `1.0` | Pitch of voice recordings (0.75 = -25% for "deep voice" effect) |
| `SITE_NAME` | *(empty)* | Prefix for messages, useful if you have multiple cameras |
| `RETENTION_DAYS` | `30` | Capture retention period |
| `HTTP_PORT` | `8765` | Port for the iOS Shortcuts HTTP server (disabled if `HTTP_TOKEN` is empty) |
| `HTTP_TOKEN` | *(empty)* | Secret token protecting the HTTP server — generate with `openssl rand -hex 20` |

See [shared/BEHAVIOR_SPEC.md](shared/BEHAVIOR_SPEC.md) for the complete behavioral specification.

## Roadmap

- [ ] Native Android port (turn an old phone into a standalone camera)
- [ ] Windows / Linux port (cross-platform via audio backend abstraction)
- [ ] Graphical install wizard (for non-technical users)
- [ ] Person vs shadow/animal detection (ML Kit / TFLite)
- [ ] Multi-camera support

## Architecture

The project is designed to share as much as possible between the macOS Python implementation and the future Android port:

- [shared/defaults.json](shared/defaults.json) — common constants
- [shared/strings.en.json](shared/strings.en.json) / [shared/strings.fr.json](shared/strings.fr.json) — Telegram messages per language
- [shared/BEHAVIOR_SPEC.md](shared/BEHAVIOR_SPEC.md) — formal behavioral specification

See [MULTIPLATFORM.md](MULTIPLATFORM.md) for the pattern and discipline.

## Documentation

- [README.md](README.md) — this file
- [README.fr.md](README.fr.md) — French version
- [AUTOSTART.md](AUTOSTART.md) — automatic startup on macOS
- [MULTIPLATFORM.md](MULTIPLATFORM.md) — multi-platform architecture
- [shared/BEHAVIOR_SPEC.md](shared/BEHAVIOR_SPEC.md) — formal behavioral spec

## Acknowledgments and context

Built for my personal use (monitoring my apartment from work), published in case it helps anyone else. Not pretending to compete with Frigate, Alfred or Wyze — `gotchacam` targets a specific use case: a Mac-owning technically inclined person who wants something simple, privacy-respecting, with a personalized "scare them" effect.

## License

[MIT](LICENSE) — use as you wish, modify as you wish. If you build something cool with it, ping me via an issue.

---

⚠️ **Legal warning**: you may only film your own property. Filming a street, a neighbor, or any public space without explicit consent is illegal in most jurisdictions (in France: Article 226-1 of the Penal Code). Aim your camera responsibly.
