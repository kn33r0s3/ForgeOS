#!/usr/bin/env python3
"""
dimag.py — DIMAG gate-graph lead ranker (NumPy, hand-written backprop).
Commands:  gradcheck | trial | final [seeds...] | summary | sweep | run_all
"""
import glob
import json
import os
import sys
import time
import hashlib
from pathlib import Path

import numpy as np

G, L = 8, 5
GDIM, HDIM, LDIM = 24, 10, 18
R = 20

RESULTS_DIR = os.environ.get("DIMAG_RESULTS_DIR", "results")


def outdir(path=None):
    d = path or RESULTS_DIR
    os.makedirs(d, exist_ok=True)
    return d


# ---------------------------------------------------------------- graphs
def make_graph(rng, n_edges=12, n_rel=10):
    """Create a directed graph and explicitly typed reverse-direction edges."""
    max_edges = G * (G - 1)
    if not isinstance(n_edges, int) or not 0 <= n_edges <= max_edges:
        raise ValueError(f"n_edges must be an integer in [0, {max_edges}]")
    if not isinstance(n_rel, int) or not 1 <= n_rel <= 10:
        raise ValueError("n_rel must be an integer in [1, 10]")
    if n_edges == 0:
        empty = np.array([], dtype=np.int64)
        return empty.copy(), empty.copy(), empty.copy()
    edges = set()
    while len(edges) < n_edges:
        src, dst = rng.integers(0, G, 2)
        if src != dst:
            edges.add((int(src), int(dst)))
    edges = sorted(edges)
    src = np.asarray([e[0] for e in edges], dtype=np.int64)
    dst = np.asarray([e[1] for e in edges], dtype=np.int64)
    typ = rng.integers(0, n_rel, len(edges), dtype=np.int64)
    return (np.concatenate([src, dst]), np.concatenate([dst, src]),
            np.concatenate([typ, typ + 10]))


EMPTY_GRAPH = (np.array([], dtype=int), np.array([], dtype=int), np.array([], dtype=int))


# ---------------------------------------------------------------- teacher
class Teacher:
    def __init__(self, seed=1234, scale=None):
        r = np.random.default_rng(seed)
        self.w_rel = r.uniform(-1, 1, R)
        self.zone = r.uniform(0, 1.5, 12)
        self.k = np.ones(12) if scale is None else np.asarray(scale)

    def graph_ctx(self, Xg, graph):
        src, dst, typ = graph
        n = Xg.shape[0]
        if len(src) == 0:
            return np.zeros((n, G))
        sig = Xg[..., 2] + 0.5 * Xg[..., 1]
        msg = sig[:, src] * self.w_rel[typ][None, :]
        deg = np.bincount(dst, minlength=G).clip(min=1)
        S = np.zeros((G, len(src)))
        S[dst, np.arange(len(src))] = 1.0 / deg[dst]
        return msg @ S.T

    def scores(self, Xg, Xh, Xl, graph):
        k = self.k
        g = lambda i: Xl[..., i]
        unc = Xg[..., 1][..., None]
        hV, hS, hC, hA = (Xh[..., i][..., None] for i in (6, 3, 8, 2))
        zs = self.zone[Xg[..., 4:16].argmax(-1)][..., None]
        ctx = self.graph_ctx(Xg, graph)[..., None]
        return (k[0] * g(0) + k[1] * 0.5 * g(15) + k[2] * 0.8 * g(6) * (0.5 + unc)
                + k[3] * g(1) * (0.3 + 2.0 * hV)
                - k[4] * (g(4) + g(7) + 0.5 * g(13)) * (0.2 + 1.5 * hS)
                - k[5] * g(5) * (1 - 0.5 * g(2))
                - k[6] * g(17) * (0.3 + 1.5 * hC)
                + k[7] * (0.5 * g(11) + 0.3 * g(12) + 0.2 * g(16))
                - k[8] * g(14) * zs
                + k[9] * 1.5 * g(8) * ctx
                + k[10] * g(3) * (0.2 + 1.0 * hA)
                + k[11] * 0.3 * g(9) * unc)


def gen(n, rng, graph, teacher, shift=False):
    if shift:
        sit = rng.beta(5, 2, (n, G, 4))
        Xh = (rng.random((n, G, HDIM)) < 0.5) * rng.uniform(0.7, 1.0, (n, G, HDIM))
        Xl = rng.beta(2, 5, (n, G, L, LDIM))
    else:
        sit = rng.random((n, G, 4))
        Xh = rng.random((n, G, HDIM))
        Xl = rng.random((n, G, L, LDIM))
    zoh = np.eye(12)[rng.integers(0, 12, (n, G))]
    roh = np.eye(4)[rng.choice(4, (n, G), p=[.60, .15, .17, .08])]
    eoh = np.eye(4)[rng.choice(4, (n, G), p=[.20, .40, .30, .10])]
    Xg = np.concatenate([sit, zoh, roh, eoh], -1).astype(np.float32)
    Xl[..., 10] = rng.random((n, G, L)) < 0.5
    Xh, Xl = Xh.astype(np.float32), Xl.astype(np.float32)
    approved = rng.random((n, G, 1)) < 0.4
    allowed = ~((Xl[..., 10] > 0.5) & ~approved) & ~(Xg[..., 19][..., None] > 0.5)
    return relabel(dict(Xg=Xg, Xh=Xh, Xl=Xl, allowed=allowed), teacher, graph)


def relabel(d, teacher, graph):
    s = teacher.scores(d['Xg'], d['Xh'], d['Xl'], graph)
    sm = np.where(d['allowed'], s, -np.inf)
    target = np.where(d['allowed'].any(-1), sm.argmax(-1), -1)
    out = dict(d)
    out['target'] = target
    return out


def sl(d, a, b):
    return {k: v[a:b] for k, v in d.items()}


def uniform_baseline(d):
    allowed, target, lab = validate_targets(d['allowed'], d['target'])
    if not lab.any():
        return None
    return float((1.0 / allowed.sum(-1)[lab]).mean())


def heuristic_acc(d, kind):
    Xl = d['Xl']
    if kind == 'benefit':
        scores = Xl[..., 0]
    elif kind == 'sum':
        scores = Xl[..., 0] + Xl[..., 15] + Xl[..., 6] - Xl[..., 4] - Xl[..., 7] - Xl[..., 5]
    else:
        raise ValueError("kind must be 'benefit' or 'sum'")
    pred = select_allowed(scores, d['allowed'])
    _, target, lab = validate_targets(d['allowed'], d['target'])
    if not lab.any():
        return None
    return float((pred[lab] == target[lab]).mean())


def mm_t(x, y):
    return x.reshape(-1, x.shape[-1]).T @ y.reshape(-1, y.shape[-1])


def validate_graph(graph):
    """Fail closed on malformed graph arrays; NumPy negative indices must not wrap."""
    if not isinstance(graph, (tuple, list)) or len(graph) != 3:
        raise ValueError("graph must be a (src, dst, relation_type) triple")
    src, dst, typ = (np.asarray(v) for v in graph)
    for name, arr in (("src", src), ("dst", dst), ("relation_type", typ)):
        if arr.ndim != 1 or not np.issubdtype(arr.dtype, np.integer):
            raise TypeError(f"graph {name} must be a one-dimensional integer array")
    if not (len(src) == len(dst) == len(typ)):
        raise ValueError("graph src, dst, and relation_type arrays must have equal lengths")
    if len(src):
        if np.any(src < 0) or np.any(src >= G) or np.any(dst < 0) or np.any(dst >= G):
            raise ValueError(f"graph node indices must be in [0, {G})")
        if np.any(typ < 0) or np.any(typ >= R):
            raise ValueError(f"graph relation types must be in [0, {R})")
    return src.astype(np.int64, copy=False), dst.astype(np.int64, copy=False), typ.astype(np.int64, copy=False)


def validate_features(Xg, Xh, Xl, dtype=None):
    """Validate the fixed DIMAG feature contract before numerical operations."""
    arrays = (np.asarray(Xg), np.asarray(Xh), np.asarray(Xl))
    Xg, Xh, Xl = arrays
    if Xg.ndim != 3 or Xg.shape[1:] != (G, GDIM):
        raise ValueError(f"Xg must have shape [B, {G}, {GDIM}]")
    batch = Xg.shape[0]
    if batch < 1:
        raise ValueError("feature batch must contain at least one item")
    if Xh.shape != (batch, G, HDIM):
        raise ValueError(f"Xh must have shape [B, {G}, {HDIM}]")
    if Xl.shape != (batch, G, L, LDIM):
        raise ValueError(f"Xl must have shape [B, {G}, {L}, {LDIM}]")
    for name, arr in (("Xg", Xg), ("Xh", Xh), ("Xl", Xl)):
        if not np.issubdtype(arr.dtype, np.number):
            raise TypeError(f"{name} must be numeric")
        if not np.isfinite(arr).all():
            raise ValueError(f"{name} contains NaN or infinite values")
    if dtype is not None:
        Xg, Xh, Xl = (arr.astype(dtype, copy=False) for arr in (Xg, Xh, Xl))
        if not all(np.isfinite(arr).all() for arr in (Xg, Xh, Xl)):
            raise ValueError("feature values overflowed during model dtype conversion")
    return Xg, Xh, Xl


def validate_targets(allowed, target):
    """Targets are -1 (unlabelled/no eligible action) or an allowed lead index."""
    allowed = np.asarray(allowed)
    target = np.asarray(target)
    if allowed.dtype != np.bool_:
        raise TypeError("allowed must be a boolean policy mask")
    if allowed.ndim != 3 or allowed.shape[1:] != (G, L):
        raise ValueError(f"allowed must have shape [B, {G}, {L}]")
    if target.shape != allowed.shape[:2] or not np.issubdtype(target.dtype, np.integer):
        raise TypeError("target must be an integer array with shape [B, G]")
    if np.any(target < -1) or np.any(target >= L):
        raise ValueError(f"target entries must be -1 or an index in [0, {L})")
    has = target >= 0
    if np.any(has & ~np.take_along_axis(allowed, np.maximum(target, 0)[..., None], axis=-1)[..., 0]):
        raise ValueError("target points to a disallowed lead; reject rather than train on it")
    no_candidates = ~allowed.any(-1)
    if np.any(no_candidates & has):
        raise ValueError("a gate with no allowed candidates cannot have a target")
    return allowed, target.astype(np.int64, copy=False), has


def select_allowed(scores, allowed):
    """Hard-mask selector. Returns -1 when no candidate is permitted."""
    scores = np.asarray(scores)
    allowed = np.asarray(allowed)
    if scores.ndim != 3 or scores.shape[1:] != (G, L):
        raise ValueError(f"scores must have shape [B, {G}, {L}]")
    if allowed.shape != scores.shape or allowed.dtype != np.bool_:
        raise ValueError("allowed must be a boolean mask matching scores")
    if not np.isfinite(scores[allowed]).all():
        raise ValueError("scores for permitted candidates must be finite")
    masked = np.where(allowed, scores, -np.inf)
    return np.where(allowed.any(-1), masked.argmax(-1), -1).astype(np.int64)


# ---------------------------------------------------------------- model
class Net:
    def __init__(self, rng, dtype=np.float32, D=64, num_steps=2, act='relu', wd=0.0):
        if not isinstance(D, int) or D < 2:
            raise ValueError("D must be an integer >= 2")
        if not isinstance(num_steps, int) or num_steps < 0:
            raise ValueError("num_steps must be a non-negative integer")
        if act not in {"relu", "leaky", "silu"}:
            raise ValueError("act must be relu, leaky, or silu")
        if not np.isfinite(wd) or wd < 0:
            raise ValueError("wd must be finite and non-negative")
        dtype = np.dtype(dtype)
        if dtype.kind != "f":
            raise TypeError("model dtype must be floating point")
        self.D = D
        self.T = num_steps
        self.act = act
        self.wd = float(wd)
        gl = lambda i, o: (rng.standard_normal((i, o)) * np.sqrt(2.0 / (i + o))).astype(dtype)
        z = lambda *shape: np.zeros(shape, dtype=dtype)
        P = {'Wg': gl(GDIM, D), 'bg': z(D), 'Wh': gl(HDIM, D), 'bh': z(D)}
        for t in range(self.T):
            P[f'Wm{t}'] = gl(D, D)
            P[f'rel{t}'] = (1.0 + 0.1 * rng.standard_normal((R, D))).astype(dtype)
            P[f'Ws{t}'] = gl(D, D) * 0.5
            P[f'bu{t}'] = z(D)
        P.update(Wgam=gl(D, D) * 0.1, bgam=z(D), Wbet=gl(D, D) * 0.1, bbet=z(D),
                 Wl=gl(LDIM, D), bl=z(D), Wa=gl(D, D), Wb=gl(D, D),
                 Wc=gl(D, D), Wd=gl(D, D), bs1=z(D),
                 w2=(rng.standard_normal(D) * np.sqrt(1.0 / D)).astype(dtype), b2=z(1))
        self.P = P


    # ---- activation + derivative ----
    def _act(self, x):
        if self.act == 'relu':
            return np.maximum(x, 0)
        if self.act == 'leaky':
            return np.where(x > 0, x, 0.01 * x).astype(x.dtype)
        if self.act == 'silu':
            s = 1.0 / (1.0 + np.exp(-np.clip(x, -50, 50)))
            return (x * s).astype(x.dtype)
        raise ValueError(self.act)

    def _act_grad(self, pre):
        if self.act == 'relu':
            return (pre > 0).astype(pre.dtype)
        if self.act == 'leaky':
            return np.where(pre > 0, 1.0, 0.01).astype(pre.dtype)
        if self.act == 'silu':
            s = 1.0 / (1.0 + np.exp(-np.clip(pre, -50, 50)))
            return (s * (1.0 + pre * (1.0 - s))).astype(pre.dtype)
        raise ValueError(self.act)

    def forward(self, Xg, Xh, Xl, graph):
        P, dt = self.P, self.P['Wg'].dtype
        Xg, Xh, Xl = validate_features(Xg, Xh, Xl, dtype=dt)
        src, dst, typ = validate_graph(graph)
        B = Xg.shape[0]
        E = len(src)
        C = {}
        C['g_pre0'] = Xg @ P['Wg'] + P['bg']
        g = self._act(C['g_pre0'])
        C['c_pre'] = Xh @ P['Wh'] + P['bh']
        c = self._act(C['c_pre'])
        if E:
            deg = np.bincount(dst, minlength=G).clip(min=1).astype(dt)
            Sinv = np.zeros((G, E), dt)
            Sinv[dst, np.arange(E)] = 1.0 / deg[dst]
            Ssrc = np.zeros((G, E), dt)
            Ssrc[src, np.arange(E)] = 1.0
            C['Sinv'], C['Ssrc'] = Sinv, Ssrc
        steps = []
        for t in range(self.T):
            gprev = g
            M = gprev @ P[f'Wm{t}']
            if E:
                msg = M[:, src, :] * P[f'rel{t}'][typ][None]
                agg = np.matmul(Sinv, msg)
            else:
                agg = np.zeros_like(M)
            pre = agg + gprev @ P[f'Ws{t}'] + P[f'bu{t}']
            g = gprev + self._act(pre)
            steps.append((gprev, M, pre))
        gam = c @ P['Wgam'] + P['bgam']
        bet = c @ P['Wbet'] + P['bbet']
        gf = g * (1 + gam) + bet
        l_pre = Xl @ P['Wl'] + P['bl']
        l = self._act(l_pre)
        a, helper_bias = gf @ P['Wa'], c @ P['Wd']
        interaction = gf[:, :, None, :] * l
        z = a[:, :, None, :] + l @ P['Wb'] + interaction @ P['Wc'] + helper_bias[:, :, None, :] + P['bs1']
        h = self._act(z)
        scores = h @ P['w2'] + P['b2'][0]
        if not np.isfinite(scores).all():
            raise FloatingPointError("forward pass produced non-finite scores")
        C.update(steps=steps, c=c, g=g, gam=gam, gf=gf, l_pre=l_pre, l=l,
                 p=interaction, z=z, h=h, E=E, src=src, dst=dst, typ=typ,
                 Xg=Xg, Xh=Xh, Xl=Xl)
        return scores, C

    def loss_and_grads(self, Xg, Xh, Xl, graph, allowed, target):
        allowed, target, has = validate_targets(allowed, target)
        if allowed.shape[0] != np.asarray(Xg).shape[0]:
            raise ValueError("allowed/target batch size must match features")
        P = self.P
        s, C = self.forward(Xg, Xh, Xl, graph)
        if allowed.shape != s.shape:
            raise ValueError("allowed mask must match model score shape")
        dt = s.dtype
        # No labels is not a training example. Fail explicitly so an external
        # caller cannot pass zero gradients into an optimizer with stale momentum.
        if not has.any():
            raise ValueError("batch has no labelled gates; skip it before optimizer.step()")
        sm = np.where(allowed, s, -1e9)
        e = np.exp(sm - sm.max(-1, keepdims=True)) * allowed
        p_soft = e / np.maximum(e.sum(-1, keepdims=True), 1e-30)
        N = int(has.sum())
        ib, ig = np.where(has)
        tg = target[ib, ig]
        loss = float(-np.log(np.maximum(p_soft[ib, ig, tg], 1e-30)).sum() / N)


        # weight decay (L2)
        WD_TARGETS = ('Wg', 'Wh', 'Wl', 'Wa', 'Wb', 'Wc', 'Wd', 'w2')
        if self.wd > 0:
            loss += 0.5 * self.wd * sum(float((P[n] ** 2).sum()) for n in WD_TARGETS)
        ds = p_soft.copy()
        ds[ib, ig, tg] -= 1
        ds = (ds * has[..., None] / N * allowed).astype(dt)

        gr = {k: np.zeros_like(v) for k, v in P.items()}
        h, z, l, l_pre, pp, gf, c, g, gam = (
            C[k] for k in ('h', 'z', 'l', 'l_pre', 'p', 'gf', 'c', 'g', 'gam'))
        gr['w2'] = np.einsum('bgl,bgld->d', ds, h)
        gr['b2'] = np.array([ds.sum()], dtype=dt)
        dz = ds[..., None] * P['w2'] * self._act_grad(z)
        gr['bs1'] = dz.sum((0, 1, 2))
        da = dz.sum(2)
        gr['Wa'] = mm_t(gf, da)
        dgf = da @ P['Wa'].T
        gr['Wd'] = mm_t(c, da)
        dc = da @ P['Wd'].T
        gr['Wb'] = mm_t(l, dz)
        dl = dz @ P['Wb'].T
        gr['Wc'] = mm_t(pp, dz)
        dp = dz @ P['Wc'].T
        dgf = dgf + (dp * l).sum(2)
        dl = dl + dp * gf[:, :, None, :]
        dl_pre = dl * self._act_grad(l_pre)
        gr['Wl'] = mm_t(C['Xl'], dl_pre)
        gr['bl'] = dl_pre.sum((0, 1, 2))
        dg = dgf * (1 + gam)
        dgam, dbet = dgf * g, dgf
        gr['Wgam'] = mm_t(c, dgam); gr['bgam'] = dgam.sum((0, 1)); dc = dc + dgam @ P['Wgam'].T
        gr['Wbet'] = mm_t(c, dbet); gr['bbet'] = dbet.sum((0, 1)); dc = dc + dbet @ P['Wbet'].T
        dc_pre = dc * self._act_grad(C['c_pre'])
        gr['Wh'] = mm_t(C['Xh'], dc_pre); gr['bh'] = dc_pre.sum((0, 1))
        E, src, typ = C['E'], C['src'], C['typ']
        for t in reversed(range(self.T)):
            gprev, M, pre = C['steps'][t]
            dpre = dg * self._act_grad(pre)
            gr[f'bu{t}'] = dpre.sum((0, 1))
            gr[f'Ws{t}'] = mm_t(gprev, dpre)
            dgprev = dg + dpre @ P[f'Ws{t}'].T
            if E:
                relv = P[f'rel{t}'][typ]
                dmsg = np.matmul(C['Sinv'].T, dpre)
                dM = np.matmul(C['Ssrc'], dmsg * relv[None])
                np.add.at(gr[f'rel{t}'], typ, (dmsg * M[:, src, :]).sum(0))
            else:
                dM = np.zeros_like(M)
            gr[f'Wm{t}'] = mm_t(gprev, dM)
            dgprev = dgprev + dM @ P[f'Wm{t}'].T
            dg = dgprev
        dg_pre0 = dg * self._act_grad(C['g_pre0'])
        gr['Wg'] = mm_t(C['Xg'], dg_pre0); gr['bg'] = dg_pre0.sum((0, 1))
        if self.wd > 0:
            for n in WD_TARGETS:
                gr[n] = gr[n] + self.wd * P[n]
        return loss, gr


class Adam:
    """Adam optimizer with finite-value checks and atomic parameter updates."""
    def __init__(self, P):
        self.m = {k: np.zeros_like(v) for k, v in P.items()}
        self.v = {k: np.zeros_like(v) for k, v in P.items()}
        self.t = 0

    def step(self, P, grads, lr, b1=0.9, b2=0.999, eps=1e-8, clip=5.0):
        if not np.isfinite(lr) or lr <= 0:
            raise ValueError("learning rate must be finite and positive")
        if not 0 <= b1 < 1 or not 0 <= b2 < 1:
            raise ValueError("Adam beta values must be in [0, 1)")
        if not np.isfinite(eps) or eps <= 0 or not np.isfinite(clip) or clip <= 0:
            raise ValueError("eps and clip must be finite and positive")
        if set(grads) != set(P):
            raise ValueError("gradient keys must exactly match parameter keys")
        for k, param in P.items():
            grad = np.asarray(grads[k])
            if grad.shape != param.shape:
                raise ValueError(f"gradient shape mismatch for {k}")
            if not np.isfinite(param).all() or not np.isfinite(grad).all():
                raise FloatingPointError(f"non-finite parameter or gradient in {k}")
        gn2 = sum(float(np.sum(np.asarray(g, dtype=np.float64) ** 2)) for g in grads.values())
        gn = float(np.sqrt(gn2))
        if not np.isfinite(gn):
            raise FloatingPointError("gradient norm is not finite")
        scale = min(1.0, clip / (gn + 1e-12))
        next_t = self.t + 1
        new_m, new_v, new_p = {}, {}, {}
        for k, param in P.items():
            grad = grads[k] * scale
            m = b1 * self.m[k] + (1 - b1) * grad
            v = b2 * self.v[k] + (1 - b2) * grad * grad
            update = (lr * (m / (1 - b1 ** next_t)) /
                      (np.sqrt(v / (1 - b2 ** next_t)) + eps))
            candidate = param - update.astype(param.dtype)
            if not (np.isfinite(m).all() and np.isfinite(v).all() and np.isfinite(candidate).all()):
                raise FloatingPointError(f"Adam update would make {k} non-finite; no state was committed")
            new_m[k], new_v[k], new_p[k] = m, v, candidate
        # Commit only after every parameter update has passed validation.
        self.m, self.v, self.t = new_m, new_v, next_t
        for k in P:
            P[k][...] = new_p[k]



def train(net, d, graph, steps, bs, lr0, lr1, rng):
    """Train with shuffled complete batches, including the final partial batch.

    The step budget counts optimizer updates. Unlabelled batches are skipped.
    Training fails explicitly when the dataset contains no labelled examples.
    """
    n = len(d['Xg'])
    if n < 1:
        raise ValueError("training dataset must contain at least one example")
    if not isinstance(steps, int) or steps < 0:
        raise ValueError("steps must be a non-negative integer")
    if not isinstance(bs, int) or bs < 1:
        raise ValueError("batch size must be a positive integer")
    if not np.isfinite(lr0) or not np.isfinite(lr1) or lr0 <= 0 or lr1 <= 0:
        raise ValueError("learning rates must be finite and positive")
    allowed, target, has = validate_targets(d['allowed'], d['target'])
    if allowed.shape[0] != n or not has.any():
        raise ValueError("training data must contain at least one labelled gate")
    validate_features(d['Xg'], d['Xh'], d['Xl'], dtype=net.P['Wg'].dtype)
    validate_graph(graph)
    opt = Adam(net.P)
    step, hist, skipped = 0, [], 0
    epoch = 0
    while step < steps:
        epoch += 1
        perm = rng.permutation(n)
        epoch_updates = 0
        for i in range(0, n, bs):
            if step >= steps:
                break
            idx = perm[i:i + bs]
            batch_has = has[idx]
            if not batch_has.any():
                skipped += 1
                continue
            lr = lr1 + (lr0 - lr1) * 0.5 * (1 + np.cos(np.pi * step / max(steps, 1)))
            loss, gr = net.loss_and_grads(
                d['Xg'][idx], d['Xh'][idx], d['Xl'][idx], graph,
                d['allowed'][idx], d['target'][idx])
            if not np.isfinite(loss):
                raise FloatingPointError("training loss is non-finite")
            opt.step(net.P, gr, lr)
            step += 1
            epoch_updates += 1
            if step % 100 == 0 or step == steps:
                hist.append({"step": step, "loss_last_batch": float(loss),
                             "labeled_gates_last_batch": int(batch_has.sum()),
                             "epoch": epoch})
        if epoch_updates == 0:
            raise ValueError("no labelled batches available; refusing an empty training loop")
        if epoch > steps + 1:
            raise RuntimeError("training exceeded its bounded epoch guard")
    return {"history": hist, "optimizer_steps": step,
            "skipped_unlabelled_batches": skipped, "epochs": epoch}


def evaluate(net, d, graph, zero_helpers=False, no_graph=False):
    Xg, Xh, Xl = validate_features(d['Xg'], d['Xh'], d['Xl'], dtype=net.P['Wg'].dtype)
    allowed, target, has = validate_targets(d['allowed'], d['target'])
    Xh = np.zeros_like(Xh) if zero_helpers else Xh
    s, _ = net.forward(Xg, Xh, Xl, EMPTY_GRAPH if no_graph else graph)
    if allowed.shape != s.shape:
        raise ValueError("allowed mask must match model scores")
    pred = select_allowed(s, allowed)
    count = int(has.sum())
    if count == 0:
        return None, None
    acc = float((pred[has] == target[has]).mean())
    sm = np.where(allowed, s, -1e9)
    e = np.exp(sm - sm.max(-1, keepdims=True)) * allowed
    p = e / np.maximum(e.sum(-1, keepdims=True), 1e-30)
    ib, ig = np.where(has)
    ce = float(-np.log(np.maximum(p[ib, ig, target[ib, ig]], 1e-30)).mean())
    return acc, ce


# ---------------------------------------------------------------- experiments
def gradcheck():
    rng = np.random.default_rng(0)
    net = Net(rng, dtype=np.float64, D=16)
    graph = make_graph(rng)
    d = gen(3, rng, graph, Teacher())
    d = {k: (v.astype(np.float64) if v.dtype == np.float32 else v) for k, v in d.items()}
    args = (d['Xg'], d['Xh'], d['Xl'], graph, d['allowed'], d['target'])
    loss, grads = net.loss_and_grads(*args)

    # PyTorch-style check: |a - n| <= atol + rtol * max(|a|, |n|)
    atol, rtol = 1e-5, 1e-3
    max_abs, max_rel, n_checked, n_fail = 0.0, 0.0, 0, 0
    failures = []
    for name, v in net.P.items():
        flat = v.reshape(-1)
        for i in rng.choice(flat.size, size=min(40, flat.size), replace=False):
            old, eps = flat[i], 1e-5
            flat[i] = old + eps; lp, _ = net.loss_and_grads(*args)
            flat[i] = old - eps; lm, _ = net.loss_and_grads(*args)
            flat[i] = old
            num, ana = (lp - lm) / (2 * eps), grads[name].reshape(-1)[i]
            diff = abs(num - ana)
            max_abs = max(max_abs, diff)
            denom = max(abs(num), abs(ana))
            if denom > 1e-6:
                max_rel = max(max_rel, diff / denom)
            if diff > atol + rtol * denom:
                n_fail += 1
                if len(failures) < 5:
                    failures.append((name, int(i), float(num), float(ana), float(diff)))
            n_checked += 1
    ok = n_fail == 0
    print(f'gradcheck: {n_checked} entries over {len(net.P)} tensors | '
          f'max abs err {max_abs:.2e} | max rel err {max_rel:.2e} | '
          f'{n_fail} failures (atol={atol:g}, rtol={rtol:g}) | '
          f'{"PASS" if ok else "FAIL"}')
    if failures:
        for f in failures:
            print(f'  fail: {f[0]}[{f[1]}] num={f[2]:.3e} ana={f[3]:.3e} diff={f[4]:.3e}')
    return ok


def mask_stress(net, te, graph, seed):
    rng = np.random.default_rng(seed)
    d = sl(te, 0, min(150, len(te['Xg'])))
    allowed = rng.random(d['allowed'].shape) < 0.6
    rows = rng.choice(allowed.shape[0] * G, min(20, allowed.shape[0] * G), replace=False)
    allowed.reshape(-1, L)[rows] = False
    scores, _ = net.forward(d['Xg'], d['Xh'], d['Xl'], graph)
    pred = select_allowed(scores, allowed)
    picked = pred >= 0
    forbidden = int((~np.take_along_axis(
        allowed, np.maximum(pred, 0)[..., None], -1)[..., 0] & picked).sum())
    return dict(decisions=int(pred.size), permitted=int(picked.sum()),
                no_eligible=int((~picked).sum()), forbidden=forbidden)



def run_seed(seed, n=12000, steps=3000, bs=64, curve=(),
             net_kw=None):
    if not isinstance(n, int) or n < 2:
        raise ValueError("n must be an integer >= 2")
    if not isinstance(steps, int) or steps < 1:
        raise ValueError("steps must be an integer >= 1")
    if not isinstance(bs, int) or bs < 1:
        raise ValueError("bs must be an integer >= 1")
    t0 = time.time()
    rng = np.random.default_rng(seed)
    teacher = Teacher(1234)
    graph = make_graph(rng)
    data = gen(n, rng, graph, teacher)
    ntr = int(0.8 * n)
    tr, te = sl(data, 0, ntr), sl(data, ntr, n)
    net_kw = net_kw or {}
    net = Net(np.random.default_rng(seed + 1), **net_kw)
    hist = train(net, tr, graph, steps, bs, 2e-3, 2e-4, np.random.default_rng(seed + 2))
    r = dict(seed=seed, n_total=n, n_train=ntr, n_test=n - ntr, steps=steps, batch_size=bs,
             split='first 80% train / final 20% test; same synthetic generator and graph',
             label_source='synthetic deterministic teacher; not human or Hami outcome labels',
             loss_hist=hist, net_kw=net_kw)
    r['train_acc'], r['train_ce'] = evaluate(net, tr, graph)
    r['test_acc'], r['test_ce'] = evaluate(net, te, graph)
    r['uniform_baseline'] = uniform_baseline(te)
    r['heuristic_benefit_acc'] = heuristic_acc(te, 'benefit')
    r['heuristic_sum_acc'] = heuristic_acc(te, 'sum')
    r['no_graph_acc'] = evaluate(net, te, graph, no_graph=True)[0]
    r['zero_helper_acc'] = evaluate(net, te, graph, zero_helpers=True)[0]
    r['neither_acc'] = evaluate(net, te, graph, no_graph=True, zero_helpers=True)[0]
    g2 = make_graph(np.random.default_rng(seed + 1000))
    d2 = gen(2400, np.random.default_rng(seed + 3), g2, teacher)
    r['unseen_graph_acc'] = evaluate(net, d2, g2)[0]
    d3 = gen(2400, np.random.default_rng(seed + 4), graph, teacher, shift=True)
    r['shift_acc'], r['shift_uniform'] = evaluate(net, d3, graph)[0], uniform_baseline(d3)
    t2 = Teacher(1234, scale=np.random.default_rng(777).uniform(0.7, 1.3, 12))
    te2 = relabel(te, t2, graph)
    r['drift_acc'] = evaluate(net, te2, graph)[0]
    lab = te['target'] >= 0
    r['teacher_drift_agreement'] = float((te['target'][lab] == te2['target'][lab]).mean())
    r['mask_stress'] = mask_stress(net, te, graph, seed)
    r['curve'] = {}
    for m in curve:
        sub = sl(tr, 0, m)
        nm = Net(np.random.default_rng(seed + 5), **net_kw)
        train(nm, sub, graph, steps, bs, 2e-3, 2e-4, np.random.default_rng(seed + 6))
        r['curve'][m] = dict(train_acc=evaluate(nm, sub, graph)[0],
                             test_acc=evaluate(nm, te, graph)[0])
    r['seconds'] = round(time.time() - t0, 1)
    return r


# ---------------------------------------------------------------- summary
SUMMARY_KEYS = [
    'test_acc', 'train_acc', 'uniform_baseline',
    'heuristic_benefit_acc', 'heuristic_sum_acc',
    'no_graph_acc', 'zero_helper_acc', 'neither_acc',
    'unseen_graph_acc', 'shift_acc', 'drift_acc', 'teacher_drift_agreement',
]


def summary(path=None):
    folder = outdir(path)
    files = sorted(glob.glob(os.path.join(folder, 'results_*.json')))
    if not files:
        print(f'no results_*.json files found in {folder}/')
        return
    rows = []
    for f in files:
        with open(f) as fh:
            rows.append(json.load(fh))

    print(f'=== Per-seed results ({len(rows)} seed(s), {folder}/) ===')
    header = f'{"seed":>5}  ' + '  '.join(f'{k[:20]:>20}' for k in SUMMARY_KEYS)
    print(header)
    for r in rows:
        line = f'{r.get("seed", "?"):>5}  ' + '  '.join(
            f'{r.get(k, float("nan")):>20.4f}' if isinstance(r.get(k), (int, float))
            else f'{str(r.get(k)):>20}' for k in SUMMARY_KEYS)
        print(line)

    print()
    print('=== Aggregate (mean ± std across seeds) ===')
    for k in SUMMARY_KEYS:
        vals = [r[k] for r in rows if isinstance(r.get(k), (int, float))]
        if vals:
            arr = np.array(vals, dtype=float)
            print(f'  {k:>22}: {arr.mean():.4f} ± {arr.std():.4f}  (n={len(vals)})')

    print()
    print('=== Mask stress (must have forbidden=0) ===')
    bad = 0
    for r in rows:
        ms = r.get('mask_stress', {})
        fb = ms.get('forbidden', None)
        ne = ms.get('no_eligible', None)
        flag = '' if fb == 0 else '  <-- FAIL'
        if fb not in (0, None):
            bad += 1
        print(f'  seed {r.get("seed", "?"):>4}: forbidden={fb}  no_eligible={ne}{flag}')
    if bad:
        print(f'  {bad} seed(s) violate the hard policy mask.')
    else:
        print('  all seeds: hard policy mask holds.')

    print()
    print('=== Configs (from each result) ===')
    for r in rows:
        print(f'  seed {r.get("seed", "?"):>4}: {r.get("net_kw", {})}')


# ---------------------------------------------------------------- sweep
def sweep(seed=0, n=4000, steps=800, bs=64):
    """Cheap hyperparameter search on the dev seed. Never one of the reported seeds."""
    configs = [
        dict(num_steps=2, act='relu',  wd=0.0),
        dict(num_steps=3, act='relu',  wd=0.0),
        dict(num_steps=4, act='relu',  wd=0.0),
        dict(num_steps=3, act='leaky', wd=0.0),
        dict(num_steps=3, act='silu',  wd=0.0),
        dict(num_steps=3, act='silu',  wd=1e-4),
        dict(num_steps=4, act='silu',  wd=1e-4),
    ]
    print(f'sweep: {len(configs)} configs, n={n}, steps={steps}, dev seed={seed}')
    results = []
    for cfg in configs:
        t0 = time.time()
        rng = np.random.default_rng(seed)
        teacher = Teacher(1234)
        graph = make_graph(rng)
        data = gen(n, rng, graph, teacher)
        ntr = int(0.8 * n)
        tr, te = sl(data, 0, ntr), sl(data, ntr, n)
        net = Net(np.random.default_rng(seed + 1), **cfg)
        train(net, tr, graph, steps, bs, 2e-3, 2e-4, np.random.default_rng(seed + 2))
        acc, ce = evaluate(net, te, graph)
        row = dict(cfg)
        row['test_acc'] = acc
        row['test_ce'] = ce
        row['seconds'] = round(time.time() - t0, 1)
        results.append(row)
        print(f'  {cfg}  ->  test_acc={acc:.4f}  test_ce={ce:.4f}  '
              f'({row["seconds"]}s)', flush=True)
    best = max(results, key=lambda r: r['test_acc'])
    print()
    print(f'Best on dev seed: {best}')
    print('Use it in final via:  DIMAG_NET_KW=' + json.dumps(
        {k: best[k] for k in ('num_steps', 'act', 'wd')}) + ' python dimag_repro.py final 29 17 42')
    return results


# ---------------------------------------------------------------- CLI
def read_net_kw():
    raw = os.environ.get('DIMAG_NET_KW')
    if not raw:
        return {}
    return json.loads(raw)


def cmd_final(seeds, path=None, curve_map=None):
    folder = outdir(path)
    net_kw = read_net_kw()
    if net_kw:
        print(f'using DIMAG_NET_KW = {net_kw}')
    curve_map = curve_map or {}
    for seed in seeds:
        curve = curve_map.get(seed, ())
        n = int(os.environ.get('DIMAG_N', '12000'))
        steps = int(os.environ.get('DIMAG_STEPS', '3000'))
        bs = int(os.environ.get('DIMAG_BATCH_SIZE', '64'))
        r = run_seed(seed, n=n, steps=steps, bs=bs, net_kw=net_kw, curve=curve)
        out = os.path.join(folder, f'results_{seed}.json')
        with open(out, 'w') as f:
            r['source_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
            r['numpy_version'] = np.__version__
            json.dump(r, f, indent=1, default=float, allow_nan=False)
        print(f'done seed {seed}  {r["seconds"]}s  '
              f'test_acc={r["test_acc"]:.4f}  ->  {out}', flush=True)
    print(f'saved results in {folder}/. Next: python dimag_repro.py summary')


def cmd_run_all(seeds):
    print('\n### 1/4 gradcheck')
    ok = gradcheck()
    if not ok:
        print('gradcheck failed; aborting run_all.')
        return
    print('\n### 2/4 trial')
    r = run_seed(0, n=4000, steps=600)
    print(json.dumps({k: v for k, v in r.items() if k != 'loss_hist'},
                     indent=1, default=float))
    print('\n### 3/4 final')
    cmd_final(seeds)
    print('\n### 4/4 summary')
    summary()


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'gradcheck'
    if mode == 'gradcheck':
        gradcheck()
    elif mode == 'trial':
        t0 = time.time()
        r = run_seed(0, n=4000, steps=600)
        print(json.dumps({k: v for k, v in r.items() if k != 'loss_hist'},
                         indent=1, default=float))
        print('trial seconds', round(time.time() - t0, 1))
    elif mode == 'final':
        seeds = [int(a) for a in sys.argv[2:] if a.isdigit()] or [29, 17, 42]
        outdir_arg = None
        for a in sys.argv[2:]:
            if a.startswith('--outdir='):
                outdir_arg = a.split('=', 1)[1]
        cmd_final(seeds, path=outdir_arg,
                  curve_map={29: (600, 2400)} if 29 in seeds else None)
    elif mode == 'summary':
        summary()
    elif mode == 'sweep':
        seed = int(sys.argv[2]) if len(sys.argv) > 2 else 0
        sweep(seed=seed)
    elif mode == 'run_all':
        cmd_run_all([int(a) for a in sys.argv[2:] if a.isdigit()] or [29, 17, 42])
    else:
        print(f'unknown mode: {mode}')
        print('usage: python dimag_repro.py '
              '{gradcheck|trial|final [seeds...]|summary|sweep [seed]|run_all [seeds...]}')
        sys.exit(1)