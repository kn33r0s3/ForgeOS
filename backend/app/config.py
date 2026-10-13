"""
Hami configuration.

Centralizes all environment-driven settings so every module reads
config from one place. This keeps the system modular: swapping the
AI provider, the database, or future services (crawler, Reddit API,
Ollama) only means touching this file plus the relevant service.
"""

import json
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ESEWA_V2_STATUS_URL = "https://epay.esewa.com.np/api/epay/transaction/status/"


def parse_allowed_origins(value: str) -> list[str]:
    """Accept comma-separated or JSON-array CORS origins from deployment env.

    Pydantic Settings JSON-decodes environment values typed as lists before
    validators run. Keeping the environment setting as a string and parsing it
    here supports the existing comma-separated deployment contract safely.
    """
    raw = value.strip()
    if not raw:
        raise ValueError("ALLOWED_ORIGINS must contain at least one origin.")

    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("ALLOWED_ORIGINS must be a comma-separated string or JSON array.") from exc
        if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
            raise ValueError("ALLOWED_ORIGINS JSON value must be an array of strings.")
        items = parsed
    else:
        items = raw.split(",")

    origins = [item.strip() for item in items if item.strip()]
    if not origins:
        raise ValueError("ALLOWED_ORIGINS must contain at least one origin.")
    if "*" in origins:
        raise ValueError("ALLOWED_ORIGINS must use explicit origins; wildcard is not allowed.")
    return origins


def _int_env(name: str, default: int) -> int:
    """Parse an integer env var with a clear error instead of a bare ValueError.

    A non-numeric value used to crash the whole app at import time with an
    opaque ``ValueError: invalid literal for int()``; name the variable so the
    operator knows what to fix.
    """
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise RuntimeError(
            f"Environment variable {name} must be an integer, got {raw!r}."
        ) from None


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "Hami"
    APP_VERSION: str = "2.3.0"

    # --- Database ---
    # SQLite is used for v0.1 to keep RAM/storage low and require zero
    # external services. Swapping to Postgres later only means changing
    # this URL and the engine args in database.py.
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{(Path(__file__).resolve().parents[2] / 'storage' / 'forge.db').resolve()}",
    )

    # --- AI ---
    # Forge runs at $0 by default and always can — paid AI is optional
    # acceleration, never a dependency. Three interchangeable providers:
    #   "mock"   -> deterministic offline templates. Default. Zero cost,
    #                zero setup, zero external calls of any kind.
    #   "ollama" -> a real local open-source model via Ollama
    #                (https://ollama.com), running entirely on the
    #                user's own hardware. Free, no API key, no internet
    #                required once the model is pulled.
    #   "openai" -> optional paid acceleration via the OpenAI API, for
    #                anyone who wants it. Never required — if this is
    #                misconfigured or unreachable, Forge automatically
    #                falls back to "mock" rather than failing a request.
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "mock")
    # Explicit opt-in only: when True, real-provider failures may use MockProvider.
    # Default False so production never silently fabricates intelligence.
    AI_FALLBACK_TO_MOCK: bool = os.getenv("AI_FALLBACK_TO_MOCK", "false").lower() in ("1", "true", "yes")

    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen3-coder:latest")
    # Compatibility settings for the standalone Qwen worker, which uses
    # Ollama's OpenAI-compatible endpoint directly.
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    QWEN_MODEL_NAME: str = os.getenv("QWEN_MODEL_NAME", "qwen3-coder:latest")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    # Paid judgment calls are opt-in; an API key alone is not authorization.
    FORGEOS_OPENAI_JUDGE_ENABLED: bool = os.getenv(
        "FORGEOS_OPENAI_JUDGE_ENABLED", "false"
    ).lower() in ("1", "true", "yes")

    # The proposal-only cognitive worker is offline by default. External
    # providers require a separate adapter and explicit configuration.
    COGNITIVE_PROVIDER: str = os.getenv("COGNITIVE_PROVIDER", "mock")

    # --- Nepal payment providers (credentials are environment-only) ---
    ESEWA_MERCHANT_CODE: str = os.getenv("ESEWA_MERCHANT_CODE", "")
    ESEWA_SECRET_KEY: str = os.getenv("ESEWA_SECRET_KEY", "")
    ESEWA_FORM_URL: str = os.getenv("ESEWA_FORM_URL", "https://epay.esewa.com.np/api/epay/main/v2/form")
    ESEWA_STATUS_URL: str = os.getenv("ESEWA_STATUS_URL", DEFAULT_ESEWA_V2_STATUS_URL)
    KHALTI_SECRET_KEY: str = os.getenv("KHALTI_SECRET_KEY", "")
    KHALTI_API_BASE_URL: str = os.getenv("KHALTI_API_BASE_URL", "https://khalti.com/api/v2")
    # Public checkout stays closed until production merchant configuration,
    # callback verification and the public origin have been verified.
    FORGEOS_PUBLIC_CHECKOUT_ENABLED: bool = os.getenv(
        "FORGEOS_PUBLIC_CHECKOUT_ENABLED", "false"
    ).lower() in ("1", "true", "yes")
    PUBLIC_APP_URL: str = os.getenv("PUBLIC_APP_URL", "https://haminp.vercel.app")

    # --- Messaging (Twilio SMS) ---
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "")

    # Dedicated owner-only digest; closed unless the owner explicitly enables it.
    HAMI_OWNER_SMS_NUMBER: str = os.getenv("HAMI_OWNER_SMS_NUMBER", "")
    HAMI_OWNER_SMS_DIGEST_ENABLED: bool = os.getenv(
        "HAMI_OWNER_SMS_DIGEST_ENABLED", "false"
    ).lower() in ("1", "true", "yes")

    # Single-owner Telegram control; closed by default.
    HAMI_TELEGRAM_BOT_TOKEN: str = os.getenv("HAMI_TELEGRAM_BOT_TOKEN", "")
    HAMI_TELEGRAM_WEBHOOK_SECRET: str = os.getenv("HAMI_TELEGRAM_WEBHOOK_SECRET", "")
    HAMI_TELEGRAM_OWNER_CHAT_ID: str = os.getenv("HAMI_TELEGRAM_OWNER_CHAT_ID", "")
    HAMI_TELEGRAM_OWNER_USER_ID: str = os.getenv("HAMI_TELEGRAM_OWNER_USER_ID", "")
    HAMI_TELEGRAM_CONTROL_ENABLED: bool = os.getenv("HAMI_TELEGRAM_CONTROL_ENABLED", "false").lower() in ("1", "true", "yes")
    HAMI_TELEGRAM_OWNER_DIGEST_ENABLED: bool = os.getenv("HAMI_TELEGRAM_OWNER_DIGEST_ENABLED", "false").lower() in ("1", "true", "yes")
    HAMI_TELEGRAM_ASK_CODE_TTL_SECONDS: int = _int_env("HAMI_TELEGRAM_ASK_CODE_TTL_SECONDS", 600)

    # --- Outbound Email (Standard Library SMTP over TLS) ---
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = _int_env("SMTP_PORT", 587)
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
    SMTP_TIMEOUT_SECONDS: int = _int_env("SMTP_TIMEOUT_SECONDS", 20)
    FORGE_BOT_OWNER_EMAIL_TIMEOUT_SECONDS: int = _int_env(
        "FORGE_BOT_OWNER_EMAIL_TIMEOUT_SECONDS", 5
    )

    # --- Forge Memory Layer (embeddings/search) ---
    # Same $0-first pattern as AI_PROVIDER: "hash" needs nothing (pure
    # Python, no network, no model) and always works. "ollama" uses a
    # real local embedding model via the same Ollama server as
    # AI_PROVIDER=ollama, for meaningfully better semantic search —
    # still free, still local. Mixing the two is avoided by tagging
    # every stored embedding with the model that produced it (see
    # embedding_engine.py); switching this setting doesn't corrupt old
    # embeddings, it just stops comparing against them until re-synced.
    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "hash")  # "hash" | "ollama"
    OLLAMA_EMBEDDING_MODEL: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
    HASH_EMBEDDING_DIM: int = _int_env("HASH_EMBEDDING_DIM", 128)

    # --- CORS ---
    # The frontend runs locally on 127.0.0.1:3002 in this environment, and
    # the dev UI also commonly uses localhost:3000. Keep the default list in
    # sync with the real browser origins and allow overriding via env.
    ALLOWED_ORIGINS: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3002,http://127.0.0.1:3002,http://0.0.0.0:3002,http://localhost:8080,http://127.0.0.1:8080",
    )

    # --- Security (opt-in) ---
    # Leave empty (default) for local-first operation with no auth. To protect
    # any state-changing API call outside localhost, set FORGE_API_KEY to a
    # non-empty secret; clients must send it via the `X-API-Key` header
    # (see app/security.py). Never commit
    # a real secret; set it via environment only.
    FORGE_API_KEY: str = os.getenv("FORGE_API_KEY", "")

    # --- Forge Bot v0 (lead intake & owner notifications) ---
    # FORGE_BOT_LIVE controls real external/customer-facing side effects.
    # When false: synthetic/test execution is allowed, internal owner
    # notifications are allowed, but no real lead outreach or customer
    # messaging occurs.
    # When true: activation is an explicit owner decision; code never
    # silently enables it. Real external/customer-facing behavior becomes
    # possible.
    FORGE_BOT_LIVE: bool = os.getenv("FORGE_BOT_LIVE", "false").lower() in ("1", "true", "yes")

    # FORGE_BOT_INTAKE_ENABLED controls whether the web form accepts
    # submissions. When false, POST /forge-bot/leads returns 503.
    # State machine:
    #   INTAKE_ENABLED=false, LIVE=false → form disabled, no submissions
    #   INTAKE_ENABLED=true,  LIVE=false → form enabled, test/synthetic only
    #   INTAKE_ENABLED=true,  LIVE=true  → form enabled, real customer activity possible
    FORGE_BOT_INTAKE_ENABLED: bool = os.getenv(
        "FORGE_BOT_INTAKE_ENABLED", "false"
    ).lower() in ("1", "true", "yes")

    FORGE_BOT_CONTACT_EMAIL: str = os.getenv(
        "FORGE_BOT_CONTACT_EMAIL", ""
    )
    FORGE_BOT_BOOKING_URL: str = os.getenv(
        "FORGE_BOT_BOOKING_URL",
        "https://cal.com/hami-forge-m9agd6/build-hami",
    )
    # Required for privacy-preserving permanent suppression after opt-out.
    FORGE_BOT_CONTACT_HMAC_KEY: str = os.getenv("FORGE_BOT_CONTACT_HMAC_KEY", "")
    # Separate final gate for any future Forge Bot customer-response sender.
    # No such sender is wired; this must remain false until one is authorized.
    FORGE_BOT_RESPONSE_SEND_ENABLED: bool = os.getenv(
        "FORGE_BOT_RESPONSE_SEND_ENABLED", "false"
    ).lower() in ("1", "true", "yes")

    FORGEOS_LEGACY_INTELLIGENCE_ENABLED: bool = os.getenv(
        "FORGEOS_LEGACY_INTELLIGENCE_ENABLED", "false"
    ).lower() in ("1", "true", "yes")

    # Recurring generators stay paused until the existing research backlog is
    # reviewed for specificity, falsifiability, and an answerable evidence path.
    # Explicit owner/user-supplied research requests use their own governed paths.
    FORGEOS_AUTO_RESEARCH_QUESTION_GENERATION_ENABLED: bool = os.getenv(
        "FORGEOS_AUTO_RESEARCH_QUESTION_GENERATION_ENABLED", "false"
    ).lower() in ("1", "true", "yes")

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
