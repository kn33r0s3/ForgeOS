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
  - HashEmbeddingProvider is now the ONLY embedding provider.
                              The external embedding provider is gone:
                              hami-model generates text, it does not
                              produce embedding vectors, and no embedding
                              endpoint exists on the serving path.

Embeddings from different providers/models live in different vector
spaces and are NOT comparable to each other. Every stored Knowledge
row is tagged with the embedding_model that produced its vector (see
models.Knowledge.embedding_model); memory_layer.py only ever compares
embeddings with matching tags.
"""

from __future__ import annotations

import hashlib
import json
import math
from abc import ABC, abstractmethod
from typing import Optional

from app.config import settings
from app.services.pattern_engine import tokenize


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


def get_embedding_provider() -> EmbeddingProvider:
    """Factory, mirroring ai_engine.get_provider(). Hash is the only
    embedding provider; EMBEDDING_PROVIDER is always "hash"."""
    return HashEmbeddingProvider()


def get_embedding(text: str) -> tuple[list[float], str]:
    """Embed text with the hash provider. Returns (vector,
    model_name) — model_name must be stored alongside the vector so
    future searches know which space it's in."""
    provider = get_embedding_provider()
    return provider.embed(text), provider.model_name


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
