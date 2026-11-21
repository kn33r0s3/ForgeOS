# Hami Research Intelligence — Phase 1 Diagnosis

Date: 21 Nov 2026. Verified from the ForgeOS repo on the Mac, by reading the
actual files. No assumptions, no summaries — every claim below cites a file.

## The question
Why do questions requiring web research get poor or empty responses from Hami?

## Answer in one line
Hami's chat has no tools and no search provider, and the research machinery
that DOES exist is not connected to the live chat path. The model can only
answer from its weights.

## What EXISTS (the machinery is real — recover it, do not rebuild it)

| Component | File | Size | Modified |
|---|---|---|---|
| Research planner | backend/app/services/research_planner.py | 109,247 B | 15 Nov 2026 |
| Discovery engine | backend/app/services/discovery_engine.py | 150,451 B | 14 Nov 2026 |
| Capability discovery | backend/app/services/capability_discovery.py | 40,309 B | 13 Oct 2026 |
| Discovery selection | backend/app/services/discovery_selection.py | 18,694 B | 9 Oct 2026 |
| Prospect discovery | backend/app/services/prospect_discovery.py | 13,268 B | 30 Sep 2026 |
| Curiosity engine | backend/app/services/curiosity_engine.py | 28,489 B | 9 Oct 2026 |
| Collector runner | backend/app/services/collector_runner.py | 40,783 B | 13 Oct 2026 |
| OpenAlex collector (academic) | backend/app/services/collectors/openalex.py | 24,022 B | 14 Nov 2026 |
| World Bank collector | backend/app/services/collectors/world_bank.py | 19,275 B | 30 Sep 2026 |
| GDELT collector (news/events) | backend/app/services/collectors/gdelt.py | 12,590 B | 30 Sep 2026 |
| Crossref collector (academic) | backend/app/services/collectors/crossref.py | 9,094 B | 30 Sep 2026 |
| Web collector (page fetch) | backend/app/services/collectors/web.py | 6,113 B | 30 Sep 2026 |
| RSS / Reddit / arXiv / GitHub collectors | backend/app/services/collectors/ | 2.5–3.6 KB each | 30 Sep 2026 |

Tests exist and pass as part of the backend suite (1,384 passed, 19 Nov):
test_research_planner.py, test_world_bank_collector.py,
test_openalex_collector.py, test_gdelt_collector.py,
test_crossref_collector.py, test_web_collector.py.

## What is BROKEN — finding 1: there is no general web search

The web collector (backend/app/services/collectors/web.py, 168 lines) states
it in its own docstring:

> "There is no free general-purpose web *search* API without a key, so
> unlike the other collectors, `query` here is treated as a direct URL
> to fetch rather than a search term. A future version could add a
> proper search layer (e.g. a self-hosted SearXNG instance) in front of
> this without changing the SourceCollector interface."

Consequences, verified:
- `web_search` appears NOWHERE in backend/app (0 matches).
- `SEARCH_API` appears NOWHERE in backend (0 matches).
- The web collector only fetches a direct URL. Give it a search term like
  "Nepal economy" and it fails — that is not a URL.
- The other collectors hit SPECIFIC APIs (World Bank, OpenAlex, GDELT,
  Crossref, RSS, Reddit, arXiv, GitHub). They work for their domains, but
  there is no GENERAL web search.
- The October 9 clue is CONFIRMED: the web-search provider was reported
  unconfigured then, and it still is now. It was never fixed.

## What is BROKEN — finding 2: the research machinery is disconnected from live chat

The live chat endpoint is backend/app/api/hami_chat.py (226 lines, 10,489 B).
Read in full and grepped. Results:
- `research`: 0 lines. `planner`: 0 lines. `discovery`: 0 lines.
- `search`: 0 lines. `collect`: 0 lines. `curiosity`: 0 lines.
- `tool`: 1 line — line 61, a docstring: "talk here; actions happen
  through the owner's tools." That is a comment, not a tool system.
- Imports: only json, os, time, urllib, fastapi, pydantic. No research
  planner, no discovery engine, no collectors, no search.
- `gateway`: 14 lines. The handler forwards the message to the gateway
  (127.0.0.1:11435 → MLX 11436) and returns the reply.

The live path is: user message → hami_chat.py → gateway → MLX → reply.
The research planner, discovery engine, curiosity engine, and collectors
are NEVER called from this path. They are tested code that the live chat
does not use. The chat is talk-only by construction.

## What this explains
- "What happened in Nepal today?" → the model has no tools, no search, no
  live data. It can only answer from its weights (cut off, often wrong or
  empty on current events).
- "What is Nepal's latest inflation rate?" → same. No official-data retrieval.
- "Find businesses in Kathmandu that need websites" → same. No discovery.
- "Is this information still accurate?" → same. No verification step.
- The model is not failing at reasoning. It is failing because it has no
  way to reach the outside world, and the machinery that could do it is
  not wired in.

## What Phase 2 must do (repair, in order)
1. Add a real general web-search provider. The web.py docstring already
   names the route: a self-hosted SearXNG instance in front of the web
   collector, without changing the SourceCollector interface. Free, local,
   no key. That is the first fix — without it, there is nothing to call.
2. Wire the research planner into the chat path: hami_chat.py must route a
   message through intent → planner → tool selection → search → retrieval
   → synthesis, and return the researched answer. The planner, discovery
   engine, and collectors are recovered and used as they are — not rebuilt.
3. Give the model tool definitions at inference time (through the gateway),
   so Hami's own model decides what to investigate and interprets the
   results. A deterministic tool-execution layer performs the search.
   The model and the tools stay separate. No borrowed model is the hidden
   intelligence.
4. Store research results in the six primitives (ENTITY, RELATION, EVENT,
   EVIDENCE, CAPABILITY, ACTION). A search result is EVIDENCE, not a
   verified fact. Keep hypotheses separate from established facts.
5. Run the 12 verification tests from the mandate against the real chat
   (general knowledge with no search, current events, Nepal research,
   official statistics, unknown subject, fact verification, multi-step,
   provider down, bad tool args, empty results, Nepali question, follow-up).
   Then run the 6-question research benchmark.

## What Phase 2 must NOT do
- Do not build a new search system from scratch. Recover the existing one.
- Do not create a parallel research ledger. Use the six primitives.
- Do not fabricate search results or evidence.
- Do not silently fall back to another model. Hami's own model decides.
- Do not declare completion because a search API responds. Completion is
  a user asking an unfamiliar or current question and Hami independently
  researching it and delivering a useful, cited answer through the real chat.

## Evidence files (all on the Mac)
- backend/app/services/research_planner.py (109,247 B)
- backend/app/services/discovery_engine.py (150,451 B)
- backend/app/services/collectors/web.py (6,113 B) — the docstring quote
- backend/app/api/hami_chat.py (226 lines, 10,489 B) — the grep counts
