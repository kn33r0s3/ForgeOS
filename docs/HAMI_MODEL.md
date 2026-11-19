# hami-model — Hami's own model

The mandate (Niroj, 19 Nov 2026 ~17:28–17:29):
1. Hami's own model powers the Hami assistant.
2. No GPT-4, gpt-oss, ChatGPT, or external GPT fallback.
3. No pretending a borrowed model is Hami because of a system prompt.
4. One shared inference path for Meet Hami, Hami chat, the terminal and the embedded widget.
5. Model identity comes from the actual loaded model and serving process.
6. If Hami's model is unavailable, report unavailable. Never silently switch to another AI.
7. Keep developing and evaluating Hami's own model until it becomes capable of carrying the workload.

The standalone `hami-model-server.py` process loads the Hami checkpoint and tokenizer. This does not by itself prove that every repository path or deployment uses that server.

## What hami-model is today

The existing from-scratch pilot is a TinyLM with 13,916,160 parameters (6 layers,
`d_model=384`, 8 heads, context 512, tied embeddings). Its currently served
tokenizer uses `Whitespace` pre-tokenization without a decoder; it is not the
new tokenizer described below.

The pilot is experimental and not capable enough to claim as a useful Nepali
assistant. Do not treat its identity prompts, fluency, or factual answers as
reliable.

## How it is served

- `scripts/hami-model-server.py` — small torch server, 127.0.0.1:11437.
  Loads `checkpoint.pt` + `tokenizer.json` from the dir in `scripts/hami-model.txt`.
  `GET /status` reports the ACTUAL loaded model (name, checkpoint sha256, params,
  steps, holdout perplexity). `POST /api/chat` generates greedily.
  If the model files are missing it refuses to start — callers then report
  "Hami is unavailable", never fall back.
- `scripts/hami-model-server.sh` — launcher (Mac venv python with torch + tokenizers).
- `scripts/com.hami.model-server.plist` — launchd, RunAtLoad + KeepAlive.
- The intended shared route is backend `app/api/hami_chat.py` →
  `scripts/hami_model_gateway.py` (`/api/hami-llm/chat`) → model server.
- This path is not yet verified end-to-end for every app, embedded widget, or
  public deployment. Do not claim that all Hami projects currently use it.

## Local status

- The model server at `127.0.0.1:11437` returned HTTP 200 with `loaded=true`.
- Loaded checkpoint SHA-256:
  `40970731ffe1f0cc6e0221c69b37ac7ae9059120b9b58b3486d2abcfa4b1c50f`.
- It reports 3,000 training steps and holdout perplexity `1302.5124`; this
  result does not pass a quality gate.
- The new, isolated dataset is at `/Users/nirojpaudyal/Downloads/hami-model/next-run`.
  It contains 11,436 training records and 585 holdout records from FineWeb-2
  Nepali text, the Hami origin/system-map/architecture documents, and selected
  public Hami pages. The tokenizer is trained on training records only and uses
  byte-level encoding with a decoder; its Nepali/English round-trip test passes.
- This new corpus and tokenizer have **not** been used to train a checkpoint.
  The existing server checkpoint and its tokenizer were left unchanged.
- The documented gateway route at `127.0.0.1:11435/api/hami-llm/status`
  returned 401 without an `X-Hami-Key`; authentication is active, but this
  unauthenticated check does not establish upstream or public-project traffic.
- The previous `43.2` perplexity claim is not comparable to the current
  checkpoint: it came from a different tokenizer/run and should not be used as
  a promotion baseline.
