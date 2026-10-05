"""
EMBEDDING ENGINE
=================

Turns text into a fixed-length numeric vector for semantic search over
Forge's Memory Layer (see memory_layer.py). Same two-tier pattern as
ai_engine.py:

  - HashEmbeddingProvider : pure Python, zero dependencies, zero
                              network, always works. Uses the "hashing
                              trick" (feature hashing): each keyword
                              hashes into one of N buckets, giving a
                              crude but real bag-of-words vector that
                              cosine similarity can compare. This is
                              the $0-guaranteed default.
  - OllamaEmbeddingProvider : a real local embedding model (e.g.
                              nomic-embed-text) via the same Ollama
                              server used for AI_PROVIDER=ollama.
                              Meaningfully better semantic search,
                              still free, still local — just requires
                              `ollama pull nomic-embed-text` once.

Embeddings from different providers/models live in different vector
spaces and are NOT comparable to each other. Every stored Knowledge
row is tagged with the embedding_model that produced its vector (see
models.Knowledge.embedding_model); memory_layer.py only ever compares
embeddings with matching tags.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from abc import ABC, abstractmethod
from typing import Optional

from app.config import settings
from app.services.pattern_engine import tokenize


logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        """A stable identifier for the vector space this provider
        produces, stored alongside every embedding so incompatible
        vectors are never compared."""
        raise NotImplementedError


class HashEmbeddingProvider(EmbeddingProvider):
    """Feature-hashed bag-of-words vector. No model, no network, no
    dependency beyond the stdlib — the $0 guarantee for semantic
    search, same as MockProvider is for text generation."""

    def __init__(self, dimensions: Optional[int] = None):
        dim = dimensions or settings.HASH_EMBEDDING_DIM
        # A misconfigured HASH_EMBEDDING_DIM of 0 would crash embed()
        # with ZeroDivisionError (bucket = digest % 0); clamp to a
        # sane minimum instead of blowing up the call site.
        self._dimensions = max(1, dim)

    @property
    def model_name(self) -> str:
        return f"hash-{self._dimensions}"

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self._dimensions
        keywords = tokenize(text)
        if not keywords:
            return vector

        for word in keywords:
            digest = hashlib.sha256(word.encode("utf-8")).hexdigest()
            bucket = int(digest, 16) % self._dimensions
            # Sign hashing (a second hash bit decides +1/-1) reduces
            # collision bias compared to always incrementing the same
            # direction — standard practice for the hashing trick.
            sign = 1.0 if int(digest, 16) % 2 == 0 else -1.0
            vector[bucket] += sign

        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0:
            vector = [v / norm for v in vector]
        return vector


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Real local embedding model via Ollama's /api/embeddings
    endpoint. Stdlib only (urllib/json) — no extra pip dependency."""

    def __init__(self):
        self._host = settings.OLLAMA_HOST.rstrip("/")
        self._model = settings.OLLAMA_EMBEDDING_MODEL

    @property
    def model_name(self) -> str:
        return f"ollama:{self._model}"

    def embed(self, text: str) -> list[float]:
        import urllib.request

        payload = {"model": self._model, "prompt": text}
        request = urllib.request.Request(
            f"{self._host}/api/embeddings",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(
                f"Ollama embedding request failed — is `ollama serve` running "
                f"with model '{self._model}' pulled? ({exc})"
            ) from exc
        embedding = data.get("embedding")
        if not embedding:
            # A 200 with no embedding vector (e.g. a proxy/gateway HTML
            # body) must fail LOUDLY so get_embedding() falls back to the
            # hash provider. Returning [] silently would store a
            # zero-vector row tagged "ollama:<model>" that matches
            # nothing forever (memory_layer would keep it on the
            # skip-re-embed path since content "unchanged").
            raise RuntimeError(
                f"Ollama embedding request for model '{self._model}' "
                "returned no embedding vector in the response body."
            )
        return embedding


def get_embedding_provider() -> EmbeddingProvider:
    """Factory, mirroring ai_engine.get_provider(). EMBEDDING_PROVIDER=
    "ollama" upgrades to a real model; anything else (including an
    unset/invalid value) uses the always-free hash provider."""
    if settings.EMBEDDING_PROVIDER == "ollama":
        return OllamaEmbeddingProvider()
    return HashEmbeddingProvider()


def get_embedding(text: str) -> tuple[list[float], str]:
    """Embed text with the configured provider, falling back to the
    hash provider on any failure (Ollama not running, model not
    pulled, etc.) so indexing/search never breaks. Returns
    (vector, model_name) — model_name must be stored alongside the
    vector so future searches know which space it's in."""
    provider = get_embedding_provider()
    if isinstance(provider, HashEmbeddingProvider):
        return provider.embed(text), provider.model_name
    try:
        return provider.embed(text), provider.model_name
    except Exception as exc:
        # Silent fallback keeps indexing working, but rows written during
        # an Ollama outage are tagged "hash-…" and memory_layer never
        # re-embeds unchanged content — so log the outage LOUDLY; the
        # operator (owner) needs to know the memory index degraded.
        logger.warning(
            "Ollama embedding failed (%s) — falling back to hash provider; "
            "stored rows are tagged with the hash model, not ollama",
            exc,
        )
        fallback = HashEmbeddingProvider()
        return fallback.embed(text), fallback.model_name


def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """Pure-Python cosine similarity — no numpy, keeps Forge's
    dependency list unchanged. Fine for the brute-force search sizes a
    personal, local knowledge base actually reaches."""
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def serialize_embedding(vector: list[float]) -> str:
    return json.dumps(vector)


def deserialize_embedding(raw: Optional[str]) -> list[float]:
    if not raw:
        return []
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
