"""Atomic checkpoint save/load + manifest + resume-equivalence helper.

Format (design section 4): one directory per checkpoint with
params.npz (every Net.P tensor by name), adam.npz (m, v, t) and
manifest.json (schema version, ranker source sha256, training-data
manifest -- the field snapshot id + row counts + training_rights
filter -- hyperparameters, seed, timestamp). The manifest's
field_snapshot is the idempotency_key set of the example batch, so a
checkpoint is traceable to the exact field state it learned from.

Atomicity: write to a temp directory on the same filesystem, fsync,
rename. A partial checkpoint is never visible as a checkpoint. Load
validates: every expected tensor present, shapes match the declared
architecture, all values finite -- else refuse (never load a corrupt
checkpoint into serving).
"""

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone

import numpy as np

from . import schema


class CheckpointError(ValueError):
    """A checkpoint is missing, corrupt, or fails validation."""


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fsync_dir(path):
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def save_checkpoint(directory, params, adam_state, *, ranker_source_sha256,
                    field_snapshot_keys, hyperparameters, seed,
                    schema_version=schema.SCHEMA_VERSION):
    """Atomically save a checkpoint directory.

    params: dict[str, np.ndarray] (every Net.P tensor by name).
    adam_state: {"m": dict, "v": dict, "t": int}.
    field_snapshot_keys: the idempotency_key set of the example batch.
    Returns the manifest dict that was written.
    """
    schema.validate_schema_version(schema_version)
    if not isinstance(params, dict) or not params:
        raise CheckpointError("params must be a non-empty dict of tensors")
    for name, tensor in params.items():
        array = np.asarray(tensor)
        if not np.isfinite(array).all():
            raise CheckpointError("refusing to save non-finite tensor %r" % name)
    manifest = {
        "schema_version": schema_version,
        "ranker_source_sha256": ranker_source_sha256,
        "field_snapshot": {
            "idempotency_keys": sorted(str(k) for k in field_snapshot_keys),
            "example_count": len(field_snapshot_keys),
        },
        "hyperparameters": dict(hyperparameters or {}),
        "seed": seed,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "param_shapes": {name: list(np.asarray(t).shape) for name, t in params.items()},
        "adam_t": int(adam_state.get("t", 0)),
    }
    parent = os.path.dirname(os.path.abspath(directory))
    os.makedirs(parent, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix=".dimag-ckpt-", dir=parent)
    try:
        np.savez(os.path.join(tmp, "params.npz"), **{k: np.asarray(v) for k, v in params.items()})
        np.savez(
            os.path.join(tmp, "adam.npz"),
            **{("m_%s" % k): np.asarray(v) for k, v in adam_state.get("m", {}).items()},
            **{("v_%s" % k): np.asarray(v) for k, v in adam_state.get("v", {}).items()},
        )
        manifest_path = os.path.join(tmp, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, sort_keys=True, indent=2)
        for name in ("params.npz", "adam.npz", "manifest.json"):
            with open(os.path.join(tmp, name), "rb") as handle:
                os.fsync(handle.fileno())
        _fsync_dir(tmp)
        os.rename(tmp, directory)
        _fsync_dir(parent)
    except BaseException:
        for name in os.listdir(tmp):
            os.unlink(os.path.join(tmp, name))
        os.rmdir(tmp)
        raise
    return manifest


def load_checkpoint(directory, *, expected_param_shapes):
    """Load and validate a checkpoint. Refuses corrupt ones.

    expected_param_shapes: dict[str, tuple] of the declared
    architecture. Returns (params, adam_state, manifest).
    """
    if not os.path.isdir(directory):
        raise CheckpointError("no checkpoint directory at %r" % directory)
    params_path = os.path.join(directory, "params.npz")
    adam_path = os.path.join(directory, "adam.npz")
    manifest_path = os.path.join(directory, "manifest.json")
    for path in (params_path, adam_path, manifest_path):
        if not os.path.isfile(path):
            raise CheckpointError("checkpoint %r is missing %s" % (directory, os.path.basename(path)))
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    schema.validate_schema_version(manifest.get("schema_version"))
    params = dict(np.load(params_path))
    missing = set(expected_param_shapes) - set(params)
    extra = set(params) - set(expected_param_shapes)
    if missing:
        raise CheckpointError("checkpoint is missing tensors: %s" % sorted(missing))
    if extra:
        raise CheckpointError("checkpoint has unexpected tensors: %s" % sorted(extra))
    for name, shape in expected_param_shapes.items():
        if tuple(params[name].shape) != tuple(shape):
            raise CheckpointError(
                "tensor %r shape %s != expected %s" % (name, tuple(params[name].shape), tuple(shape))
            )
        if not np.isfinite(params[name]).all():
            raise CheckpointError("tensor %r contains non-finite values" % name)
    adam_raw = dict(np.load(adam_path))
    adam_state = {"m": {}, "v": {}, "t": int(manifest.get("adam_t", 0))}
    for key, value in adam_raw.items():
        if key.startswith("m_"):
            adam_state["m"][key[2:]] = value
        elif key.startswith("v_"):
            adam_state["v"][key[2:]] = value
        else:
            raise CheckpointError("adam.npz has unexpected entry %r" % key)
    return params, adam_state, manifest


def ranker_source_sha256(ranker_path):
    """sha256 of the ranker source file, recorded in every manifest."""
    return _sha256_file(ranker_path)


def resume_equivalence_scores(net, examples, graph):
    """Score a fixed probe set with a Net; returns a list of score arrays.

    Used by the checkpoint round-trip test: scores before save must be
    bit-identical to scores after load.
    """
    from .ranker import select_allowed  # noqa: F401  (re-exported for callers)

    scores = []
    for example in examples:
        batch_scores, _cache = net.forward(
            np.asarray(example["Xg"])[None, :, :],
            np.asarray(example["Xh"])[None, :, :],
            np.asarray(example["Xl"])[None, :, :, :],
            graph,
        )
        scores.append(np.asarray(batch_scores[0]))
    return scores
