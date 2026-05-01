"""One-shot helper: print the chat_id of whoever sent the bot a message.

Steps:
  1. Open Telegram, find your bot by its handle (the @name BotFather gave you).
  2. Send it any message (e.g. "hi").
  3. Run: python get_chat_id.py
"""

import asyncio
import os

from dotenv import load_dotenv
from telegram import Bot

load_dotenv()


async def main() -> None:
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    updates = await bot.get_updates()
    if not updates:
        print("No messages yet. Send a message to your bot from Telegram, then re-run.")
        return
    seen = {}
    for u in updates:
        if u.message:
            seen[u.message.chat.id] = u.message.chat.full_name or u.message.chat.title or "?"
    for cid, name in seen.items():
        print(f"chat_id={cid}  ({name})")


if __name__ == "__main__":
    asyncio.run(main())
