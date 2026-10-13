"""Single-owner Telegram sender. Never log token, URL, text, IDs or provider response."""
import json
import re
import urllib.error
import urllib.request
from typing import Any
from app.config import settings

class TelegramTransportError(RuntimeError):
    """Safe-to-log transport failure."""

def send_owner_message(text: str, *, message_type: str = "alert") -> dict[str, Any]:
    token = str(settings.HAMI_TELEGRAM_BOT_TOKEN or "").strip()
    chat = str(settings.HAMI_TELEGRAM_OWNER_CHAT_ID or "").strip()
    if not settings.HAMI_TELEGRAM_CONTROL_ENABLED or len(token) < 30:
        raise TelegramTransportError("telegram_control_disabled_or_unconfigured")
    if not re.fullmatch(r"[1-9][0-9]{0,18}", chat):
        raise TelegramTransportError("telegram_owner_chat_missing_or_invalid")
    if not isinstance(text, str) or not text.strip() or len(text) > 4096 or message_type not in {"ask", "status", "help", "alert", "daily_digest"}:
        raise TelegramTransportError("telegram_message_invalid")
    payload = json.dumps({"chat_id": int(chat), "text": text, "disable_web_page_preview": True}, separators=(",", ":")).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage", data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise TelegramTransportError("telegram_api_unavailable_or_invalid_response") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise TelegramTransportError("telegram_api_rejected_request")
    item = result.get("result")
    message_id = item.get("message_id") if isinstance(item, dict) else None
    if type(message_id) is not int:
        raise TelegramTransportError("telegram_response_missing_message_id")
    return {"message_id": message_id, "accepted": True}
