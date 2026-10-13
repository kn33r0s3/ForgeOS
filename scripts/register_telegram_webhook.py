#!/usr/bin/env python3
"""Register Telegram webhook only when the owner runs this local script."""
import json
import os
import re
import sys
import urllib.request

token = os.environ.get("HAMI_TELEGRAM_BOT_TOKEN", "").strip()
secret = os.environ.get("HAMI_TELEGRAM_WEBHOOK_SECRET", "").strip()
enabled = os.environ.get("HAMI_TELEGRAM_CONTROL_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
webhook = os.environ.get("HAMI_TELEGRAM_WEBHOOK_URL", "https://haminp.vercel.app/api/owner-control/telegram/webhook").strip()
if not enabled:
    print("Refusing registration while HAMI_TELEGRAM_CONTROL_ENABLED is false.")
    raise SystemExit(2)
if len(token) < 30 or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", secret):
    print("Set token and a 32+ character URL-safe webhook secret locally.")
    raise SystemExit(2)
if not webhook.startswith("https://"):
    print("Webhook URL must use HTTPS.")
    raise SystemExit(2)
payload = json.dumps({"url": webhook, "secret_token": secret, "allowed_updates": ["message"], "drop_pending_updates": False}).encode()
request = urllib.request.Request(f"https://api.telegram.org/bot{token}/setWebhook", data=payload,
    headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
except Exception:
    print("Webhook registration failed; token/provider response not printed.")
    raise SystemExit(1)
if not isinstance(data, dict) or data.get("ok") is not True:
    print("Telegram rejected registration; inspect bot status privately.")
    raise SystemExit(1)
print("Telegram accepted webhook registration; handset delivery is not established.")
