# Hami owner control — Telegram setup checklist

Telegram is the single-owner control channel, separate from seller/buyer channels. Adding this checklist does not activate customer sending, intake, checkout, or the owner digest.

## 1. Create the private bot

1. Open the verified official **@BotFather**, create a bot, and copy its token once.
2. Open the bot's private chat from the owner's Telegram account and send `/start`.
3. Enable Telegram two-step verification and a device passcode. Never share account login codes or the bot token.
4. Never commit the bot token, webhook secret, owner IDs, confirmation codes, phone numbers, raw Telegram updates, or customer messages. Do not paste them into GitHub issues, logs, or third-party chats.

## 2. Find the owner IDs

Set `HAMI_TELEGRAM_BOT_TOKEN` only in a private local shell, then run:

```sh
python scripts/inspect_telegram_owner_ids.py
```

The helper prints only the private `chat_id` and `owner_user_id`; it never prints message text. Keep both values private. Telegram's `getUpdates` may not work while a webhook is registered.

## 3. Configure the deployment privately

Set the following in the deployment's private environment settings, never in repository files:

- `HAMI_TELEGRAM_BOT_TOKEN` — BotFather token.
- `HAMI_TELEGRAM_WEBHOOK_SECRET` — random 32+ character string using letters, digits, underscore or hyphen.
- `HAMI_TELEGRAM_OWNER_CHAT_ID` — the owner's private chat ID.
- `HAMI_TELEGRAM_OWNER_USER_ID` — the owner's Telegram user ID.
- `HAMI_TELEGRAM_CONTROL_ENABLED` — keep `false` until the owner authorizes activation and durable PostgreSQL/runtime readiness is confirmed.
- `HAMI_TELEGRAM_OWNER_DIGEST_ENABLED` — keep `false` until separately approved; digest delivery requires durable PostgreSQL.
- `HAMI_TELEGRAM_ASK_CODE_TTL_SECONDS` — default 600 seconds.

Keep all existing Twilio credentials and SMS flags unchanged. Never commit an `.env` file.

## 4. Register the webhook only after deployment verification

After the implementation is deployed, durable PostgreSQL is verified, environment values are correct, and the owner authorizes `HAMI_TELEGRAM_CONTROL_ENABLED=true`, export the token and webhook secret in a private local shell and run:

```sh
python scripts/register_telegram_webhook.py
```

The helper registers `https://haminp.vercel.app/api/owner-control/telegram/webhook` through Telegram's `setWebhook`, allows message updates only, and preserves pending updates. Telegram sends the configured secret in `X-Telegram-Bot-Api-Secret-Token` over HTTPS. This is a shared-secret header check, not a per-body HMAC signature. Hami compares it in constant time and then checks the exact configured private chat ID and user ID.

## 5. Verify without opening customer sending

1. Send `/status` from the owner's private chat; verify the reply and owner-console contact timestamp.
2. Send `HALT`; verify persisted `safe_mode_enabled=true` and blocked generic customer email/SMS dispatch.
3. Verify other accounts and group chats are ignored. Approvals must be new, unforwarded messages.
4. Leave the digest disabled until it is separately approved. Telegram API acceptance is not proof that a handset displayed the message.
5. Resume only from the authenticated owner console: request a resume ASK and submit the one-time code delivered to Telegram. The code must be hashed at rest, expire, and be single-use. Resume clears safe mode only; it does not enable sending flags.
6. Record observed test results in `LOG.md` without secrets, IDs, codes, phone numbers, or message content.

## Commands

- `HALT` or `/halt` — persistently enable safe mode.
- `/status` — inspect safety posture.
- `/answer ASK-REF CODE OPTION` — routine ASKs only, as a new unforwarded message.
- High-impact decisions require the authenticated owner console plus a one-time code. Telegram never executes Actions automatically.

No credentials, webhook settings, production flags, or external messages are changed by this checklist itself.
