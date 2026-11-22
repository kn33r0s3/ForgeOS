# hami-model — Hami's own model

The mandate (Niroj, 19 Nov 2026 ~17:28–17:29):
1. Hami's own model powers the Hami assistant.
2. No GPT-4, gpt-oss, ChatGPT, or external GPT fallback.
3. No pretending a borrowed model is Hami because of a system prompt.
4. One shared inference path for Meet Hami, Hami chat, the terminal and the embedded widget.
5. Model identity comes from the actual loaded model and serving process.
6. If Hami's model is unavailable, report unavailable. Never silently switch to another AI.
7. Keep developing and evaluating Hami's own model until it becomes capable of carrying the workload.

The serving model is pinned under 'How it is served' below (MLX + clean adapter on 127.0.0.1:11436). The standalone `hami-model-server.py` process is the from-scratch pilot experiment server; it loads the Hami pilot checkpoint and tokenizer, and does not by itself prove that every repository path or deployment uses that server.

## What hami-model is today

The existing from-scratch pilot is a TinyLM with 13,916,160 parameters (6 layers,
`d_model=384`, 8 heads, context 512, tied embeddings). Its currently served
tokenizer uses `Whitespace` pre-tokenization without a decoder; it is not the
new tokenizer described below.

The pilot is experimental and not capable enough to claim as a useful Nepali
assistant. Do not treat its identity prompts, fluency, or factual answers as
reliable. The pilot is NOT what answers chat — the serving model is the MLX
adapter pinned under 'How it is served' below.

## How it is served — ONE identity line (pinned 21 Nov 2026)

Chat is answered by exactly one serving path:

  backend `app/api/hami_chat.py`
  → `scripts/hami_model_gateway.py` (127.0.0.1:11435, `X-Hami-Key` auth,
    one generation at a time)
  → MLX server (127.0.0.1:11436)
  → base `mlx-community/Qwen3-4B-4bit`
    + adapter `qwen3-4b-nepali-sft-clean-5000`
      adapter sha256
      `a309e2290dd5cf098564fdb2557b3a3626dca9013063b52a2b345ea844001385`
      (verified by re-hashing `adapters.safetensors`, 21 Nov 2026; the same
      sha is recorded as the cycle-1 baseline adapter sha in
      `hami-nepali-sft/upgrade-history.jsonl`)
      Re-verified independently by the Muse self-watch, 22 Nov 2026 10:24
      +0545: sha256 of the on-disk file
      `.../hami-nepali-sft/adapters/qwen3-4b-nepali-sft-clean-5000/adapters.safetensors`
      (29,384,266 bytes) computed via the file channel (Full Disk Access)
      + `sha256sum` = `a309e2290dd5cf098564fdb2557b3a3626dca9013063b52a2b345ea844001385`,
      exact match. See `/tmp/hami-t5-sha-verified.md`. Note: probe 184's 21 Nov
      `shasum` failed with TCC "Operation not permitted" from its shell —
      the adapter file itself was never the problem; the T5 sha leg PASSES.
      recipe `sft-clean-retrain-config.yaml`
      (LoRA rank 8, scale 20, 16 layers, 2,500 iters, lr 1e-05,
      `mask_prompt: true`, seed 23)

The gateway forwards the full message list — its own Hami system prompt,
the chat history, and the latest user message — to the MLX server, which
applies the adapter. The gateway answers identity questions itself with a
hard-coded line (by design: the model does not self-identify; probe T5).
If the MLX server is down (it is stopped while a training cycle runs), the
gateway returns `upstream_unavailable` and chat reports "Hami is
unavailable". Never any other model, never a silent fallback.

The torch pilot below is NOT in this path. It is a separate experiment
server; nothing in chat calls it. Do not cite the pilot as the serving
model, and do not cite this MLX path as the from-scratch model: the
from-scratch pilot takes over only when it beats the adapter on the same
eval (see the replacement note in the repo memory).

- `scripts/hami-model-server.py` — the pilot experiment server, small torch
  server, 127.0.0.1:11437. Loads `checkpoint.pt` + `tokenizer.json` from the
  dir in `scripts/hami-model.txt`. `GET /status` reports the ACTUAL loaded
  model (name, checkpoint sha256, params, steps, holdout perplexity).
  `POST /api/chat` generates greedily. If the model files are missing it
  refuses to start — callers then report "Hami is unavailable", never fall
  back. Experiment-only: not in the chat path above.
- `scripts/hami-model-server.sh` — pilot launcher (Mac venv python with torch + tokenizers).
- `scripts/com.hami.model-server.plist` — pilot launchd, RunAtLoad + KeepAlive.
- This path is not yet verified end-to-end for every app, embedded widget, or
  public deployment. Do not claim that all Hami projects currently use it.

## Local status

- Serving path, observed live 21 Nov 2026 ~02:10 +0545: the gateway is up on
  `127.0.0.1:11435` (PID 8449, since 20 Nov 13:36 +0545). The MLX server on
  `127.0.0.1:11436` was DOWN at that moment because cycle-2 training was
  running (`mlx_lm lora`, PID 52394, since 21 Nov 00:45 +0545) and the
  upgrade loop stops the server while training; chat therefore reports
  "Hami is unavailable" until the cycle restores it. That is by design, not
  an outage of the gateway.
- The serving adapter is `qwen3-4b-nepali-sft-clean-5000`, sha256
  `a309e2290dd5cf098564fdb2557b3a3626dca9013063b52a2b345ea844001385`
  (see the pinned identity line above). No `active-adapter.json` exists, so
  no promotion through `continuous_upgrade.py` has ever been recorded; the
  clean adapter is the fallback default in that script. Two v2 candidates
  exist on disk (`...-v2-20261120T182626Z-fa54f17ee9`,
  `...-v2-20261120T184939Z-e1a55a10dc`) and neither has been promoted.
- The pilot server at `127.0.0.1:11437` returned HTTP 200 with `loaded=true`
  (PID 81384, since 20 Nov 19:00 +0545) — but it is the experiment pilot,
  not the chat path. Its loaded checkpoint SHA-256:
  `40970731ffe1f0cc6e0221c69b37ac7ae9059120b9b58b3486d2abcfa4b1c50f`.
- The pilot reports 3,000 training steps and holdout perplexity `1302.5124`;
  this result does not pass a quality gate.
- This pilot checkpoint remains unchanged. It is separate from all experimental
  checkpoints; none has been promoted or loaded into the pilot server.
- ForgeOS now defaults both `AI_PROVIDER` and `COGNITIVE_PROVIDER` to
  `hami-model`, with mock fallback disabled. This selects the guarded local
  gateway path; it does not prove that the local gateway, tunnel, or public
  projects are currently reachable.
- The backend chat route forwards the full conversation (system prompt +
  history + latest message) to the gateway, and the gateway forwards the
  full message list to the MLX server. The earlier claim that the gateway
  sends only the latest user message was wrong; the gateway code builds one
  message list from all supplied turns.
- The raw-text pilot is not instruction-tuned, so system prompts and history do
  not condition its response. (That applies to the pilot only, not to the
  MLX adapter path, which is instruction-tuned.)

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

## Source-grounded QA benchmark (evaluation only)

Added `evaluate-nepali-qa.py` to run a local JSON QA dataset against a selected
checkpoint. It strict-loads the model, builds a Nepali context/question prompt,
greedily generates up to 32 tokens, and reports normalized exact match and
whitespace-token F1 without printing or saving dataset examples.

The evaluation-only benchmark was `Yunika/Nepali-QA`, pinned to revision
`2c1c3376886d35f89e4908da441e55655044a3ee`. Its card describes 266
human-curated QA pairs under CC BY-SA 4.0, derived from Belebele/FLORES-200,
and cites [the 2025 Nepali extractive QA
paper](https://doi.org/10.3126/kjse.v9i1.78368). See the
[pinned dataset card](https://huggingface.co/datasets/Yunika/Nepali-QA/tree/2c1c3376886d35f89e4908da441e55655044a3ee).
FLORES-200's [dataset card](https://huggingface.co/datasets/facebook/flores)
restricts its data and derivatives to evaluation, forbids training use, and
restricts redistribution; accordingly, this benchmark was used only for local
inference, never training, and its temporary downloaded file was removed. It
is not included in this repository or any training split.

All 266 records were valid across 101 distinct contexts. No normalized context
matched or appeared as a substring in the expanded training records; this
checks exact overlap only, not paraphrase or semantic contamination. No context
needed truncation to fit the 512-token model window. On this extractive QA task,
the 12,000-step candidate scored exact match `0.0000` and token F1 `0.0103`;
the currently served 3,000-step checkpoint scored exact match `0.0000` and
token F1 `0.0085`; they returned non-empty answers for 258 and 265 records,
respectively. The small F1 difference is not useful QA performance:
neither checkpoint answers these questions reliably, and this benchmark does
not cover broader Nepal-specific conversational quality.

The separate `hami-nepali-sft` workspace contains Qwen-targeted adapters and
instruction datasets, but the inspected records have no source, citation, or
license metadata. They were not used to train these Hami-owned checkpoints;
their provenance must be established before considering them.

Additional public SFT candidates reviewed at pinned revisions were also not
admitted to training:

- [Nepali Finance Instruction Dataset](https://huggingface.co/datasets/sabin1234/Nepali_SCRAP_Finance_Instruction_Dataset/tree/3f25c337ed20e5fd6c6f4684e56441b35ac25239)
  has 23,855 rows but a mixed, dataset-level `other` license, 2,257 duplicate
  rows, 51 rows without a license field, 8,442 rows naming Gemini as answer
  generator, and no generator recorded for many other rows.
- [Nepali instruction Alpaca dataset](https://huggingface.co/datasets/chhatramani/nepali_instruction_dataset_alpaca/tree/f60bad7d4ec7fe64b4651ebdbab76920514e6dc7)
  declares CC BY 4.0 for 28,910 rows, but its card does not provide source or
  answer-generation provenance.
- [Nepali legal SFT dataset](https://huggingface.co/datasets/Somtharu181coder/Legal_domain_ocr_extracted_Nepali_sft_dataset/tree/8b2b3d8cab384e641c47bb7d5f2317bb2157120d)
  declares CC BY 4.0 and traces 31 rows to one Law Commission order, but labels
  the answers synthetic and warns about OCR uncertainty. It is not a broad
  Nepali instruction corpus.

No new instruction data was added to training. A candidate for the next SFT
stage must have verifiable per-record source and license information, plus
answer-generation provenance; licensed human/source text is preferable to
answers generated by an unidentified external model.

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
