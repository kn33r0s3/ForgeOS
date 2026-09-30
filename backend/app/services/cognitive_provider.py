"""Replaceable provider boundary for bounded, proposal-only cognition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Protocol, Sequence

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from app.config import settings

MAX_COGNITIVE_OBJECTIVE_CHARS = 2_000
MAX_COGNITIVE_EVIDENCE_IDS = 10
MAX_COGNITIVE_PROPOSALS = 3


class CognitiveProviderError(RuntimeError):
    """A cognitive provider could not safely produce a proposal."""


class CognitiveProviderUnavailable(CognitiveProviderError):
    """The selected cognitive provider is not installed or configured."""


class CognitiveProposalValidationError(CognitiveProviderError):
    """Provider output did not satisfy the proposal-only contract."""


class CognitiveTaskBoundsError(ValueError):
    """The research context exceeds the bounded cognitive task contract."""


class CognitiveTaskInputError(ValueError):
    """A task does not reference a valid existing research record."""


@dataclass(frozen=True)
class CognitiveTaskContext:
    research_task_id: int
    objective: str
    evidence_ids: tuple[int, ...]
    evidence_refs_truncated: bool
    max_proposals: int = MAX_COGNITIVE_PROPOSALS


class CognitiveProposal(BaseModel):
    """A bounded research follow-up suggestion, never an executable action."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["research_follow_up"]
    title: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=400)
    next_step: str = Field(min_length=1, max_length=240)
    evidence_ids: list[StrictInt] = Field(default_factory=list, max_length=MAX_COGNITIVE_EVIDENCE_IDS)
    status: Literal["PROPOSED"] = "PROPOSED"
    execution_authorized: Literal[False] = False


class CognitiveProvider(Protocol):
    """Provider interface kept independent from the existing text AI engine."""

    name: str
    version: str
    mode: Literal["MOCK", "TEST", "EXTERNAL"]

    def propose(self, context: CognitiveTaskContext) -> Sequence[Mapping[str, Any]]:
        """Return candidate proposals; callers validate them before persistence."""
        ...


class MockCognitiveProvider:
    """Deterministic offline provider; its templates are not evidence."""

    name = "mock"
    version = "deterministic-v1"
    mode: Literal["MOCK"] = "MOCK"

    def propose(self, context: CognitiveTaskContext) -> Sequence[Mapping[str, Any]]:
        return [
            {
                "kind": "research_follow_up",
                "title": "Review the outstanding research question",
                "rationale": (
                    "Offline mock template only. It does not assess source content "
                    "or establish a factual conclusion."
                ),
                "next_step": (
                    "Have an authorized operator select a cleared source and review "
                    "the question before any collection."
                ),
                "evidence_ids": [],
                "status": "PROPOSED",
                "execution_authorized": False,
            }
        ][: context.max_proposals]


def get_cognitive_provider(provider_name: str | None = None) -> CognitiveProvider:
    """Return only an explicitly selected implementation; never silently fallback."""
    selected = (provider_name or settings.COGNITIVE_PROVIDER).strip().lower()
    if selected == "mock":
        return MockCognitiveProvider()
    if selected in {"gemini", "google"}:
        raise CognitiveProviderUnavailable(
            "Gemini cognitive provider is unavailable: the repository has no "
            "GEMINI_API_KEY setting or Gemini client dependency; no provider call was made."
        )
    raise CognitiveProviderUnavailable(
        f"Unsupported cognitive provider '{selected}'; configure 'mock' or install an adapter."
    )
