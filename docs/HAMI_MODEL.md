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
- This served checkpoint remains unchanged. It is separate from all experimental
  checkpoints; none has been promoted or loaded into the server.
- ForgeOS now defaults both `AI_PROVIDER` and `COGNITIVE_PROVIDER` to
  `hami-model`, with mock fallback disabled. This selects the guarded local
  gateway path; it does not prove that the local gateway, tunnel, or public
  projects are currently reachable.
- The backend chat route forwards conversation context to the gateway, but the
  gateway currently sends only the latest user message to the model server.
  The raw-text pilot is not instruction-tuned, so system prompts and history do
  not condition its response.

## Isolated training experiments

The experiments use the same from-scratch 13.9M-parameter architecture. Their
perplexities are not comparable across tokenizers; bits per character (BPC) is
the current cross-tokenizer metric. All remain experimental because generated
Nepali has shown repetition or incoherence.

- `next-run`: byte-level tokenizer, 3,000 steps, holdout BPC `3.632`;
  checkpoint SHA-256 begins `161330ff`.
- `next-run-metaspace`: Metaspace tokenizer, 3,000 steps, holdout BPC `2.605`;
  checkpoint SHA-256 begins `01c785e2`. Samples still repeated.
- `next-run-metaspace-init`: Metaspace with normalized initialization and
  residual scaling, 3,000 steps, holdout BPC `1.824`, perplexity `167.233`,
  checkpoint SHA-256
  `fa842daf09f8d7e089744479171fa6c8994a2f28989900724394d1807e300e06`.
  The candidate loaded strictly into the serving model class, but greedy
  generation collapsed to repeated question marks: across four fixed prompts,
  the repeated-trigram fraction was `0.989`. Non-question prompts produced
  only short, incomplete fragments. It fails the quality gate.
- `next-run-stratified-v2`: Metaspace with normalized initialization, 3,000
  steps, holdout BPC `1.759`, perplexity `155.483`, checkpoint SHA-256
  `ae417409ed42c710eeab8394c1a93168d31750db64c94109ad455c0e45604891`.
  The candidate loaded strictly into the serving model class, but greedy
  output repeated short phrases (repeated-trigram fractions `0.809`–`0.979`
  over six prompts). Top-k sampling produced varied but incoherent text. It
  also fails the quality gate.
- `next-run-expanded-50k`: Metaspace with normalized initialization, 3,000
  steps, holdout BPC `1.724`, perplexity `155.648`, checkpoint SHA-256
  `246735b9668f98473025b14e3ce878986ca59cd2e92fb1b2dc28adfb0c9daa7b`.
  The candidate loaded strictly into the serving model class, but greedy
  output again collapsed into punctuation or repeated tokens (repeated-trigram
  fractions `0.926`–`0.989` across six prompts). It fails the quality gate.
- The same expanded run was warm-started to 6,000 total steps with a fresh
  optimizer. Holdout BPC fell to `1.541` and perplexity to `91.109`; checkpoint
  SHA-256 is
  `485082a1de8ea771050116a429bf1b7a1713eb8b7941bcca6df16517d7d83e19`.
  Greedy outputs still looped (repeated-trigram fractions `0.809`–`0.989`);
  top-k sampling remained incoherent. It still fails the quality gate.
- The 6,000-step checkpoint and result are preserved as
  `checkpoint-steps-6000.pt` and `train-result-steps-6000.json`. A further
  warm-start to 9,000 steps lowered BPC to `1.442` and perplexity to `68.198`;
  checkpoint SHA-256 is
  `3033f670eaf98e3cce423d215503994167716c6bf44541b524cf1d2532f99e4a`.
  Greedy outputs still repeated or terminated immediately (repeated-trigram
  fractions `0.872`–`0.989` across five nonempty prompts). It fails the quality
  gate.
- A further warm-start to 12,000 steps lowered holdout BPC to `1.392` and
  perplexity to `58.821`; checkpoint SHA-256 is
  `82f55fb4ec0ae10d95836fe6ea9d8f0cb41fc6c7565ee352f65b4d6afea98b45`.
  The candidate loaded strictly into the same model state layout as the serving
  `TinyLM`, but greedy generation failed all six Nepali prompts: outputs looped
  on short phrases, question marks, or repeated numbers. The 12,000-step
  checkpoint and metrics are preserved as `checkpoint-steps-12000.pt` and
  `train-result-steps-12000.json`. Lower holdout loss has not resolved
  generation collapse; this candidate is not suitable for promotion.

The trainer accepts `HAMI_MODEL_STEPS` and
`HAMI_MODEL_INIT_CHECKPOINT`. Warm-starts validate architecture compatibility,
append to the training log, and start a fresh AdamW optimizer; optimizer state
is not restored, so this is not an exact training resume.

The first three runs used the earlier corpus sample. That corpus contains
11,436 training and 585 holdout records from FineWeb-2 Nepali text, the Hami
origin/system-map/architecture documents, and selected public Hami pages. Its
tokenizer was fit on training records only and round-trips Nepali/English.

A first shard-stratified corpus was built at `next-run-stratified` with 11,428
training and 593 holdout records. The provenance-complete rebuild at
`next-run-stratified-v2` has also been built and verified: the 12,000 FineWeb
records span two Parquet shards and 1,500 row groups, and each retains its
source ID, URL, shard, row group, and row index. Its train/holdout text hashes
are disjoint. Hami documents and public pages contribute 21 more records.
Some chunks from the same Hami document/page appear on both sides, so v2's Hami
holdout is not source-independent. The builder now keeps all chunks from each
Hami source together. The v3 corpus has 11,433 training and 588 holdout records;
its FineWeb provenance is complete, Hami sources are separated, and the text
hashes are disjoint. The tokenizer is fit on training records only; only 4 of
191,003 holdout tokens are unknown.

An expanded corpus at `next-run-expanded-50k` contains 50,000 FineWeb records
across 4,889 row groups, plus 21 Hami records. It has 48,989 training and 1,032
holdout records, complete source provenance, source-separated Hami pages,
disjoint text hashes, and 3 unknown tokens among 350,489 holdout tokens. The
3,000-, 6,000-, 9,000-, and 12,000-step results are preserved. More raw-text
data and training lowered loss but have not passed the generation quality gate.
No candidate has been promoted; the live server remains on its original
checkpoint.

A character-level scan of the expanded training split found that the 48,970
FineWeb records contain 70.6 million characters, of which 83.55% are in
U+0900–U+097F and 0.33% are ASCII Latin letters. The 19 Hami records contain
52,110 characters total and are predominantly ASCII Latin (73.80%–79.50% by
source). This confirms a Nepali-heavy raw-text corpus, but very little
Hami-authored material; these figures alone do not identify why generation
collapses.

The separate `hami-nepali-sft` workspace contains Qwen-targeted adapters and
instruction datasets, but the inspected records have no source, citation, or
license metadata. They were not used to train these Hami-owned checkpoints;
their provenance must be established before considering them.

Do not treat any pilot output—identity, fluency, or factual answers—as reliable.
No training candidate has passed the quality gate, and the served checkpoint
must remain unchanged.

The initialized run's result file now also records its holdout character count,
BPC, tokenizer type, and tokenizer SHA-256. The next corpus and model
experiments remain isolated and do not overwrite any trained run.

- The documented gateway route at `127.0.0.1:11435/api/hami-llm/status`
  returned 401 without an `X-Hami-Key`; authentication is active, but this
  unauthenticated check does not establish upstream or public-project traffic.
- No Vercel deployment or 3000-peer test has been performed.
- The previous `43.2` perplexity claim is not comparable to the current
  checkpoint: it came from a different tokenizer/run and should not be used as
  a promotion baseline.
