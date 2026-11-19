#!/usr/bin/env python3
"""hami-model server — Hami's own model, on this Mac only.

Serves the from-scratch pilot (own-base/train-model.py: TinyLM, ~14M params,
own 8k BPE tokenizer, trained on Hami's real Nepali text only).
# No borrowed model or external fallback.
If the model files are missing the server refuses to start — callers then
report "Hami is unavailable", they never switch to another AI.

Model dir: read from scripts/hami-model.txt (one line, the dir holding
checkpoint.pt + tokenizer.json). Listens on 127.0.0.1:11437.

Endpoints:
  GET  /status    identity from the ACTUAL loaded model (name, checkpoint
                   sha256, params, steps, holdout perplexity).
  POST /api/chat  {"message": "...", "max_tokens": 128} -> {"reply": ...,
                   "model": "hami-model", ...}. Greedy generation.
"""
import hashlib
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import torch
import torch.nn as nn
from tokenizers import Tokenizer

HERE = os.path.dirname(os.path.abspath(__file__))
STARTED = time.time()


def model_dir():
    with open(os.path.join(HERE, "hami-model.txt"), encoding="utf-8") as f:
        return f.read().strip()


class Block(nn.Module):
    def __init__(self, d, heads, d_ff):
        super().__init__()
        self.ln1 = nn.LayerNorm(d)
        self.attn = nn.MultiheadAttention(d, heads, batch_first=True)
        self.ln2 = nn.LayerNorm(d)
        self.mlp = nn.Sequential(nn.Linear(d, d_ff), nn.GELU(), nn.Linear(d_ff, d))

    def forward(self, x, mask):
        a, _ = self.attn(self.ln1(x), self.ln1(x), self.ln1(x), attn_mask=mask, need_weights=False)
        x = x + a
        return x + self.mlp(self.ln2(x))


class TinyLM(nn.Module):
    def __init__(self, vocab, d=384, layers=6, heads=8, d_ff=1536, ctx=512):
        super().__init__()
        self.ctx = ctx
        self.tok_emb = nn.Embedding(vocab, d)
        self.pos_emb = nn.Embedding(ctx, d)
        self.blocks = nn.ModuleList([Block(d, heads, d_ff) for _ in range(layers)])
        self.ln = nn.LayerNorm(d)
        self.head = nn.Linear(d, vocab, bias=False)
        self.head.weight = self.tok_emb.weight

    def forward(self, idx):
        b, t = idx.shape
        pos = torch.arange(t, device=idx.device)
        x = self.tok_emb(idx) + self.pos_emb(pos)[None]
        mask = torch.triu(torch.ones(t, t, device=idx.device, dtype=torch.bool), diagonal=1)
        for blk in self.blocks:
            x = blk(x, mask)
        return self.head(self.ln(x))

    def n_params(self):
        return sum(p.numel() for p in self.parameters())


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_model():
    mdir = model_dir()
    cpt = os.path.join(mdir, "checkpoint.pt")
    tokp = os.path.join(mdir, "tokenizer.json")
    res = os.path.join(mdir, "train-result.json")
    for p in (cpt, tokp):
        if not os.path.exists(p):
            print(f"hami-model: missing {p} — refusing to start", file=sys.stderr)
            sys.exit(1)
    tok = Tokenizer.from_file(tokp)
    ck = torch.load(cpt, map_location="cpu", weights_only=True)
    cfg = ck["config"]
    model = TinyLM(cfg["vocab"], d=cfg["d"], layers=cfg["layers"],
                   heads=cfg["heads"], d_ff=cfg["d_ff"], ctx=cfg["ctx"])
    model.load_state_dict(ck["state"])
    model.eval()
    info = {
        "model": "hami-model",
        "checkpoint_sha256": sha256_file(cpt),
        "params": model.n_params(),
        "vocab": cfg["vocab"],
        "layers": cfg["layers"],
        "d_model": cfg["d"],
        "ctx": cfg["ctx"],
        "steps": cfg.get("steps"),
        "train_tokens": None,
        "holdout_ppl": None,
    }
    if os.path.exists(res):
        with open(res, encoding="utf-8") as f:
            r = json.load(f)
        info["train_tokens"] = r.get("train_tokens")
        info["holdout_ppl"] = r.get("holdout_ppl")
    return tok, model, info


TOK, MODEL, INFO = load_model()
BOS = TOK.token_to_id("[BOS]")
EOS = TOK.token_to_id("[EOS]")
torch.set_num_threads(4)


def generate(prompt, max_tokens=128):
    ids = [BOS] + TOK.encode(prompt).ids
    with torch.no_grad():
        for _ in range(max_tokens):
            ctx = torch.tensor([ids[-MODEL.ctx:]])
            nxt = MODEL(ctx)[0, -1].argmax().item()
            ids.append(nxt)
            if nxt == EOS:
                break
    return TOK.decode(ids[1:])


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path in ("/status", "/"):
            self._send(200, {**INFO, "loaded": True,
                             "uptime_s": round(time.time() - STARTED, 1)})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/chat":
            self._send(404, {"error": "not found"})
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n).decode("utf-8")) if n else {}
        except Exception:
            self._send(400, {"error": "bad json"})
            return
        msg = (data.get("message") or "").strip()
        if not msg:
            self._send(400, {"error": "empty message"})
            return
        mt = data.get("max_tokens", 128)
        try:
            mt = max(1, min(int(mt), 256))
        except Exception:
            mt = 128
        reply = generate(msg, mt)
        self._send(200, {"reply": reply, "model": "hami-model",
                         "checkpoint_sha256": INFO["checkpoint_sha256"],
                         "params": INFO["params"]})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", 11437), Handler)
    print(f"hami-model up on 127.0.0.1:11437 params={INFO['params']} "
          f"ppl={INFO['holdout_ppl']} sha={INFO['checkpoint_sha256'][:12]}",
          flush=True)
    srv.serve_forever()
