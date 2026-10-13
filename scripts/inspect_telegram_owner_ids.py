#!/usr/bin/env python3
"""Show only private Telegram chat/user IDs, never message text."""
import json
import os
import sys
import urllib.request

token = os.environ.get("HAMI_TELEGRAM_BOT_TOKEN", "").strip()
if len(token) < 30:
    print("Set HAMI_TELEGRAM_BOT_TOKEN in your local shell.")
    raise SystemExit(2)
try:
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getUpdates", timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
except Exception:
    print("Could not read updates; check bot setup or an existing webhook.")
    raise SystemExit(1)
if not isinstance(data, dict) or data.get("ok") is not True:
    print("Telegram did not return updates.")
    raise SystemExit(1)
seen = set()
for update in data.get("result", []):
    msg = update.get("message") if isinstance(update, dict) else None
    if not isinstance(msg, dict):
        continue
    chat = msg.get("chat") if isinstance(msg.get("chat"), dict) else {}
    sender = msg.get("from") if isinstance(msg.get("from"), dict) else {}
    pair = (chat.get("id"), sender.get("id"))
    if chat.get("type") == "private" and sender.get("is_bot") is not True and all(type(x) is int and x > 0 for x in pair) and pair not in seen:
        print(f"private_chat_id={pair[0]} owner_user_id={pair[1]}")
        seen.add(pair)
if not seen:
    print("Open the bot's private chat, send /start, then rerun; getUpdates may be unavailable with a webhook.")
