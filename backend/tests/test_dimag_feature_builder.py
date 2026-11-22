"""DIMAG-001 acceptance tests (design section 8). Pure logic, no database.

Fixtures are anonymized copies of real ForgeOS rows (gate chains from
the capacity / income / training work), never live secrets. The test
runs with pytest; numpy is required (pytest.importorskip) because the
ranker is a NumPy model. NOTE: backend/requirements.txt does not list
numpy yet -- until it does, this module skips in the Mac backend env
and the logic is verified on the VM (see the DIMAG-001 report).

Cases: three real gate networks built, rebuilt after a fresh builder
(restart simulation), input-hash match + prediction match; gate with
no evidence; only-lead-blocked; empty graph; contradictory evidence
(CONTESTED -> BLOCKED slot + metadata flag, never PROVEN); unknown
relation_type rejected with a named error; checkpoint save/load
round-trip with resume equivalence (bit-identical probe scores).
"""

import copy
import hashlib
from datetime import datetime, timezone

import numpy as np
import pytest

pytest.importorskip("numpy")

from app.services.dimag import schema
from app.services.dimag.checkpoint import (
    load_checkpoint,
    resume_equivalence_scores,
    save_checkpoint,
)
from app.services.dimag.feature_builder import DimagFeatureBuilder, example_hash
from app.services.dimag.governance_mask import GovernanceInput
from app.services.dimag.ranker import EMPTY_GRAPH, Net, select_allowed
from app.services.dimag.relations import UnknownRelationTypeError

NOW = datetime(2026, 11, 22, 13, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------- fixtures
def _gate(gid, name, run_state=None):
    attrs = {}
    if run_state is not None:
        attrs["run_state"] = run_state
    return {
        "id": gid,
        "entity_type": "gate",
        "display_name": name,
        "attributes": attrs,
        "status": "active",
    }


def _evidence(eid, gate_id, claim, support_level, *, complete=True, proof_level=5):
    return {
        "id": eid,
        "subject_kind": "gate",
        "subject_id": gate_id,
        "claim": claim,
        "support_level": support_level,
        "content_fingerprint": ("fp-%d" % eid) if complete else None,
        "source": "run-log-%d" % eid,
        "verifier": "verifier-%d" % eid if complete else None,
        "proof_level": proof_level if complete else 0,
        "provenance": "provenance-%d" % eid if complete else None,
        "consent_status": "granted",
        "recorded_at": "2026-11-21T10:00:00Z",
        "source_kind": "TEST",
    }


def _event(eid, gate_id, event_type, payload, occurred_at="2026-11-22T12:00:00Z"):
    return {
        "id": eid,
        "event_type": event_type,
        "entity_id": gate_id,
        "payload": payload,
        "source": "forge_loop",
        "occurred_at": occurred_at,
        "idempotency_key": "evt-%d" % eid,
    }


def _evaluated(eid, gate_id, state, criteria, met):
    return _event(
        eid, gate_id, "gate_evaluated",
        {"state": state, "criteria": criteria, "met": met},
    )


def _relation(rid, src, dst, relation_type, *, strength=0.8, truth_state="supported"):
    return {
        "id": rid,
        "from_entity_id": src,
        "to_entity_id": dst,
        "relation_type": relation_type,
        "direction": "directed",
        "strength": strength,
        "truth_state": truth_state,
    }


def _action(aid, gate_id, action_type, objective, *, status="PROPOSED",
            policy_result="ALLOW", parameters=None, verification_state="UNVERIFIED"):
    return {
        "id": aid,
        "gate_id": gate_id,
        "action_type": action_type,
        "objective": objective,
        "parameters_json": parameters or {},
        "status": status,
        "policy_result": policy_result,
        "proposed_at": "2026-11-22T11:00:00Z",
        "approved_at": None,
        "started_at": None,
        "completed_at": None,
        "verification_state": verification_state,
    }


def _outcome(oid, action_id, *, success=True, actual_value=1.0):
    return {
        "id": oid,
        "action_id": action_id,
        "observed_at": "2026-11-22T12:30:00Z",
        "outcome_type": "ACTUAL_RESPONSE",
        "actual_value": actual_value,
        "success": success,
        "verification_state": "VERIFIED",
        "data_scope": "REAL",
        "source_kind": "TEST",
    }


def _capacity_network():
    """SFU capacity chain (from the 20x50 / 20x75 runs)."""
    gates = [
        _gate(1, "sfu-1000-baseline", "COMPLETED"),
        _gate(2, "sfu-1500-frame-integrity"),
        _gate(3, "sfu-1500-cause"),
        _gate(4, "sfu-safe-copy-treatment"),
        _gate(5, "sfu-1500-repeat", "PAUSED"),
    ]
    evidence = [
        _evidence(1, 1, "20x50 run passes 1000 viewers", "supported"),
        _evidence(2, 2, "20x75 run passes 1500 viewers", "refuted"),
        _evidence(3, 3, "missing frames traced to assembler", "hypothesized", complete=False),
        _evidence(4, 4, "copy reduction preserves NACK", "refuted"),
        _evidence(5, 5, "repeat run is safe to start", "hypothesized", complete=False),
    ]
    events = [
        _evaluated(1, 1, "PROVEN", ["viewers_1000", "latency_p99", "heap_6gib"],
                   ["viewers_1000", "latency_p99", "heap_6gib"]),
        _evaluated(2, 2, "BLOCKED", ["pending_frames_zero"], []),
        _evaluated(3, 3, "IN_PROGRESS", ["trace_3_timestamps", "identify_path"], []),
        _evaluated(4, 4, "BLOCKED", ["nack_preserved"], []),
        _evaluated(5, 5, "IN_PROGRESS", ["headroom_ok"], []),
    ]
    relations = [
        _relation(1, 2, 1, "DEPENDS_ON"),
        _relation(2, 3, 2, "DEPENDS_ON"),
        _relation(3, 3, 2, "CONTRADICTS", strength=0.9),
        _relation(4, 4, 3, "DEPENDS_ON"),
        _relation(5, 5, 3, "DEPENDS_ON"),
        _relation(6, 5, 4, "LEADS_TO", truth_state="hypothesized"),
    ]
    actions = [
        _action(1, 1, "research", "stage the next rung", status="SUCCEEDED",
                verification_state="VERIFIED_SUCCESS"),
        _action(2, 1, "research", "record the 1000 baseline", parameters={"owner": "muse", "next_check_at": "2026-11-23T00:00:00Z"}),
        _action(3, 2, "research", "read the failing gate"),
        _action(4, 3, "research", "trace the three timestamps", parameters={"fallback": "packet capture"}),
        _action(5, 4, "research", "test the copy reduction"),
        _action(6, 5, "research", "wait for the cause", policy_result="REQUIRE_APPROVAL"),
    ]
    outcomes = [_outcome(1, 1, success=True, actual_value=1000.0)]
    return gates, relations, evidence, events, actions, outcomes


def _income_network():
    """Seller / enquiry-organiser chain (from the income work)."""
    gates = [
        _gate(11, "seller-outreach", "COMPLETED"),
        _gate(12, "enquiry-organiser"),
        _gate(13, "pitch-sent"),
        _gate(14, "reply-received"),
    ]
    evidence = [
        _evidence(11, 11, "seller verified from public posts", "supported"),
        _evidence(12, 12, "enquiries need one organised record", "hypothesized", complete=False),
        _evidence(13, 13, "pitch delivered to seller", "refuted"),
    ]
    events = [
        _evaluated(11, 11, "PROVEN", ["seller_found", "contact_route"], ["seller_found", "contact_route"]),
        _evaluated(12, 12, "IN_PROGRESS", ["record_built"], []),
        _evaluated(13, 13, "BLOCKED", ["pitch_sent"], []),
    ]
    relations = [
        _relation(11, 12, 11, "DEPENDS_ON"),
        _relation(12, 13, 12, "DEPENDS_ON"),
        _relation(13, 13, 14, "LEADS_TO", truth_state="hypothesized"),
        _relation(14, 12, 13, "CONTRADICTS", strength=0.7),
    ]
    actions = [
        _action(11, 11, "outreach", "draft the first contact", status="SUCCEEDED",
                verification_state="VERIFIED_SUCCESS"),
        _action(12, 12, "research", "build the enquiry record"),
        _action(13, 13, "outreach", "send the pitch", policy_result="REQUIRE_APPROVAL"),
        _action(14, 14, "research", "watch for the reply"),
    ]
    outcomes = [_outcome(11, 11, success=True, actual_value=1.0)]
    return gates, relations, evidence, events, actions, outcomes


def _training_network():
    """Training chain (dedup / holdout / pilot / teacher)."""
    gates = [
        _gate(21, "corpus-dedup", "COMPLETED"),
        _gate(22, "holdout-rebuild"),
        _gate(23, "pilot-train", "RUNNING"),
        _gate(24, "teacher-verify", "COMPLETED"),
    ]
    evidence = [
        _evidence(21, 21, "all 20 chunks deduped", "supported"),
        _evidence(22, 22, "holdout rebuilt from v2", "hypothesized", complete=False),
        _evidence(23, 23, "pilot loss falling", "supported"),
        _evidence(24, 24, "teacher blobs sha-verified", "supported"),
    ]
    events = [
        _evaluated(21, 21, "PROVEN", ["chunks_20", "drops_match"], ["chunks_20", "drops_match"]),
        _evaluated(22, 22, "IN_PROGRESS", ["snapshot_v2", "seed_606006"], ["snapshot_v2"]),
        _evaluated(23, 23, "IN_PROGRESS", ["loss_falling"], ["loss_falling"]),
        _evaluated(24, 24, "PROVEN", ["blobs_ok"], ["blobs_ok"]),
    ]
    relations = [
        _relation(21, 22, 21, "DEPENDS_ON"),
        _relation(22, 23, 22, "DEPENDS_ON"),
        _relation(23, 24, 23, "SUPPORTS"),
        _relation(24, 22, 21, "CONTRADICTS", strength=0.85),
    ]
    actions = [
        _action(21, 21, "research", "write the v2 snapshot", status="SUCCEEDED",
                verification_state="VERIFIED_SUCCESS"),
        _action(22, 22, "research", "rebuild the holdout"),
        _action(23, 23, "research", "keep the pilot training"),
        _action(24, 24, "research", "verify the teacher blobs"),
    ]
    outcomes = [_outcome(21, 21, success=True, actual_value=1604092.0)]
    return gates, relations, evidence, events, actions, outcomes


def _build_all(network, target_id, *, governance=None, training_review=None):
    gates, relations, evidence, events, actions, outcomes = network
    target = next(g for g in gates if g["id"] == target_id)
    builder = DimagFeatureBuilder(now=NOW, governance=governance or GovernanceInput(now=NOW))
    return builder.build_example(
        target, gates, relations, evidence, events, actions, outcomes,
        training_review=training_review,
    )


# ---------------------------------------------------------------- cases
def test_three_networks_build_and_hash_stable():
    """Build three networks; rebuild after a fresh builder; hashes match."""
    for network_fn, target_id in ((_capacity_network, 1), (_income_network, 11), (_training_network, 21)):
        first = _build_all(network_fn(), target_id)
        second = _build_all(copy.deepcopy(network_fn()), target_id)
        assert first["metadata"]["input_hash"] == second["metadata"]["input_hash"]
        assert example_hash(first) == example_hash(second)
        assert first["Xg"].shape == (schema.G, schema.GDIM)
        assert first["Xh"].shape == (schema.G, schema.HDIM)
        assert first["Xl"].shape == (schema.G, schema.L, schema.LDIM)
        assert first["allowed"].shape == (schema.G, schema.L)
        assert first["target"].shape == (schema.G,)


def test_restart_prediction_match():
    """Fixed-seed Net scores are bit-identical across the rebuild."""
    net = Net(np.random.default_rng(0))
    for network_fn, target_id in ((_capacity_network, 1), (_income_network, 11), (_training_network, 21)):
        first = _build_all(network_fn(), target_id)
        second = _build_all(copy.deepcopy(network_fn()), target_id)
        scores_a, _ = net.forward(
            first["Xg"][None], first["Xh"][None], first["Xl"][None], first["graph"]
        )
        scores_b, _ = net.forward(
            second["Xg"][None], second["Xh"][None], second["Xl"][None], second["graph"]
        )
        assert np.array_equal(scores_a, scores_b)


def test_gate_with_no_evidence():
    """Uncertainty 1.0, UNKNOWN, no crash."""
    example = _build_all(_income_network(), 14)
    assert example["Xg"][0, 0] == pytest.approx(1.0)
    assert example["metadata"]["evidence_states"][14] == "UNKNOWN"
    assert example["Xg"][0, 20] == pytest.approx(1.0)  # UNKNOWN slot 0.


def test_only_lead_blocked():
    """Allowed all False, prediction -1."""
    gate = _gate(99, "blocked-only-lead")
    actions = [_action(99, 99, "research", "the only lead", policy_result="BLOCK")]
    builder = DimagFeatureBuilder(now=NOW, governance=GovernanceInput(now=NOW))
    example = builder.build_example(gate, [gate], [], [], [], actions, [])
    assert not example["allowed"][0].any()
    assert example["target"][0] == -1
    scores = np.zeros((1, schema.G, schema.L), dtype=np.float32)
    assert select_allowed(scores, example["allowed"][None])[0, 0] == -1


def test_empty_graph():
    """A gate with no relations is a valid example; graph contributes 0."""
    gate = _gate(98, "lonely-gate")
    builder = DimagFeatureBuilder(now=NOW, governance=GovernanceInput(now=NOW))
    example = builder.build_example(gate, [gate], [], [], [], [], [])
    assert len(example["graph"][0]) == 0
    net = Net(np.random.default_rng(0))
    scores_graph, _ = net.forward(
        example["Xg"][None], example["Xh"][None], example["Xl"][None], example["graph"]
    )
    scores_empty, _ = net.forward(
        example["Xg"][None], example["Xh"][None], example["Xl"][None], EMPTY_GRAPH
    )
    assert np.array_equal(scores_graph, scores_empty)


def test_contradictory_evidence():
    """CONTESTED -> BLOCKED slot + metadata flag, never PROVEN."""
    gate = _gate(97, "contested-gate")
    evidence = [
        _evidence(97, 97, "the claim holds", "supported"),
        _evidence(98, 97, "the claim holds", "refuted"),
    ]
    builder = DimagFeatureBuilder(now=NOW, governance=GovernanceInput(now=NOW))
    example = builder.build_example(gate, [gate], [], evidence, [], [], [])
    assert example["metadata"]["evidence_states"][97] == "CONTESTED"
    assert 97 in example["metadata"]["contested"]
    assert example["Xg"][0, 23] == pytest.approx(1.0)  # BLOCKED slot 3.
    assert example["Xg"][0, 22] == pytest.approx(0.0)  # never PROVEN slot 2.


def test_unknown_relation_type_rejected():
    """Unknown relation_type is rejected at ingestion with a named error."""
    gates, relations, evidence, events, actions, outcomes = _capacity_network()
    relations = list(relations) + [_relation(99, 2, 1, "TELEPORTS")]
    target = next(g for g in gates if g["id"] == 1)
    builder = DimagFeatureBuilder(now=NOW, governance=GovernanceInput(now=NOW))
    with pytest.raises(UnknownRelationTypeError, match="TELEPORTS"):
        builder.build_example(target, gates, relations, evidence, events, actions, outcomes)


def test_checkpoint_round_trip_resume_equivalence(tmp_path):
    """Save/load round-trip; probe scores bit-identical."""
    net = Net(np.random.default_rng(0))
    from app.services.dimag.ranker import Adam

    probes = [
        _build_all(_capacity_network(), 1),
        _build_all(_income_network(), 11),
        _build_all(_training_network(), 21),
    ]
    graph = probes[0]["graph"]
    before = resume_equivalence_scores(net, probes, graph)
    adam = Adam(net.P)
    directory = tmp_path / "ckpt"
    manifest = save_checkpoint(
        str(directory),
        net.P,
        {"m": adam.m, "v": adam.v, "t": adam.t},
        ranker_source_sha256=hashlib.sha256(b"test").hexdigest(),
        field_snapshot_keys=[p["metadata"]["input_hash"] for p in probes],
        hyperparameters={"lr": 0.002, "steps": 0},
        seed=0,
    )
    assert manifest["schema_version"] == schema.SCHEMA_VERSION
    loaded_params, loaded_adam, loaded_manifest = load_checkpoint(
        str(directory),
        expected_param_shapes={k: tuple(v.shape) for k, v in net.P.items()},
    )
    assert loaded_manifest["schema_version"] == schema.SCHEMA_VERSION
    assert loaded_adam["t"] == 0
    net2 = Net(np.random.default_rng(999))
    net2.P = {k: np.array(v) for k, v in loaded_params.items()}
    after = resume_equivalence_scores(net2, probes, graph)
    for score_before, score_after in zip(before, after):
        assert np.array_equal(score_before, score_after)


def test_zone_names_unfilled():
    """Zone slots stay all-zero with zone_missing=1 until Niroj supplies names."""
    assert schema.ZONE_NAMES == [None] * schema.ZONE_COUNT
    for network_fn, target_id in ((_capacity_network, 1), (_income_network, 11), (_training_network, 21)):
        example = _build_all(network_fn(), target_id)
        assert not example["Xg"][:, 4:16].any()
        assert example["metadata"]["zone_missing"]


def test_training_rights_pending_by_default():
    """No reviewed grant -> pending; a reviewed grant -> granted."""
    pending = _build_all(_capacity_network(), 1)
    assert pending["metadata"]["training_rights"] == "pending"
    granted = _build_all(
        _capacity_network(), 1,
        training_review={"reviewed": True, "decision": "granted"},
    )
    assert granted["metadata"]["training_rights"] == "granted"


def test_label_action_blocked_by_policy_is_unlabelled():
    """An executed action the policy blocks cannot be a label."""
    gate = _gate(96, "blocked-label-gate")
    action = _action(96, 96, "research", "the executed lead", status="SUCCEEDED",
                     policy_result="BLOCK", verification_state="VERIFIED_SUCCESS")
    outcome = _outcome(96, 96, success=True, actual_value=2.0)
    builder = DimagFeatureBuilder(now=NOW, governance=GovernanceInput(now=NOW))
    example = builder.build_example(gate, [gate], [], [], [], [action], [outcome])
    assert example["target"][0] == -1
