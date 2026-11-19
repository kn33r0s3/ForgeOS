# hami-model — Hami's own model

The mandate (Niroj, 19 Nov 2026 ~17:28–17:29):
1. Hami's own model powers the Hami assistant.
2. No GPT-4, gpt-oss, ChatGPT, or external GPT fallback.
3. No pretending a borrowed model is Hami because of a system prompt.
4. One shared inference path for Meet Hami, Hami chat, the terminal and the embedded widget.
5. Model identity comes from the actual loaded model and serving process.
6. If Hami's model is unavailable, report unavailable. Never silently switch to another AI.
7. Keep developing and evaluating Hami's own model until it becomes capable of carrying the workload.

Nothing — no code, no file, no project — uses gpt-oss, GPT, Ollama, Qwen, or any other model. Only hami-model.

## What hami-model is today

The from-scratch pilot, built from nothing on Hami's own data:
- TinyLM, ~14M params (6 layers, d_model 384, 8 heads, ctx 512, tied embeddings).
- Own byte-level BPE tokenizer, 8,000 vocab, trained on Hami's data only.
- Trained on v2 real Nepali text + news (10,275,610 tokens, 300 steps, seed 42).
- Holdout perplexity 43.2. It does NOT speak coherent Nepali yet — it starts a phrase
  ("नेपालको राजधानी") then degenerates into repeating "र". Beginner level, accepted.
- The Qwen3-4B + clean adapter (94 vs 96 tie) is OUT of serving under this mandate.
  Its eval record stays in docs; its training data and config are preserved.

## How it is served

- `scripts/hami-model-server.py` — small torch server, 127.0.0.1:11437.
  Loads `checkpoint.pt` + `tokenizer.json` from the dir in `scripts/hami-model.txt`.
  `GET /status` reports the ACTUAL loaded model (name, checkpoint sha256, params,
  steps, holdout perplexity). `POST /api/chat` generates greedily.
  If the model files are missing it refuses to start — callers then report
  "Hami is unavailable", never fall back.
- `scripts/hami-model-server.sh` — launcher (Mac venv python with torch + tokenizers).
- `scripts/com.hami.model-server.plist` — launchd, RunAtLoad + KeepAlive.
- The gateway (`scripts/hami_ollama_gateway.py`) is the ONLY caller of the model server.
  Backend `app/api/hami_chat.py` → gateway `/api/hami-llm/chat` → model server.
  Meet Hami, Hami chat, the terminal and the widget all go through that one path.
  Live reaches the gateway through the Cloudflare tunnel; local code reaches it
  on localhost. Same server, same model, same answers.

## Status (19 Nov 2026, evening)

- Server files written. NOT started yet: the model files are still on the VM
  (checkpoint split into two <50 MB chunks, sha256 b53bc33219fa…; tokenizer,
  training script and tokens ready) and torch + tokenizers are not yet installed
  on the Mac. Transfer + install + first start are Order 025's steps, after the
  v3 media run ends.
- Next rung (point 7): continue the pilot on the v2 real Nepali text + news + courses
  + history, more steps, until holdout perplexity beats 43.2 and samples turn coherent.
  The v2 training order is rewritten to this target (no Qwen LoRA, no Alpaca anchor).
