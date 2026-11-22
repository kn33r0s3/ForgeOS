"""DIMAG-001: the gate-network feature builder (dimag-feature-schema v1).

The builder connects the persistent gate field (the six primitives in
backend/app/models.py) to the neural ranker, so Hami LLM thinks and
decides from DIMAG's own concepts, methodology and neurology.

DIMAG-004: the durable intelligence worker (dimag-004-worker v1).
The continuous worker that consumes DIMAG-003 diagnostic leads and
executes them -- with leases, idempotency, and reconciliation --
without ever executing anything unauthorized, without ever
re-deriving a trace, and without ever writing an experience row or
training the ranker. Its state lives in plain files under
~/hami/dimag-004-worker/ (no new infrastructure).

Public API (stdlib-only modules are importable without numpy):
  schema, relations, governance_mask -- always importable.
  worker, field_seam -- always importable (stdlib-only).
  feature_builder, checkpoint, ranker -- need numpy (the ranker is a
  NumPy model; backend/requirements.txt lists numpy==2.5.5 since
  22 Nov 2026 -- see the DIMAG-001 report -- so these names are
  resolved lazily).
  runner -- the DIMAG-004 CLI (lazy; run as
  `python -m backend.app.services.dimag.runner`).

ranker.py is the byte-identical v3 ranker (dimag_numpy_ranker_v3.py,
sha256 e6afdc3bdc001a6aacfb355eb9b8e48a512012fc8b87696d21d83d04a8109296).
Its Teacher / gen functions are the SYNTHETIC experiment harness only;
the production path (feature_builder -> Net) never uses them, and the
synthetic-trained weights do NOT transfer (design section 6).

worker.py is the DIMAG-004 reference implementation ported verbatim,
with exactly two adaptations (both marked "Mac/ForgeOS port"): the
Worker.action_reader hook and the read_action() delegation, so field
mode reads the LIVE ForgeOS Action row on every call (design SS5.1).
field_seam.py is the field-mode seam (ForgeOSSeam + field_wiring),
which reads live Action rows, live STOP state
(OpHamiRuntimeControl.safe_mode_enabled) and live DoNotContact rows
through a SQLAlchemy session supplied by the caller. The worker never
writes a ForgeOS row.
"""

from . import governance_mask, relations, schema
from . import field_seam, worker

__all__ = [
    "schema",
    "relations",
    "governance_mask",
    "feature_builder",
    "checkpoint",
    "ranker",
    "worker",
    "field_seam",
    "runner",
    "SCHEMA_VERSION",
]

SCHEMA_VERSION = schema.SCHEMA_VERSION


def __getattr__(name):
    """Lazy import for the numpy-backed modules + the runner CLI (PEP 562)."""
    if name in ("feature_builder", "checkpoint", "ranker", "runner"):
        import importlib

        return importlib.import_module("." + name, __package__)
    raise AttributeError("module %r has no attribute %r" % (__name__, name))
