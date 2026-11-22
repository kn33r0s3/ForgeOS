"""dimag-feature-schema v1: slot names, formulas, registries, validation.

Pure stdlib: importable without numpy. The tensor math lives in
feature_builder.py / ranker.py.

Authority: /tmp/dimag-001-feature-builder-design.md section 2.
Every slot below has one deterministic formula from the ForgeOS field
rows (backend/app/models.py, re-verified 22 Nov 2026) and a [0, 1] range
unless stated otherwise. Nothing is filled by guessing a column
position. The schema version travels with every example, every
checkpoint, and every prediction.
"""

SCHEMA_VERSION = "dimag-feature-schema v1"

# Ranker contract (dimag_numpy_ranker_v3.py, read in full): fixed dims.
G = 8  # gates per example
L = 5  # leads per gate
GDIM = 24  # gate feature slots
HDIM = 10  # helper feature channels
LDIM = 18  # lead feature slots
R = 20  # relation types (10 base + 10 reverse forms)
NUM_STEPS = 2  # message-passing steps
HIDDEN_DIM = 64

# ---------------------------------------------------------------- gate
# Xg [B, 8, 24]: slots 0-3 situation, 4-15 zone one-hot, 16-19 run state,
# 20-23 evidence state.
GATE_SLOT_NAMES = (
    ["uncertainty", "progress", "recency", "blocked_share"]
    + ["zone_%02d" % i for i in range(12)]
    + ["run_state_%d" % i for i in range(4)]
    + ["evidence_state_%d" % i for i in range(4)]
)
assert len(GATE_SLOT_NAMES) == GDIM

# ---------------------------------------------------------------- helper
# Xh [B, 8, 10]: the 10 helper gates, in book order.
HELPER_NAMES = (
    "log_everything",
    "summarize_and_finalize_next_move",
    "advance_every_time",
    "speed_at_peak",
    "never_start_from_square_one",
    "advancement_multiplies_with_time",
    "verify_from_evidence",
    "nothing_dormant",
    "never_copy",
    "never_lose_track",
)
assert len(HELPER_NAMES) == HDIM

# ---------------------------------------------------------------- lead
# Xl [B, 8, 5, 18]: one row per candidate ACTION.
LEAD_SLOT_NAMES = (
    "benefit",
    "helper_gated_value",
    "mitigator",
    "action_value",
    "cost",
    "effort",
    "uncertainty_value",
    "risk",
    "graph_value",
    "uncertainty_gate",
    "needs_approval",
    "secondary_benefit_1",
    "secondary_benefit_2",
    "secondary_cost",
    "zone_cost",
    "secondary_benefit_3",
    "secondary_benefit_4",
    "helper_gated_cost",
)
assert len(LEAD_SLOT_NAMES) == LDIM

# ---------------------------------------------------------------- zones
# dimag_zones v1. The 12 zone names come from Niroj's map text (book
# source S1). They are NOT in models.py, GATES.md, docs/
# hami-gates-as-neurons.md, or the Edition 3.0 book text (checked
# 22 Nov 2026: the book names the 12 zones only as a count). The
# registry exists with IDs 0-11; names are filled from the owner's map,
# never invented. Until filled, zone slots stay all-zero with
# zone_missing=1 in the example metadata.
ZONE_REGISTRY_VERSION = "dimag_zones v1"
ZONE_COUNT = 12
ZONE_NAMES = [None] * ZONE_COUNT  # UNFILLED -- filled only by Niroj.


def zone_name(zone_id):
    """Return the zone name for an id, or None while names are unfilled."""
    if not isinstance(zone_id, int) or not 0 <= zone_id < ZONE_COUNT:
        raise ValueError("zone_id must be an integer in [0, %d)" % ZONE_COUNT)
    return ZONE_NAMES[zone_id]


# ---------------------------------------------------------------- states
# Run states (book Appendix D, 8 operational states) collapse to 4,
# versioned and lossy by design; the full state is preserved in the
# example metadata.
RUN_STATES = (
    "READY",
    "RUNNING",
    "RECONCILING",
    "PAUSED",
    "NEEDS_APPROVAL",
    "STOPPED",
    "COMPLETED",
    "RETIRED",
)
RUN_STATE_SLOTS = {
    "READY": 0,
    "RUNNING": 1,
    "RECONCILING": 1,
    "PAUSED": 2,
    "NEEDS_APPROVAL": 2,
    "STOPPED": 3,
    "COMPLETED": 3,
    "RETIRED": 3,
}
RUN_STATE_MISSING_SLOT = 2  # PAUSED when no lifecycle event exists.

# Evidence states. CONTESTED (the 5th book state) maps to slot 3
# (BLOCKED) AND sets contested=1 in the example metadata: a contested
# gate must never look proven, and the distinction is preserved
# outside the tensor.
EVIDENCE_STATES = ("UNKNOWN", "IN_PROGRESS", "PROVEN", "BLOCKED", "CONTESTED")
EVIDENCE_STATE_SLOTS = {
    "UNKNOWN": 0,
    "IN_PROGRESS": 1,
    "PROVEN": 2,
    "BLOCKED": 3,
    "CONTESTED": 3,
}
EVIDENCE_STATE_MISSING_SLOT = 0  # UNKNOWN when there is no evidence.


def run_state_slot(state):
    """Collapse an 8-way run state to its 4-way slot. Unknown/missing -> 2."""
    if state is None:
        return RUN_STATE_MISSING_SLOT
    return RUN_STATE_SLOTS.get(str(state).upper(), RUN_STATE_MISSING_SLOT)


def evidence_state_slot(state):
    """Map an evidence state to (slot, contested_flag). Unknown -> (0, 0)."""
    if state is None:
        return EVIDENCE_STATE_MISSING_SLOT, 0
    key = str(state).upper()
    slot = EVIDENCE_STATE_SLOTS.get(key, EVIDENCE_STATE_MISSING_SLOT)
    return slot, 1 if key == "CONTESTED" else 0


# ---------------------------------------------------------------- helpers
def clip01(value):
    """Clip a number into [0, 1]; None becomes 0.0."""
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def validate_schema_version(version):
    """Fail closed unless the version is exactly dimag-feature-schema v1."""
    if version != SCHEMA_VERSION:
        raise ValueError(
            "unsupported feature-schema version %r (expected %r)"
            % (version, SCHEMA_VERSION)
        )
    return True
