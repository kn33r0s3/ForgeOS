"""
AI ENGINE
=========

Single entry point for every AI-generated piece of text in Forge:
market analysis, business ideas, MVP plans, validation steps, and
marketing strategy snippets.

$0 OPERATING COST IS A HARD CONSTRAINT, NOT A DEFAULT TO OVERRIDE:
Forge must run completely free, with no required credit card,
subscription, or paid inference, on the user's own hardware. Paid AI
(OpenAI) is optional acceleration only — never a dependency. Every
high-level generate_*() function below routes through
_complete_with_fallback(), which guarantees that even a fully broken
or unreachable paid/local provider degrades to the free MockProvider
instead of failing the request.

Design goal: the rest of the app (opportunity_engine, api/analyze)
never talks to a specific provider directly. It calls functions on
this module. That means swapping providers never touches any other
file.

Providers
---------
- MockProvider   : deterministic, offline, zero cost, zero setup.
                    Default. Keeps Forge fully usable on a low-end
                    laptop with no API key, no local model, and no
                    internet at all.
- OllamaProvider : a real, free, open-source model running on the
                    user's own machine via Ollama (https://ollama.com).
                    No API key, no per-token cost, no internet required
                    once a model is pulled. The intended "better than
                    mock, still $0" path.
- OpenAIProvider : OPTIONAL paid acceleration via the OpenAI API. Only
                    used if explicitly configured; never required, and
                    the `openai` package itself is an optional install
                    (see requirements-optional.txt).
"""

from __future__ import annotations

import re
import textwrap
from abc import ABC, abstractmethod

from app.config import settings


class AIUnavailableError(RuntimeError):
    """Raised when a real AI provider was configured but is unavailable.

    Production code must surface this as AI_UNAVAILABLE / degraded —
    never silently replace with fabricated MockProvider output unless
    AI_PROVIDER is explicitly set to "mock" or DEMO_MODE is on.
    """
    def __init__(self, provider: str, reason: str):
        self.provider = provider
        self.reason = reason
        super().__init__(f"AI_UNAVAILABLE provider={provider}: {reason}")



class AIProvider(ABC):
    """Common interface every AI backend must implement."""

    @abstractmethod
    def complete(self, prompt: str, system: str = "") -> str:
        """Return a text completion for the given prompt."""
        raise NotImplementedError


class MockProvider(AIProvider):
    """
    Offline provider used when AI_PROVIDER=mock (the default) or when
    no OpenAI key is configured. Produces reasonable, readable output
    using simple heuristics/templates instead of a real model call, so
    the full Forge loop (signal -> pattern -> opportunity -> analysis)
    works with zero setup and zero cost.
    """

    def complete(self, prompt: str, system: str = "") -> str:
        # Very small "understanding" step: pull out a plausible subject
        # phrase from the prompt so the mock output doesn't feel totally
        # generic. This is intentionally simple — it's a placeholder for
        # a real model, not a model itself.
        idea = _extract_idea_text(prompt)
        idea_short = idea.strip().rstrip(".")
        if len(idea_short) > 120:
            idea_short = idea_short[:117] + "..."

        if "market analysis" in prompt.lower():
            return (
                f"There is a recurring, verifiable pain point around: \"{idea_short}\". "
                "Early indicators suggest a fragmented market with mostly manual or ad-hoc "
                "solutions today, which usually signals room for a focused product. "
                "Competition is likely indirect (spreadsheets, generic tools, manual labor) "
                "rather than a single dominant player, which lowers the barrier for a "
                "well-targeted MVP to get initial traction."
            )
        if "mvp plan" in prompt.lower():
            return (
                "1) Interview 10-15 people who experience this problem weekly.\n"
                "2) Build the smallest possible version that solves ONE step of the "
                "problem end-to-end (no polish, manual backend allowed).\n"
                "3) Charge money for it, even a small amount, within the first 2 weeks.\n"
                "4) Use a no-code or low-code front layer if possible to cut build time.\n"
                "5) Ship to 5 real users before writing a single extra feature."
            )
        if "validation" in prompt.lower():
            return (
                "1) Post the problem statement in 2-3 relevant online communities and "
                "measure reply/engagement rate.\n"
                "2) Run 5 paid or unpaid pilot users through the manual/MVP version.\n"
                "3) Track whether users come back a second time unprompted (real signal "
                "of value vs. politeness).\n"
                "4) Ask directly: 'Would you pay $X/month for this?' and log the answers.\n"
                "5) Kill or pivot if fewer than 3 of 10 target users show real urgency."
            )
        if "marketing" in prompt.lower():
            return (
                "Lead with the specific pain point in plain language (not the product "
                "name) in all messaging. Target the exact forums, subreddits, or Slack/"
                "Discord communities where this audience already complains about the "
                "problem. Use founder-led outreach (DMs, comments, small posts) before "
                "any paid spend — it's free and it validates messaging simultaneously."
            )
        if "business idea" in prompt.lower() or "solution" in prompt.lower():
            return (
                f"A focused tool or service that directly resolves: \"{idea_short}\". "
                "Start narrow (one customer segment, one workflow) rather than building "
                "a broad platform, then expand once the core value is proven."
            )

        # Generic fallback
        return (
            f"Based on the input (\"{idea_short}\"), Forge suggests validating the core "
            "assumption with real users before building further, and keeping the first "
            "version deliberately small."
        )


class OllamaProvider(AIProvider):
    """
    Real, free, local model provider via Ollama (https://ollama.com) —
    the intended default path for anyone who wants better-than-mock
    output without paying for or depending on a cloud API. Runs
    entirely on the user's own hardware; no API key, no per-token cost,
    no internet required once a model has been pulled.

    Requires Ollama installed and running locally:
        ollama pull qwen3-coder:latest  # one-time, downloads the model
        ollama serve               # usually already running as a service

    Uses only the stdlib (urllib/json) to talk to Ollama's local REST
    API — no extra pip dependency for this provider.
    """

    def __init__(self):
        self._host = settings.OLLAMA_HOST.rstrip("/")
        self._model = settings.OLLAMA_MODEL

    def complete(self, prompt: str, system: str = "") -> str:
        import json
        import urllib.request

        payload = {
            "model": self._model,
            "prompt": prompt,
            "system": system,
            "stream": False,
        }
        request = urllib.request.Request(
            f"{self._host}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise RuntimeError(
                f"Ollama request failed — is `ollama serve` running with "
                f"model '{self._model}' pulled? ({exc})"
            ) from exc
        return (data.get("response") or "").strip()


class OpenAIProvider(AIProvider):
    """Optional, paid acceleration via the OpenAI API. Used only when
    AI_PROVIDER=openai and a key is set — never required. The `openai`
    package itself is an OPTIONAL dependency (see requirements-optional.txt);
    it's imported lazily here so a base Forge install never needs it."""

    def __init__(self):
        from openai import OpenAI  # optional dependency — see requirements-optional.txt

        self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = settings.OPENAI_MODEL

    def complete(self, prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()


def _extract_idea_text(prompt: str) -> str:
    """Pull the quoted idea/problem text out of a templated prompt, used
    only by MockProvider to make its output feel grounded."""
    match = re.search(r'"([^"]{3,300})"', prompt)
    if match:
        return match.group(1)
    return prompt[:120]


def get_provider() -> AIProvider:
    """
    Factory: returns the active AI provider based on settings.

    AI_PROVIDER=openai and a real key -> OpenAIProvider (optional, paid)
    AI_PROVIDER=ollama                 -> OllamaProvider (free, local)
    anything else                       -> MockProvider (free, offline, always works)

    Construction failures (missing `openai` package, bad key) fall back
    to MockProvider immediately. Runtime failures (Ollama not running,
    OpenAI network error) are handled separately by
    _complete_with_fallback() below, since those only surface once
    .complete() is actually called.
    """
    if settings.AI_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        return OpenAIProvider()  # construction errors surface as AI_UNAVAILABLE
    if settings.AI_PROVIDER == "ollama":
        return OllamaProvider()
    if settings.AI_PROVIDER == "mock":
        return MockProvider()
    # Unknown provider name: explicit mock only when requested; otherwise unavailable
    return MockProvider()


def get_provider_status() -> dict:
    """Inspectable provider status — never claims intelligence when degraded."""
    name = settings.AI_PROVIDER
    if name == "mock":
        return {"provider": "mock", "status": "MOCK", "note": "Deterministic templates only. Not production intelligence."}
    try:
        p = get_provider()
        if isinstance(p, MockProvider):
            return {"provider": name, "status": "AI_UNAVAILABLE", "note": "Configured for real provider but resolved to mock."}
        return {"provider": name, "status": "READY", "note": "Real provider configured."}
    except Exception as e:
        return {"provider": name, "status": "AI_UNAVAILABLE", "note": str(e)}


def _complete_with_fallback(prompt: str, system: str = "", context: str = "") -> str:
    """Run completion through configured provider.

    When AI_PROVIDER is explicitly "mock": use MockProvider (tests/demo).
    When AI_PROVIDER is ollama/openai and fails: raise AIUnavailableError
    unless settings.AI_FALLBACK_TO_MOCK is True (explicit opt-in for demos).

    Never silently fabricate intelligence when the user asked for a real model.
    """
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    provider_name = settings.AI_PROVIDER

    if provider_name == "mock":
        return MockProvider().complete(full_prompt, system=system)

    try:
        provider = get_provider()
    except Exception as e:
        if getattr(settings, "AI_FALLBACK_TO_MOCK", False):
            return MockProvider().complete(full_prompt, system=system)
        raise AIUnavailableError(provider_name, f"provider construction failed: {e}") from e

    if isinstance(provider, MockProvider):
        # Config asked for real provider but we only have mock path
        if getattr(settings, "AI_FALLBACK_TO_MOCK", False):
            return provider.complete(full_prompt, system=system)
        raise AIUnavailableError(provider_name, "real provider not available")

    try:
        return provider.complete(full_prompt, system=system)
    except Exception as e:
        if getattr(settings, "AI_FALLBACK_TO_MOCK", False):
            return MockProvider().complete(full_prompt, system=system)
        raise AIUnavailableError(provider_name, str(e)) from e


def _retrieve_context(db, query: str) -> str:
    """Fetch relevant Forge Memory Layer context for a query, if a db
    session was provided. Returns "" (no-op) when db is None, so every
    generate_*() function below works exactly as before for any caller
    that doesn't have a session handy — retrieval is additive, not
    required."""
    if db is None:
        return ""
    from app.services import memory_layer  # local import: keeps ai_engine usable with zero db dependency when db=None

    try:
        return memory_layer.retrieve_context_for_prompt(db, query, top_k=3)
    except Exception:
        # A broken memory lookup should degrade to "no context", not
        # break generation — same $0-resilience principle as providers.
        return ""


# ---------------------------------------------------------------------
# High-level prompt functions used by the rest of the app.
#
# Each accepts an optional `db` session: when provided, Forge retrieves
# relevant memories from its own Knowledge base (see memory_layer.py)
# and grounds the prompt in them before calling the AI provider — this
# is what "Ollama retrieves relevant Forge memories before answering"
# means concretely. When db is omitted, these behave exactly as before.
# ---------------------------------------------------------------------

def generate_market_analysis(idea: str, db=None) -> str:
    prompt = textwrap.dedent(f"""
        You are a pragmatic startup analyst. Write a short market analysis
        (3-4 sentences, no fluff) for this business idea/problem:
        "{idea}"
        Cover: is this a real recurring problem, who has it, and how
        crowded the current solutions are.
    """).strip()
    context = _retrieve_context(db, idea)
    return _complete_with_fallback(prompt, system="You are Forge, a concise business analyst.", context=context)


def generate_solution(idea: str, db=None) -> str:
    prompt = textwrap.dedent(f"""
        Propose a specific, narrow business idea / solution (2-3 sentences)
        that solves this problem:
        "{idea}"
    """).strip()
    context = _retrieve_context(db, idea)
    return _complete_with_fallback(prompt, system="You are Forge, a concise business analyst.", context=context)


def generate_mvp_plan(idea: str, db=None) -> str:
    prompt = textwrap.dedent(f"""
        Write an MVP plan (numbered list, 4-6 steps, concrete and specific)
        for validating and building a first version of a business that solves:
        "{idea}"
    """).strip()
    context = _retrieve_context(db, idea)
    return _complete_with_fallback(prompt, system="You are Forge, a concise business analyst.", context=context)


def generate_validation_plan(idea: str, db=None) -> str:
    prompt = textwrap.dedent(f"""
        Write a validation plan (numbered list, 4-6 steps) to test real
        demand, before building much, for a business solving:
        "{idea}"
    """).strip()
    context = _retrieve_context(db, idea)
    return _complete_with_fallback(prompt, system="You are Forge, a concise business analyst.", context=context)


def generate_marketing_strategy(idea: str, db=None) -> str:
    prompt = textwrap.dedent(f"""
        Write a short go-to-market / marketing strategy (3-4 sentences)
        for a business solving:
        "{idea}"
    """).strip()
    context = _retrieve_context(db, idea)
    return _complete_with_fallback(prompt, system="You are Forge, a concise business analyst.", context=context)


def generate_pricing_idea(idea: str, db=None) -> str:
    prompt = textwrap.dedent(f"""
        Suggest one concrete pricing model (1-2 sentences, with a rough
        price point) for a business solving:
        "{idea}"
    """).strip()
    context = _retrieve_context(db, idea)
    return _complete_with_fallback(prompt, system="You are Forge, a concise business analyst.", context=context)


def answer_question(question: str, db) -> dict:
    """
    Forge is not a chatbot — it's a reality model that answers FROM its
    own accumulated, evidence-linked knowledge, not from general model
    knowledge dressed up as an opinion. This is the flagship retrieval-
    augmented function: it always retrieves relevant Knowledge first,
    and the prompt explicitly instructs the model to say so honestly if
    its own memory doesn't cover the question, rather than inventing an
    answer. Backs POST /forge/ask.

    Returns {"answer": str, "context_used": str} — context_used is
    exposed so callers (the API) can show what memory actually
    informed the answer, keeping this transparent rather than opaque.
    """
    from app.services import memory_layer

    context = memory_layer.retrieve_context_for_prompt(db, question, top_k=5)

    if context:
        prompt = textwrap.dedent(f"""
            {context}

            Using ONLY the knowledge above (which comes from Forge's own
            observed signals, detected patterns, and tested beliefs),
            answer this question in 2-4 sentences. If the knowledge above
            doesn't actually cover the question, say so honestly instead
            of guessing.

            Question: {question}
        """).strip()
    else:
        prompt = textwrap.dedent(f"""
            Forge has no relevant existing knowledge for this question yet.
            Say so plainly in one sentence, and suggest what kind of
            signals Forge would need to observe to be able to answer it.

            Question: {question}
        """).strip()

    answer = _complete_with_fallback(prompt, system="You are Forge, answering from your own accumulated knowledge only.")
    return {"answer": answer, "context_used": context}
