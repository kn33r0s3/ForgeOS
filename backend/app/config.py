"""
Forge configuration.

Centralizes all environment-driven settings so every module reads
config from one place. This keeps the system modular: swapping the
AI provider, the database, or future services (crawler, Reddit API,
Ollama) only means touching this file plus the relevant service.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- App ---
    APP_NAME: str = "ForgeOS"
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

    # --- Nepal payment providers (credentials are environment-only) ---
    ESEWA_MERCHANT_CODE: str = os.getenv("ESEWA_MERCHANT_CODE", "")
    ESEWA_SECRET_KEY: str = os.getenv("ESEWA_SECRET_KEY", "")
    ESEWA_FORM_URL: str = os.getenv("ESEWA_FORM_URL", "https://epay.esewa.com.np/api/epay/main/v2/form")
    ESEWA_STATUS_URL: str = os.getenv("ESEWA_STATUS_URL", "https://esewa.com.np/api/epay/transaction/status/")
    KHALTI_SECRET_KEY: str = os.getenv("KHALTI_SECRET_KEY", "")
    KHALTI_API_BASE_URL: str = os.getenv("KHALTI_API_BASE_URL", "https://khalti.com/api/v2")

    # --- Messaging (Twilio SMS) ---
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "")

    # --- Outbound Email (Standard Library SMTP over TLS) ---
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
    SMTP_TIMEOUT_SECONDS: int = int(os.getenv("SMTP_TIMEOUT_SECONDS", "20"))

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
    HASH_EMBEDDING_DIM: int = int(os.getenv("HASH_EMBEDDING_DIM", "128"))

    # --- CORS ---
    # The frontend runs locally on 127.0.0.1:3002 in this environment, and
    # the dev UI also commonly uses localhost:3000. Keep the default list in
    # sync with the real browser origins and allow overriding via env.
    ALLOWED_ORIGINS: list[str] = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3002,http://127.0.0.1:3002,http://0.0.0.0:3002",
    ).split(",")

    # --- Security (opt-in) ---
    # Leave empty (default) for local-first operation with no auth. To protect
    # any state-changing API call outside localhost, set FORGE_API_KEY to a
    # non-empty secret; clients must send it via `X-API-Key` header or
    # `?api_key=` on POST/PUT/PATCH/DELETE (see app/security.py). Never commit
    # a real secret; set it via environment only.
    FORGE_API_KEY: str = os.getenv("FORGE_API_KEY", "")

    class Config:
        env_file = ".env"


settings = Settings()
