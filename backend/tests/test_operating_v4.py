"""Operating Model v4: substrate bets, provenance, dormancy, verifier, frontier."""

import json

import pytest

from app import models
from app.services import operating_v4


def _evidence(db, source_type="firsthand"):
    ev = models.Evidence(
        claim="test", content="test", source="test", source_type=source_type
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def test_bet_is_substrate_projection(db):
    b = operating_v4.create_bet(
        db,
        claim="Fast replies recover sales",
        constraint="Response presence, not demand",
        test="One seller, one week",
        kill_criterion="No recovery",
        decision_rule="Recover >= 1 sale",
        skeptic_case="Sellers don't care about speed",
        money_at_risk="Rs 0",
    )
    assert b.entity_type == "bet"
    assert isinstance(b, models.SubstrateEntity)
    # No separate bets table.
    assert not hasattr(models, "Bet")
    live = operating_v4.live_bets(db)
    assert len(live) == 1


def test_bet_wip_limit(db):
    for i in range(3):
        operating_v4.create_bet(
            db, claim=f"c{i}", constraint="x", test="t",
            kill_criterion="k", decision_rule="r", skeptic_case="s",
        )
    with pytest.raises(ValueError, match="WIP limit"):
        operating_v4.create_bet(
            db, claim="c3", constraint="x", test="t",
            kill_criterion="k", decision_rule="r", skeptic_case="s",
        )


def test_agent_written_capped_l0(db):
    ev = _evidence(db, "agent_written")
    operating_v4.set_proof_level(db, ev.id, 4, source_type="agent_written")
    assert db.get(models.Evidence, ev.id).proof_level == 0


def test_secondhand_capped_l1(db):
    ev = _evidence(db, "secondhand")
    operating_v4.set_proof_level(db, ev.id, 5, source_type="secondhand")
    assert db.get(models.Evidence, ev.id).proof_level == 1


def test_l5_requires_verifier(db):
    ev = _evidence(db, "firsthand")
    with pytest.raises(ValueError, match="counterparty confirmation"):
        operating_v4.set_proof_level(db, ev.id, 5)
    operating_v4.set_proof_level(db, ev.id, 5, verifier="counterparty: seller confirmed")
    assert db.get(models.Evidence, ev.id).proof_level == 5


def test_l0_l4_unchanged(db):
    # Firsthand evidence can still sit at L0-L4 without a verifier.
    for level in (0, 2, 3, 4):
        ev = _evidence(db, "firsthand")
        operating_v4.set_proof_level(db, ev.id, level)
        assert db.get(models.Evidence, ev.id).proof_level == level


def test_found_wording_requires_l5(db):
    ev = _evidence(db, "firsthand")
    operating_v4.set_proof_level(db, ev.id, 4)
    with pytest.raises(ValueError, match="requires proof level >= L5"):
        operating_v4.check_found_wording(db, ev.id)
    operating_v4.set_proof_level(
        db, ev.id, 5, verifier="counterparty: seller confirmed"
    )
    # No raise at L5.
    operating_v4.check_found_wording(db, ev.id)
    with pytest.raises(ValueError, match="not found"):
        operating_v4.check_found_wording(db, 999999)


def test_plan_change_requires_l3(db):
    low = _evidence(db, "firsthand")
    operating_v4.set_proof_level(db, low.id, 2)
    with pytest.raises(ValueError, match="require proof >= L3"):
        operating_v4.check_plan_change(db, [low.id])
    ok = _evidence(db, "firsthand")
    operating_v4.set_proof_level(db, ok.id, 3)
    # No raise at L3+.
    operating_v4.check_plan_change(db, [ok.id])
    operating_v4.check_plan_change(db, [ok.id, ok.id])
    with pytest.raises(ValueError, match="not found"):
        operating_v4.check_plan_change(db, [999999])


def test_plan_change_rejects_non_evidence_ids(db):
    # A bet's assumption_ids are not evidence IDs — passing one must fail
    # as "not found", never silently pass or be reinterpreted.
    bet = operating_v4.create_bet(
        db,
        claim="c", constraint="x", test="t",
        kill_criterion="k", decision_rule="r", skeptic_case="s",
        assumption_ids=[12345],
    )
    attrs = bet.attributes
    assert "12345" in attrs  # the assumption id is stored on the bet
    with pytest.raises(ValueError, match="not found"):
        operating_v4.check_plan_change(db, [12345])


def test_flag_proof_violations(db):
    clean = _evidence(db, "firsthand")
    clean.claim = "We found that sellers reply faster"
    db.commit()
    operating_v4.set_proof_level(
        db, clean.id, 5, verifier="counterparty: seller confirmed"
    )
    viol = _evidence(db, "firsthand")
    viol.claim = "We found that buyers haggle"
    db.commit()
    operating_v4.set_proof_level(db, viol.id, 2)
    neutral = _evidence(db, "firsthand")
    neutral.claim = "Observed slow replies"
    db.commit()
    operating_v4.set_proof_level(db, neutral.id, 2)
    flags = operating_v4.flag_proof_violations(db)
    flagged_ids = [f["evidence_id"] for f in flags]
    assert viol.id in flagged_ids
    assert clean.id not in flagged_ids
    assert neutral.id not in flagged_ids
    assert flags[0]["proof_level"] == 2


def test_starved_blocks_builds_except_obligations(db):
    assert operating_v4.is_starved(db) is True
    with pytest.raises(ValueError, match="STARVED"):
        operating_v4.check_build_allowed(db)
    # System Obligations exempt.
    operating_v4.check_build_allowed(db, is_system_obligation=True)


def test_verification_rejects_incomplete(db):
    with pytest.raises(ValueError, match="rejected"):
        operating_v4.record_verification(db, "", "content", "1/1", True)
    # Regression: run 37442162237 sent empty test_counts (grep found no matches
    # on GitHub Actions), causing HTTP 422. The backend must reject it.
    with pytest.raises(ValueError, match="rejected"):
        operating_v4.record_verification(db, "abc123", "fetched", "", True)
    with pytest.raises(ValueError, match="rejected"):
        operating_v4.record_verification(db, "abc123", "", "198/198", True)
    rec = operating_v4.record_verification(db, "abc123", "fetched", "198/198", True)
    assert rec.passed is True


def test_dormancy_freeze_and_resume(tmp_path, db, monkeypatch):
    assert operating_v4.is_dormant(db) is False
    operating_v4.enter_dormancy(db)
    assert operating_v4.is_dormant(db) is True
    with pytest.raises(ValueError, match="Dormant"):
        operating_v4.check_agent_run_allowed(db)
    # Resume requires docs/RUN_STATE.md.
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="RUN_STATE.md"):
        operating_v4.exit_dormancy(db)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "RUN_STATE.md").write_text("# run state")
    operating_v4.exit_dormancy(db, run_state_path="docs/RUN_STATE.md")
    assert operating_v4.is_dormant(db) is False


def test_frontier_challenge_monthly(db):
    fc = operating_v4.record_frontier_challenge(
        db, "2026-10", "Lead-gen SaaS", "SaaS charges before value; we charge after."
    )
    assert fc.month == "2026-10"
    with pytest.raises(ValueError, match="already recorded"):
        operating_v4.record_frontier_challenge(db, "2026-10", "x", "y")


def test_scoreboard_readonly_shape(db):
    board = operating_v4.scoreboard(db)
    for field in (
        "days_since_last_contact",
        "observations",
        "conversations",
        "live_bets",
        "bets_killed",
        "bets_amplified",
        "highest_proof_level",
        "verified_rupees",
        "sampling_gaps",
        "who_not_heard_from",
        "owner_time_used",
        "owner_budget_remaining",
        "starved",
    ):
        assert field in board, f"scoreboard missing {field}"
    assert board["starved"] is True
    assert board["verified_rupees"] == 0.0


def test_gate_result_requires_kill_criterion(db):
    operating_v4.upsert_gate(db, 14, "Day 14: contact check")
    with pytest.raises(ValueError, match="BEFORE any result"):
        operating_v4.record_gate_result(db, 14, "pass")
    operating_v4.upsert_gate(
        db, 14, "Day 14: contact check", kill_criterion="No contact => review"
    )
    gate = operating_v4.record_gate_result(db, 14, "pass")
    assert gate.result == "pass"
    assert gate.decided_at is not None


def test_gate_criterion_immutable_after_result(db):
    operating_v4.upsert_gate(
        db, 30, "Day 30: frontier review", kill_criterion="Zero L3+ => challenged"
    )
    operating_v4.record_gate_result(db, 30, "challenged")
    with pytest.raises(ValueError, match="cannot be changed after a result"):
        operating_v4.upsert_gate(
            db, 30, "Day 30: frontier review", kill_criterion="New criterion"
        )
    # Title update without touching the criterion still works.
    gate = operating_v4.upsert_gate(db, 30, "Day 30: revised title")
    assert gate.title == "Day 30: revised title"
    assert gate.kill_criterion == "Zero L3+ => challenged"
    assert gate.result == "challenged"


def test_gate_invalid_day_rejected(db):
    with pytest.raises(ValueError, match="must be one of"):
        operating_v4.upsert_gate(db, 45, "Not a gate day")
    with pytest.raises(ValueError, match="not found"):
        operating_v4.record_gate_result(db, 45, "pass")


def test_seeded_gates_carry_kill_criteria(db):
    created = operating_v4.seed_frontier_gates(db)
    assert len(created) == 4
    # Seeded gates already carry kill criteria, so results record cleanly.
    for day in (14, 30, 60, 90):
        gate = operating_v4.record_gate_result(db, day, "reviewed")
        assert gate.kill_criterion
        assert gate.result == "reviewed"
    # Idempotent: second seed creates nothing.
    assert operating_v4.seed_frontier_gates(db) == []


def test_no_duplicate_gate_model(db):
    # One Gate model, one gate service seam, no v3 remnants.
    assert hasattr(models, "Gate")
    assert not hasattr(models, "GateV3")
    assert hasattr(operating_v4, "upsert_gate")
    assert hasattr(operating_v4, "record_gate_result")
    assert hasattr(operating_v4, "seed_frontier_gates")
    assert not hasattr(operating_v4, "operating_v3")


def _assumption(db):
    created = operating_v4.seed_assumptions(db)
    assert len(created) == 6
    return created[0]


def _probe(db, assumption_id, probe_type="observation"):
    return operating_v4.record_probe(
        db,
        assumption_id=assumption_id,
        probe_type=probe_type,
        affordable_loss="Rs 0",
        kill_criterion="No signal in 7 days",
    )


def test_probe_types_accepted(db):
    a = _assumption(db)
    for pt in ("observation", "conversation", "intervention"):
        p = _probe(db, a.id, pt)
        assert p.entity_type == "probe"
        assert isinstance(p, models.SubstrateEntity)


def test_probe_invalid_type_rejected(db):
    a = _assumption(db)
    with pytest.raises(ValueError, match="must be one of"):
        _probe(db, a.id, "survey")


def test_probe_requires_affordable_loss(db):
    a = _assumption(db)
    with pytest.raises(ValueError, match="affordable_loss is required"):
        operating_v4.record_probe(
            db, assumption_id=a.id, probe_type="observation",
            affordable_loss="", kill_criterion="k",
        )


def test_probe_requires_kill_criterion(db):
    a = _assumption(db)
    with pytest.raises(ValueError, match="kill_criterion is required"):
        operating_v4.record_probe(
            db, assumption_id=a.id, probe_type="observation",
            affordable_loss="Rs 0", kill_criterion="",
        )


def test_probe_assumption_must_resolve(db):
    with pytest.raises(ValueError, match="Assumption not found"):
        _probe(db, 999999)
    # A bet is a real entity but not an assumption — still rejected.
    bet = operating_v4.create_bet(
        db, claim="c", constraint="x", test="t",
        kill_criterion="k", decision_rule="r", skeptic_case="s",
    )
    with pytest.raises(ValueError, match="Assumption not found"):
        _probe(db, bet.id)


def test_one_active_intervention(db):
    a = _assumption(db)
    first = _probe(db, a.id, "intervention")
    assert len(operating_v4.active_probes(db, "intervention")) == 1
    with pytest.raises(ValueError, match="Only one active intervention"):
        _probe(db, a.id, "intervention")
    # Deciding the first permits another.
    operating_v4.decide_probe(db, first.id, "KILL", result="No effect")
    assert len(operating_v4.active_probes(db, "intervention")) == 0
    second = _probe(db, a.id, "intervention")
    assert second.id != first.id


def test_conversation_batch_of_five(db):
    a = _assumption(db)
    probes = [_probe(db, a.id, "conversation") for _ in range(5)]
    assert len(operating_v4.active_probes(db, "conversation")) == 5
    with pytest.raises(ValueError, match="batches of 5"):
        _probe(db, a.id, "conversation")
    # Deciding one frees a slot.
    operating_v4.decide_probe(db, probes[0].id, "AMPLIFY")
    assert len(operating_v4.active_probes(db, "conversation")) == 4
    sixth = _probe(db, a.id, "conversation")
    assert sixth.id not in [p.id for p in probes]


def test_decide_probe_invalid_decision(db):
    a = _assumption(db)
    p = _probe(db, a.id, "observation")
    with pytest.raises(ValueError, match="must be one of"):
        operating_v4.decide_probe(db, p.id, "MAYBE")
    with pytest.raises(ValueError, match="not found"):
        operating_v4.decide_probe(db, 999999, "KILL")


def test_no_duplicate_probe_model(db):
    assert not hasattr(models, "Probe")
    assert not hasattr(models, "Assumption")
    assert hasattr(operating_v4, "record_probe")
    assert hasattr(operating_v4, "decide_probe")
    assert hasattr(operating_v4, "active_probes")
    assert not hasattr(operating_v4, "operating_model")


def test_probe_creation_uses_canonical_substrate_write(db):
    a = _assumption(db)
    p = _probe(db, a.id, "observation")
    # Canonical write contract: identity starts as candidate.
    assert p.identity_state == "candidate"
    # entity_created event emitted for THIS probe entity.
    evt = (
        db.query(models.WorldEvent)
        .filter(
            models.WorldEvent.event_type == "entity_created",
        )
        .order_by(models.WorldEvent.id.desc())
        .first()
    )
    assert evt is not None
    payload = evt.payload if isinstance(evt.payload, dict) else {}
    assert payload.get("entity_type") == "probe" or "probe" in str(evt.payload)


def test_seed_assumptions_six(db):
    created = operating_v4.seed_assumptions(db)
    assert len(created) == 6
    for a in created:
        assert isinstance(a, models.SubstrateEntity)
        assert a.entity_type == "assumption"
        assert a.identity_state == "candidate"
        attrs = json.loads(a.attributes)
        assert attrs["status"] == "untested"
        assert attrs["evidence_links"] == []
        for field in (
            "statement", "deal_killer", "cost_to_test", "cheapest_test",
            "milestone", "source_note",
        ):
            assert field in attrs, f"missing {field}"


def test_seed_assumptions_idempotent(db):
    first = operating_v4.seed_assumptions(db)
    assert len(first) == 6
    second = operating_v4.seed_assumptions(db)
    assert second == []
    assert len(operating_v4.list_assumptions(db)) == 6


def test_seed_assumptions_emits_events(db):
    operating_v4.seed_assumptions(db)
    count = (
        db.query(models.WorldEvent)
        .filter(models.WorldEvent.event_type == "entity_created")
        .count()
    )
    assert count >= 6


def test_no_assumption_model(db):
    assert not hasattr(models, "Assumption")
    assert hasattr(operating_v4, "seed_assumptions")
    assert hasattr(operating_v4, "rank_assumptions")
    assert hasattr(operating_v4, "set_assumption_status")
    assert hasattr(operating_v4, "add_evidence_link")


def test_rank_assumptions_deal_killer_first(db):
    operating_v4.seed_assumptions(db)
    ranked = operating_v4.rank_assumptions(db)
    assert len(ranked) == 6
    attrs = [json.loads(a.attributes) for a in ranked]
    # First three are deal-killers.
    assert all(a["deal_killer"] for a in attrs[:3])
    assert not any(a["deal_killer"] for a in attrs[3:])
    # Within deal-killers: Rs 0 cheapest first.
    assert attrs[0]["cost_to_test"] == "Rs 0"
    # Deterministic: same order on repeat.
    reranked = operating_v4.rank_assumptions(db)
    assert [a.id for a in ranked] == [a.id for a in reranked]


def test_set_assumption_status_rejects_bad_id(db):
    operating_v4.seed_assumptions(db)
    with pytest.raises(ValueError, match="not found"):
        operating_v4.set_assumption_status(db, 999999, "supported")


def test_set_assumption_status_rejects_bad_value(db):
    a = operating_v4.seed_assumptions(db)[0]
    with pytest.raises(ValueError, match="must be one of"):
        operating_v4.set_assumption_status(db, a.id, "proven")


def test_supported_requires_evidence_links(db):
    a = operating_v4.seed_assumptions(db)[0]
    with pytest.raises(ValueError, match="without linked evidence"):
        operating_v4.set_assumption_status(db, a.id, "supported")
    operating_v4.add_evidence_link(db, a.id, "evidence:42")
    updated = operating_v4.set_assumption_status(db, a.id, "supported")
    assert json.loads(updated.attributes)["status"] == "supported"


def test_contradicted_and_untested(db):
    a = operating_v4.seed_assumptions(db)[0]
    updated = operating_v4.set_assumption_status(db, a.id, "contradicted")
    assert json.loads(updated.attributes)["status"] == "contradicted"
    updated = operating_v4.set_assumption_status(db, a.id, "untested")
    assert json.loads(updated.attributes)["status"] == "untested"


def test_add_evidence_link_idempotent(db):
    a = operating_v4.seed_assumptions(db)[0]
    operating_v4.add_evidence_link(db, a.id, "evidence:42")
    operating_v4.add_evidence_link(db, a.id, "evidence:42")
    operating_v4.add_evidence_link(db, a.id, "evidence:43")
    attrs = json.loads(db.get(models.SubstrateEntity, a.id).attributes)
    assert attrs["evidence_links"] == ["evidence:42", "evidence:43"]
    with pytest.raises(ValueError, match="not found"):
        operating_v4.add_evidence_link(db, 999999, "evidence:42")


def test_evidence_link_distinct_from_proof_level(db):
    # Linking evidence does not change any proof level anywhere.
    a = operating_v4.seed_assumptions(db)[0]
    operating_v4.add_evidence_link(db, a.id, "evidence:42")
    operating_v4.set_assumption_status(db, a.id, "supported")
    assert db.query(models.Evidence).count() == 0


def _orientation(db, beliefs=None, **kw):
    params = {
        "observer_who": "Niroj",
        "observer_from_where": "Kathmandu",
        "means": "direct conversation",
        "local_knowledge": "sellers answer DMs slowly",
        "beliefs": beliefs if beliefs is not None else [],
    }
    params.update(kw)
    return operating_v4.record_orientation(db, **params)


def test_orientation_created_as_projection(db):
    o = _orientation(db)
    assert isinstance(o, models.SubstrateEntity)
    assert o.entity_type == "orientation"
    assert o.identity_state == "candidate"


def test_orientation_emits_event(db):
    o = _orientation(db)
    evt = (
        db.query(models.WorldEvent)
        .filter(models.WorldEvent.event_type == "entity_created")
        .order_by(models.WorldEvent.id.desc())
        .first()
    )
    assert evt is not None
    assert "orientation" in str(evt.payload)


def test_orientation_version_monotonic(db):
    first = _orientation(db)
    second = _orientation(db)
    third = _orientation(db)
    assert json.loads(first.attributes)["version"] == 1
    assert json.loads(second.attributes)["version"] == 2
    assert json.loads(third.attributes)["version"] == 3


def test_orientation_beliefs_preserved(db):
    a = operating_v4.seed_assumptions(db)[0]
    o = _orientation(
        db,
        beliefs=[
            {"belief_text": "Speed matters", "assumption_id": a.id},
            {"belief_text": "Unlinked hunch", "assumption_id": None},
        ],
    )
    beliefs = json.loads(o.attributes)["beliefs"]
    assert beliefs[0] == {"belief_text": "Speed matters", "assumption_id": a.id}
    assert beliefs[1] == {"belief_text": "Unlinked hunch", "assumption_id": None}


def test_orientation_rejects_bad_assumption(db):
    with pytest.raises(ValueError, match="not found"):
        _orientation(db, beliefs=[{"belief_text": "x", "assumption_id": 999999}])


def test_orientation_schema_enforced(db):
    o = _orientation(db)
    attrs = json.loads(o.attributes)
    for field in (
        "version", "observer_who", "observer_from_where",
        "means", "local_knowledge", "beliefs",
    ):
        assert field in attrs


def _diagnosis(db, nodes=None, situation="Slow replies"):
    if nodes is None:
        nodes = [
            {"node_text": "Sellers are offline", "evidence": "obs:12",
             "binding_status": "most_binding_hypothesis"},
            {"node_text": "Buyers use other apps", "evidence": "obs:13",
             "binding_status": "not_binding_now"},
        ]
    return operating_v4.diagnose_constraints(db, situation=situation, nodes=nodes)


def test_diagnosis_created_as_projection(db):
    d = _diagnosis(db)
    assert isinstance(d, models.SubstrateEntity)
    assert d.entity_type == "constraint_diagnosis"
    assert d.identity_state == "candidate"


def test_diagnosis_emits_event(db):
    _diagnosis(db)
    evt = (
        db.query(models.WorldEvent)
        .filter(models.WorldEvent.event_type == "entity_created")
        .order_by(models.WorldEvent.id.desc())
        .first()
    )
    assert evt is not None
    assert "constraint_diagnosis" in str(evt.payload)


def test_diagnosis_requires_exactly_one_binding(db):
    with pytest.raises(ValueError, match="Exactly one"):
        _diagnosis(db, nodes=[
            {"node_text": "a", "evidence": "", "binding_status": "not_binding_now"},
            {"node_text": "b", "evidence": "", "binding_status": "may_bind_later"},
        ])
    with pytest.raises(ValueError, match="Exactly one"):
        _diagnosis(db, nodes=[
            {"node_text": "a", "evidence": "",
             "binding_status": "most_binding_hypothesis"},
            {"node_text": "b", "evidence": "",
             "binding_status": "most_binding_hypothesis"},
        ])


def test_diagnosis_rejects_bad_status(db):
    with pytest.raises(ValueError, match="must be one of"):
        _diagnosis(db, nodes=[
            {"node_text": "a", "evidence": "", "binding_status": "proven_fact"},
        ])


def test_diagnosis_evidence_stays_reference(db):
    d = _diagnosis(db)
    nodes = json.loads(d.attributes)["nodes"]
    assert nodes[0]["evidence"] == "obs:12"
    # No Evidence rows created, no proof levels touched.
    assert db.query(models.Evidence).count() == 0


def test_no_dedicated_orientation_diagnosis_models(db):
    assert not hasattr(models, "Orientation")
    assert not hasattr(models, "OrientationBelief")
    assert not hasattr(models, "ConstraintDiagnosis")
    assert not hasattr(models, "DiagnosisNode")
    assert hasattr(operating_v4, "record_orientation")
    assert hasattr(operating_v4, "diagnose_constraints")


def test_contributor_consent_defaults_false(db):
    c = operating_v4.add_contributor(db, "Seller A", notes="Kathmandu")
    assert c.consent_given is False
    assert c.consent_at is None


def test_consent_explicitly_recorded(db):
    c = operating_v4.add_contributor(db, "Seller B")
    c = operating_v4.record_consent(db, c.id)
    assert c.consent_given is True
    assert c.consent_at is not None
    with pytest.raises(ValueError, match="not found"):
        operating_v4.record_consent(db, 999999)


def test_observation_requires_consent(db):
    c = operating_v4.add_contributor(db, "Seller C")
    with pytest.raises(ValueError, match="Consent required"):
        operating_v4.record_sensor_observation(db, c.id, "claim", "content")
    with pytest.raises(ValueError, match="not found"):
        operating_v4.record_sensor_observation(db, 999999, "claim", "content")


def test_consented_observation_persisted_with_provenance(db):
    c = operating_v4.add_contributor(db, "Seller D")
    operating_v4.record_consent(db, c.id)
    ev = operating_v4.record_sensor_observation(db, c.id, "Buyers haggle", "observed")
    assert ev.source == "sensor-circle:Seller D"
    assert ev.source_type == "sensor"
    assert ev.provenance == "consent-based contributor observation"
    # Low proof under v4 semantics — never promoted by this path.
    assert ev.proof_level == 1


def test_silent_contributor_in_who_not_heard_from(db):
    c = operating_v4.add_contributor(db, "Silent Seller")
    operating_v4.record_consent(db, c.id)
    # No observations recorded → appears in silence list.
    assert "Silent Seller" in operating_v4.who_not_heard_from(db)
    # After an observation, no longer silent.
    operating_v4.record_sensor_observation(db, c.id, "claim", "content")
    assert "Silent Seller" not in operating_v4.who_not_heard_from(db)


def test_no_duplicate_sensor_model(db):
    assert hasattr(models, "SensorContributor")
    assert hasattr(operating_v4, "add_contributor")
    assert hasattr(operating_v4, "record_consent")
    assert hasattr(operating_v4, "record_sensor_observation")


def test_park_domain(db):
    h = operating_v4.park_domain(db, "Livestream selling", "No capacity to verify")
    assert h.entity_type == "horizon_domain"
    assert h.identity_state == "candidate"
    attrs = json.loads(h.attributes)
    assert attrs["name"] == "Livestream selling"
    assert attrs["reason_parked"] == "No capacity to verify"
    assert attrs["status"] == "parked"
    assert attrs["parked_at"]
    assert attrs["unparked_at"] is None


def test_duplicate_park_rejected(db):
    operating_v4.park_domain(db, "Wholesale", "Too early")
    with pytest.raises(ValueError, match="already parked"):
        operating_v4.park_domain(db, "Wholesale", "Different reason")


def test_unpark_preserves_history(db):
    h = operating_v4.park_domain(db, "Exports", "No license")
    h = operating_v4.unpark_domain(db, h.id)
    attrs = json.loads(h.attributes)
    assert attrs["status"] == "unparked"
    assert attrs["unparked_at"]
    assert attrs["parked_at"]  # original park record retained
    assert attrs["reason_parked"] == "No license"
    with pytest.raises(ValueError, match="not found"):
        operating_v4.unpark_domain(db, 999999)


def _bet(db, **kw):
    params = {
        "claim": "Fast replies recover sales",
        "constraint": "Response presence",
        "test": "One seller, one week",
        "kill_criterion": "No recovery",
        "decision_rule": "Recover >= 1 sale",
        "skeptic_case": "Sellers don't care",
    }
    params.update(kw)
    return operating_v4.create_bet(db, **params)


def test_parked_domain_blocks_bet(db):
    h = operating_v4.park_domain(db, "Dropshipping", "Out of scope")
    with pytest.raises(ValueError, match="parked on the Horizon register"):
        _bet(db, horizon_domain_id=h.id)
    # Unparked domain allows the bet.
    operating_v4.unpark_domain(db, h.id)
    b = _bet(db, horizon_domain_id=h.id)
    assert json.loads(b.attributes)["horizon_domain_id"] == h.id
    # Bets without a horizon reference still work.
    b2 = _bet(db)
    assert json.loads(b2.attributes)["horizon_domain_id"] is None
    # Invalid domain reference rejected.
    with pytest.raises(ValueError, match="not found"):
        _bet(db, horizon_domain_id=999999)


def test_no_horizon_domain_model(db):
    assert not hasattr(models, "HorizonDomain")
    assert hasattr(operating_v4, "park_domain")
    assert hasattr(operating_v4, "unpark_domain")
    assert hasattr(operating_v4, "list_horizon_domains")


def test_no_duplicate_bet_model(db):
    assert not hasattr(models, "Bet")
    assert hasattr(operating_v4, "create_bet")
    assert hasattr(operating_v4, "decide_bet")
    assert hasattr(operating_v4, "live_bets")


def test_bet_uses_canonical_substrate_write(db):
    b = _bet(db, assumption_ids=[1, 2])
    assert isinstance(b, models.SubstrateEntity)
    assert b.entity_type == "bet"
    assert b.identity_state == "candidate"
    attrs = json.loads(b.attributes)
    # All existing semantics preserved.
    assert attrs["claim"] == "Fast replies recover sales"
    assert attrs["constraint"] == "Response presence"
    assert attrs["test"] == "One seller, one week"
    assert attrs["kill_criterion"] == "No recovery"
    assert attrs["decision_rule"] == "Recover >= 1 sale"
    assert attrs["skeptic_case"] == "Sellers don't care"
    assert attrs["status"] == "live"
    assert attrs["assumption_ids"] == [1, 2]
    assert attrs["horizon_domain_id"] is None
    assert attrs["affordable_loss"]["owner_time"] is None
    # entity_created emitted specifically for this Bet.
    evt = (
        db.query(models.WorldEvent)
        .filter(models.WorldEvent.event_type == "entity_created")
        .order_by(models.WorldEvent.id.desc())
        .first()
    )
    assert evt is not None
    assert "bet" in str(evt.payload)


def test_bet_canonical_write_preserves_guards(db):
    # MAX_LIVE_BETS still enforced through the canonical path.
    bets = [_bet(db, claim=f"c{i}") for i in range(3)]
    with pytest.raises(ValueError, match="WIP limit"):
        _bet(db, claim="c3")
    # Free a slot, then parked-domain rejection still works.
    operating_v4.decide_bet(db, bets[0].id, "dampened")
    h = operating_v4.park_domain(db, "Dropshipping", "Out of scope")
    with pytest.raises(ValueError, match="parked on the Horizon register"):
        _bet(db, horizon_domain_id=h.id)


def test_decide_bet_killed_uses_canonical_archival(db):
    b = _bet(db)
    assert b.status == "active"
    decided = operating_v4.decide_bet(db, b.id, "killed", notes="No sales recovered")
    # Archived through the canonical seam, not direct assignment.
    assert decided.status == "archived"
    attrs = json.loads(decided.attributes)
    assert attrs["status"] == "killed"
    assert attrs["decision_notes"] == "No sales recovered"
    assert attrs["decided_at"]
    # Canonical entity_archived event recorded.
    evt = (
        db.query(models.WorldEvent)
        .filter(models.WorldEvent.event_type == "entity_archived")
        .order_by(models.WorldEvent.id.desc())
        .first()
    )
    assert evt is not None
    assert "archive" in str(evt.payload).lower() or "killed" in str(evt.payload).lower() or str(b.id) in str(evt.payload)


def test_decide_bet_killed_uses_kill_criterion_as_rationale(db):
    b = _bet(db)
    decided = operating_v4.decide_bet(db, b.id, "killed")
    assert decided.status == "archived"
    evt = (
        db.query(models.WorldEvent)
        .filter(models.WorldEvent.event_type == "entity_archived")
        .order_by(models.WorldEvent.id.desc())
        .first()
    )
    assert evt is not None
    # Rationale falls back to the bet's kill criterion when no notes given.
    assert "No recovery" in str(evt.payload)


def test_decide_bet_non_kill_unchanged(db):
    b = _bet(db)
    decided = operating_v4.decide_bet(db, b.id, "amplified", notes="Working")
    assert decided.status == "active"  # entity stays active
    attrs = json.loads(decided.attributes)
    assert attrs["status"] == "amplified"
    assert attrs["decision_notes"] == "Working"
    # No archival event for non-kill.
    count = (
        db.query(models.WorldEvent)
        .filter(models.WorldEvent.event_type == "entity_archived")
        .count()
    )
    assert count == 0


def test_killed_bet_frees_wip_slot(db):
    bets = [_bet(db, claim=f"c{i}") for i in range(3)]
    with pytest.raises(ValueError, match="WIP limit"):
        _bet(db, claim="c3")
    operating_v4.decide_bet(db, bets[0].id, "killed")
    # Killed bet is archived; live count drops; new bet allowed.
    assert len(operating_v4.live_bets(db)) == 2
    new_bet = _bet(db, claim="c3")
    assert new_bet.id not in [b.id for b in bets]


def test_archival_authorization_preserved(db):
    # Direct archival without the canonical seam is still rejected.
    from app.services import world_graph

    b = _bet(db)
    b.status = "archived"
    with pytest.raises(Exception):
        db.commit()
    db.rollback()
    # Canonical path with empty actor/rationale is rejected.
    with pytest.raises(Exception, match="actor and rationale"):
        world_graph.archive_entity(db, b, actor="", rationale="")
    db.rollback()
    with pytest.raises(Exception, match="actor and rationale"):
        world_graph.archive_entity(db, b, actor="owner", rationale="")
    db.rollback()
    assert db.get(models.SubstrateEntity, b.id).status == "active"
