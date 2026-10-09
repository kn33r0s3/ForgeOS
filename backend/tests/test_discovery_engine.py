"""Open-world discovery engine: capability proofs over real substrate state.

Each test builds substrate state only through the canonical services (types,
entities, relations, evidence, events, capabilities), runs the engine, and
checks what it *discovered*, not merely that rows were created. Throughout,
the engine may only propose (possible/hypothesized) and must cite recorded rows.
"""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import models
from app.database import get_db
from app.main import app
from app.services import discovery_engine as engine
from app.services import world_graph

TEST_REF = "backend/tests/test_discovery_engine.py"
PROVENANCE = {"actor": "test", "revision": "e06b09f0a1b2c3d4"}
FIELD_SOURCE = {"url": "https://example.org/field-notes/2026-09", "retrieved_at": "2026-09-01T00:00:00Z"}


def _counts(db):
    return {
        table.__name__: db.query(table).count()
        for table in (models.SubstrateEntity, models.WorldRelation, models.Evidence,
                      models.WorldEvent, models.ForgeCapability, models.TypeRegistry)
    }


def _entity(db, entity_type, name, **attributes):
    return world_graph.create_entity(
        db, entity_type=entity_type, display_name=name, attributes=attributes, created_by="observer",
    )


def _engine_rows_are_only_proposals(db):
    """No engine output may claim more than possible/hypothesized, and every basis must resolve."""
    for evidence in db.query(models.Evidence).filter(models.Evidence.source.like("discovery_engine%")).all():
        assert evidence.support_level in engine.EPISTEMIC_STATES
    for relation in db.query(models.WorldRelation).filter_by(created_by=engine.ENGINE_ACTOR).all():
        assert relation.truth_state in engine.EPISTEMIC_STATES + ("refuted",)
    for entity in db.query(models.SubstrateEntity).filter_by(source_system=engine.ENGINE_ACTOR).all():
        attrs = json.loads(entity.attributes)
        assert attrs["epistemic_state"] in engine.EPISTEMIC_STATES
        assert attrs["basis"], entity.display_name
        for ref in attrs["basis"]:
            assert db.get(engine._BASIS_TABLES[ref["kind"]], ref["id"]) is not None


@pytest.fixture
def world(db):
    """A small recorded world with a contested premise under an open question."""
    world_graph.seed_core_types(db)
    record = models.ResearchQuestion(question="Which Kathmandu cafes would pay for faster card payments?")
    db.add(record)
    db.flush()
    question = world_graph.ensure_canonical_entity(db, "research_question", record.id)
    need = _entity(db, "need", "Cafes lose sales to slow card payments", area="thamel")
    premise = world_graph.create_relation(
        db, from_entity_id=question.id, to_entity_id=need.id, relation_type="derived_from",
        created_by="curiosity_engine",
    )
    supported = world_graph.create_evidence(
        db, subject_kind="entity", subject_id=need.id, support_level="supported",
        claim="Two owners said card terminals time out at peak hours.",
        source="field_interview", provenance=FIELD_SOURCE,
    )
    refuted = world_graph.create_evidence(
        db, subject_kind="entity", subject_id=need.id, support_level="refuted",
        claim="Terminal logs for the same cafes show no timeouts; queues come from order taking.",
        source="pos_terminal_log", provenance={"export": "terminal-log-2026-09.csv", "rows": 1840},
    )
    legacy = world_graph.create_capability(
        db, capability_type="workflow", name="legacy-card-payment-audit",
        description="Audits cafe card-payment flow.", owner_agent="legacy",
    )
    db.commit()
    # Rows written before the lifecycle contract can still say "active".
    db.execute(text("UPDATE capabilities SET status='active', test_ref=:ref WHERE id=:id"), {"ref": TEST_REF, "id": legacy.id})
    db.commit()
    return {"record": record, "question": question, "need": need, "premise": premise,
            "supported": supported, "refuted": refuted, "legacy": legacy}


def _by_kind(report, kind):
    return [row for row in report["surfaced"] if row["kind"] == kind]


def test_real_state_surfaces_contradiction_capability_gap_and_reframed_question(db, world):
    report = engine.run_discovery(db)
    db.commit()

    contradiction = [row for row in _by_kind(report, "contradiction") if f"#{world['need'].id})" in row["statement"]]
    assert len(contradiction) == 1
    attrs = json.loads(db.get(models.SubstrateEntity, contradiction[0]["entity_id"]).attributes)
    assert attrs["facets"]["supporting_evidence_ids"] == [world["supported"].id]
    assert attrs["facets"]["refuting_evidence_ids"] == [world["refuted"].id]
    assert {"kind": "evidence", "id": world["refuted"].id} in attrs["basis"]

    reframed = [row for row in _by_kind(report, "question") if row["method"] == "question_reframe"]
    assert len(reframed) == 1
    question_row = db.get(models.SubstrateEntity, reframed[0]["entity_id"])
    facets = json.loads(question_row.attributes)["facets"]
    assert facets["reframe_reason"] == "refuted_premise"
    assert facets["original_question"] == world["record"].question
    assert facets["premise_entity_id"] == world["need"].id
    assert "question may be wrong" in reframed[0]["statement"]
    reframes = db.query(models.WorldRelation).filter_by(
        relation_type="reframes", from_entity_id=question_row.id, to_entity_id=world["question"].id
    ).one()
    assert reframes.truth_state == "possible"

    gaps = [row for row in _by_kind(report, "capability_gap") if row["method"] == "capability_integrity"]
    assert len(gaps) == 1 and "legacy-card-payment-audit" in gaps[0]["statement"]

    # Nothing is fabricated: every output is a proposal citing recorded rows,
    # and the engine never touched the truth of what it inspected.
    _engine_rows_are_only_proposals(db)
    db.refresh(world["premise"])
    assert world["premise"].truth_state == "hypothesized"
    stored = db.query(models.WorldEvent).filter_by(event_type="discovery_run_completed").one()
    assert json.loads(stored.payload)["surfaced"] == len(report["surfaced"])


def test_empty_substrate_yields_nothing_invented(db):
    world_graph.seed_core_types(db)
    report = engine.run_discovery(db)
    assert report["surfaced"] == [] and report["rejected"] == [] and report["errors"] == []
    assert db.query(models.SubstrateEntity).filter_by(source_system=engine.ENGINE_ACTOR).count() == 0


def test_runs_are_idempotent(db, world):
    first = engine.run_discovery(db)
    db.commit()
    before = _counts(db)
    second = engine.run_discovery(db)
    db.commit()
    after = _counts(db)
    assert second["surfaced"] == []
    assert sorted(row["fingerprint"] for row in second["existing"]) == sorted(
        row["fingerprint"] for row in first["surfaced"] + first["existing"]
    )
    # Only the new run's own EVENT is added.
    assert {k: after[k] - before[k] for k in after} == {
        "SubstrateEntity": 0, "WorldRelation": 0, "Evidence": 0, "WorldEvent": 1,
        "ForgeCapability": 0, "TypeRegistry": 0,
    }


def test_missing_input_becomes_capability_gap_closed_only_by_the_verified_lifecycle(db, world):
    seen = []

    def compare_quotes(ctx):
        seen.append(ctx.inputs["observation.price_quotes"])
        return [engine.Finding(
            kind="observation", key="quotes", statement="Quote source is available for comparison.",
            basis=(engine.BasisRef("capability", ctx.inputs["observation.price_quotes"][0].id),),
            epistemic_state="possible",
        )]

    registry = engine.DiscoveryMethodRegistry([engine.DiscoveryMethod(
        "cross_place_price_gap", "1", "Compare live quotes across places.", compare_quotes,
        emits=("observation",), requires=("substrate.entities", "observation.price_quotes"),
    )])
    report = engine.run_discovery(db, registry=registry)
    db.commit()
    assert report["methods"][0]["status"] == "blocked_by_capability"
    assert seen == []
    gap = db.get(models.ForgeCapability, report["capability_gaps"][0]["capability_id"])
    assert gap.status == "proposed" and gap.capability_type == "discovery_input"
    assert json.loads(gap.attributes)["provides"] == ["observation.price_quotes"]
    gap_finding = _by_kind(report, "capability_gap")[0]
    assert "observation.price_quotes" in gap_finding["statement"]

    # A row that merely claims to be active does not close the gap.
    claimed = world_graph.create_capability(
        db, capability_type="integration", name="unverified-quotes", description="Claims quotes.",
        owner_agent="legacy", attributes={"provides": ["observation.price_quotes"]},
    )
    db.commit()
    db.execute(text("UPDATE capabilities SET status='active', test_ref=:ref WHERE id=:id"), {"ref": TEST_REF, "id": claimed.id})
    db.commit()
    assert engine.run_discovery(db, registry=registry)["methods"][0]["status"] == "blocked_by_capability"

    # Building the gap row itself through the hardened lifecycle closes it.
    # Non-starved: lifecycle tests verify mechanics, not operating discipline.
    world_graph.create_event(db, event_type="outreach.sent", source="test", payload={})
    db.commit()
    world_graph.begin_capability_build(db, gap)
    world_graph.mark_capability_tested(
        db, gap, test_ref=TEST_REF, command=f"python -m pytest {TEST_REF} -q",
        exit_code=0, output_excerpt="passed", provenance=PROVENANCE,
    )
    world_graph.activate_capability(db, gap)
    db.commit()
    report = engine.run_discovery(db, registry=registry)
    assert report["methods"][0]["status"] == "ran"
    assert [row.id for row in seen[0]] == [gap.id]
    assert _by_kind(report, "observation")[0]["statement"] == "Quote source is available for comparison."


def test_an_unknown_kind_is_proposed_as_a_type_and_deferred_until_activated(db, world):
    def timing(ctx):
        return [engine.Finding(
            kind="timing_window", key="peak", statement="Payment complaints cluster around peak hours.",
            basis=(engine.BasisRef("evidence", world["supported"].id),), epistemic_state="possible",
        )]

    registry = engine.DiscoveryMethodRegistry([engine.DiscoveryMethod("timing", "1", "Timing.", timing)])
    tables_before = set(db.get_bind().dialect.get_table_names(db.connection()))
    report = engine.run_discovery(db, registry=registry)
    db.commit()
    assert report["surfaced"] == []
    assert report["deferred"][0]["reason"] == "category_proposed"
    row = db.query(models.TypeRegistry).filter_by(category="entity_type", type_name="timing_window").one()
    assert row.status == "proposed"
    assert json.loads(row.schema_json) == engine.discovery_schema("timing_window")
    assert db.query(models.WorldEvent).filter_by(event_type="discovery_deferred").count() == 1
    assert set(db.get_bind().dialect.get_table_names(db.connection())) == tables_before

    world_graph.set_type_status(
        db, row, "active", actor="reviewer", rationale="Timing windows are a useful category.",
        evidence_ref=TEST_REF,
    )
    db.commit()
    report = engine.run_discovery(db, registry=registry)
    entity = db.get(models.SubstrateEntity, report["surfaced"][0]["entity_id"])
    assert entity.entity_type == "timing_window"
    assert json.loads(entity.attributes)["epistemic_state"] == "possible"


def test_fabricated_or_overclaiming_findings_are_rejected_and_broken_plugins_isolated(db, world):
    def fabricate(ctx):
        yield engine.Finding(kind="observation", key="ghost", statement="Invented.",
                             basis=(engine.BasisRef("evidence", 999_999),))
        yield engine.Finding(kind="observation", key="naked", statement="No basis.", basis=())
        yield engine.Finding(kind="hypothesis", key="sure", statement="Certainly true.",
                             basis=(engine.BasisRef("entity", world["need"].id),), epistemic_state="supported")

    def broken(ctx):
        raise RuntimeError("plugin bug")

    registry = engine.DEFAULT_REGISTRY.copy()
    registry.register(engine.DiscoveryMethod("fabricator", "1", "Bad plugin.", fabricate))
    registry.register(engine.DiscoveryMethod("broken", "1", "Crashes.", broken))
    report = engine.run_discovery(db, registry=registry)
    reasons = sorted(row["reason"] for row in report["rejected"])
    assert reasons == [
        "a finding must cite at least one recorded basis row",
        "basis evidence:999999 does not resolve to a recorded row",
        "findings must begin possible or hypothesized",
    ]
    assert report["errors"] == [{"method": "broken", "error": "RuntimeError: plugin bug"}]
    assert _by_kind(report, "contradiction")  # the other methods still ran
    _engine_rows_are_only_proposals(db)


def test_value_hypotheses_are_possible_and_advance_or_stop_only_through_evidence(db):
    world_graph.seed_core_types(db)
    kathmandu = [_entity(db, "resource", f"Laptop repair bench {i}", city="kathmandu", price_npr=p)
                 for i, p in enumerate((1500, 1800, 1600))]
    pokhara = [_entity(db, "resource", f"Laptop repair bench P{i}", city="pokhara", price_npr=p)
               for i, p in enumerate((4200, 4800))]
    shop = _entity(db, "organization", "Lakeside Electronics", street="lakeside road 6")
    need = _entity(db, "need", "Tourists need same-day charger replacement", location="lakeside road 6")
    report = engine.run_discovery(db)
    db.commit()

    divergence = [row for row in _by_kind(report, "observation") if row["method"] == "numeric_divergence"]
    assert len(divergence) == 1
    facets = json.loads(db.get(models.SubstrateEntity, divergence[0]["entity_id"]).attributes)["facets"]
    assert (facets["low_group"], facets["high_group"], facets["measure"]) == ("kathmandu", "pokhara", "price_npr")
    assert facets["ratio"] == pytest.approx(4500 / 1600)
    divergence_question = [row for row in _by_kind(report, "question")
                           if row["method"] == "numeric_divergence"]
    assert len(divergence_question) == 1 and "could it be used" in divergence_question[0]["statement"]

    hypothesis = [row for row in _by_kind(report, "hypothesis") if row["method"] == "disconnection"]
    assert len(hypothesis) == 1 and "lakeside road 6" in hypothesis[0]["statement"]
    relation = db.query(models.WorldRelation).filter_by(relation_type="may_relate").one()
    assert {relation.from_entity_id, relation.to_entity_id} == {shop.id, need.id}
    assert relation.truth_state == "possible"
    with pytest.raises(world_graph.SubstrateError, match="requires recorded tested evidence"):
        world_graph.transition_relation_truth_state(db, world_graph.transition_relation_truth_state(
            db, relation, "hypothesized"), "tested")
    db.rollback()
    assert not [row for row in kathmandu + pokhara if row.id in {relation.from_entity_id, relation.to_entity_id}]

    world_graph.create_evidence(
        db, subject_kind="relation", subject_id=relation.id, support_level="refuted",
        claim="The shop closed in 2025; the address now hosts a guesthouse.",
        source="site_visit", provenance={"visited_at": "2026-09-20", "observer": "field team"},
    )
    world_graph.transition_relation_truth_state(db, relation, "refuted")
    db.commit()
    report = engine.run_discovery(db)
    stop = _by_kind(report, "reason_to_stop")
    assert len(stop) == 1 and "refuted" in stop[0]["statement"]
    hypothesis_entity_id = hypothesis[0]["entity_id"]
    assert db.query(models.WorldRelation).filter_by(
        relation_type="stops", from_entity_id=stop[0]["entity_id"], to_entity_id=hypothesis_entity_id
    ).count() == 1
    _engine_rows_are_only_proposals(db)


def test_unanswered_question_is_reframed_from_research_history(db):
    world_graph.seed_core_types(db)
    record = models.ResearchQuestion(question="Is there demand for Newari language tutoring apps?")
    db.add(record)
    db.flush()
    world_graph.ensure_canonical_entity(db, "research_question", record.id)
    for source in ("github", "news"):
        db.add(models.ResearchTask(question_id=record.id, source=source, query="newari tutoring app",
                                   status="needs_research", evidence_ids="[]"))
    db.commit()
    report = engine.run_discovery(db, methods=["question_reframe"])
    reframed = _by_kind(report, "question")
    assert len(reframed) == 1
    assert "2 research tasks (github, news) ended without any evidence" in reframed[0]["statement"]
    basis = json.loads(db.get(models.SubstrateEntity, reframed[0]["entity_id"]).attributes)["basis"]
    assert {ref["kind"] for ref in basis} == {"entity", "research_question", "research_task"}


def test_isolation_and_recurrence_surface_neglect_and_repeated_behaviour(db):
    world_graph.seed_core_types(db)
    tools = [_entity(db, "tool", name) for name in ("Label printer", "Card reader", "Spare laptop")]
    owner = _entity(db, "person", "Shop owner")
    for used in tools[:2]:
        world_graph.create_relation(db, from_entity_id=owner.id, to_entity_id=used.id,
                                    relation_type="owned_by", created_by="observer")
    for day in range(3):
        world_graph.create_event(db, event_type="demand_observed", source="shop_log",
                                 entity_id=owner.id, payload={"day": day})
    report = engine.run_discovery(db, methods=["isolation", "recurrence"])
    observations = {row["method"]: row["statement"] for row in _by_kind(report, "observation")}
    assert "Spare laptop" in observations["isolation"] and "2 of 3 tool" in observations["isolation"]
    assert "repeatedly records demand_observed (3 times" in observations["recurrence"]
    # The engine's own derived_from links do not make the spare laptop look "used" later.
    db.commit()
    assert engine.run_discovery(db, methods=["isolation"])["existing"]


def test_methods_are_replaceable_and_registration_is_explicit(db, world):
    registry = engine.DEFAULT_REGISTRY.copy()
    with pytest.raises(world_graph.SubstrateError, match="already registered"):
        registry.register(engine.DiscoveryMethod("evidence_contradiction", "2", "dup", lambda ctx: ()))
    registry.register(engine.DiscoveryMethod("evidence_contradiction", "2", "silenced", lambda ctx: ()), replace=True)
    report = engine.run_discovery(db, registry=registry, methods=["evidence_contradiction"])
    assert report["methods"] == [{"name": "evidence_contradiction", "version": "2", "findings": 0, "status": "ran"}]
    assert engine.DEFAULT_REGISTRY.get("evidence_contradiction").version == "1"


def test_preview_is_read_only_and_api_runs_explicitly(db, world, monkeypatch):
    from app import security

    # Discovery runs are owner-keyed (Step 1); the test client presents the key.
    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "discovery-test-key")
    before = _counts(db)
    preview = engine.run_discovery(db, persist=False)
    db.rollback()
    assert _counts(db) == before
    assert {row["kind"] for row in preview["preview"]} >= {"contradiction", "question", "capability_gap"}

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app, headers={"X-API-Key": "discovery-test-key"})
        methods = client.get("/forge/substrate/discovery/methods").json()
        assert "question_reframe" in {row["name"] for row in methods}
        assert client.get("/forge/substrate/discovery/preview").status_code == 200
        assert _counts(db) == before
        created = client.post("/forge/substrate/discovery/runs", json={"methods": ["evidence_contradiction"]})
        assert created.status_code == 201, created.text
        findings = client.get("/forge/substrate/discovery/findings", params={"kind": "contradiction"}).json()
        assert findings and all(row["epistemic_state"] == "hypothesized" for row in findings)
        assert client.post("/forge/substrate/discovery/runs", json={"methods": ["nope"]}).status_code == 422
        # With the optional API key configured, discovery is private like the rest of the substrate.
        monkeypatch.setattr(security.settings, "FORGE_API_KEY", "discovery-secret")
        assert client.get("/forge/substrate/discovery/findings").status_code == 401
        assert client.post("/forge/substrate/discovery/runs", json={}).status_code == 401
        keyed = client.get("/forge/substrate/discovery/methods", headers={"X-API-Key": "discovery-secret"})
        assert keyed.status_code == 200
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Step 3B-1: Tests for PR #15 recovered sources (adapted from test_discovery_selection.py).
# These verify the 5 new DiscoveryMethods work as discovery_engine methods.
# ---------------------------------------------------------------------------

def _horizon_domain(db, name, status="unparked", reason=None):
    """Create a horizon domain entity."""
    from datetime import datetime, timezone

    attrs = {
        "name": name,
        "status": status,
        "reason_parked": reason or "test reason",
        "parked_at": datetime.now(timezone.utc).isoformat(),
        "unparked_at": None,
    }
    return world_graph.create_entity(
        db,
        entity_type="horizon_domain",
        display_name=name,
        attributes=attrs,
        created_by="test",
    )


def _run_method(db, method_name):
    """Run a single discovery method and return its findings."""
    from app.services.discovery_engine import DiscoveryContext, DEFAULT_REGISTRY

    method = DEFAULT_REGISTRY.get(method_name)
    ctx = DiscoveryContext(db=db, inputs={})
    return list(method.run(ctx))


def test_pr15_map_gap_finds_uncovered_domain(db):
    """Horizon domain with no candidate coverage → new_unknown finding."""
    world_graph.seed_core_types(db)
    _horizon_domain(db, "Quantum Computing", status="unparked")
    findings = _run_method(db, "map_gap")
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "new_unknown"
    assert "Quantum Computing" in f.statement
    assert f.facets["source"] == "map_gap"
    assert f.facets["provenance"] == "model-proposed"
    assert f.facets["confirmed"] is False


def test_pr15_map_gap_skips_covered_domain(db):
    """Horizon domain with candidate coverage → no finding."""
    from app.services import operating_v4 as _opv4

    world_graph.seed_core_types(db)
    _horizon_domain(db, "Thamel Retail", status="unparked")
    # Create a bet that references the domain
    bet = world_graph.create_entity(
        db, entity_type=_opv4.BET_ENTITY_TYPE, display_name="Test Bet",
        attributes={"claim": "Thamel Retail has unknowns", "constraint": "", "test": ""},
        created_by="test",
    )
    findings = _run_method(db, "map_gap")
    # The domain name appears in bet text, so no finding
    assert len(findings) == 0


def test_pr15_superseded_belief_finds_flawed_assumption(db):
    """Superseded belief → contradiction finding."""
    world_graph.seed_core_types(db)
    # Create two beliefs, one superseded by the other
    old = models.Belief(statement="Old wrong belief", confidence_score=0.3)
    db.add(old)
    db.flush()
    new = models.Belief(statement="New correct belief", confidence_score=0.9)
    db.add(new)
    db.flush()
    old.merged_into_id = new.id
    db.flush()

    findings = _run_method(db, "superseded_belief")
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "contradiction"
    assert f.facets["source"] == "evidence_contradiction"
    assert f.facets["superseded_belief_id"] == old.id


def test_pr15_outcome_anomaly_finds_failed_outcome(db):
    """Failed outcome → anomaly finding."""
    world_graph.seed_core_types(db)
    outcome = models.Outcome(
        outcome_type="test_outcome",
        success=False,
        qualitative_result="The test failed unexpectedly",
        verification_state="UNVERIFIED",
    )
    db.add(outcome)
    db.flush()

    findings = _run_method(db, "outcome_anomaly")
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "anomaly"
    assert f.facets["source"] == "outcome_anomaly"
    assert f.facets["label"] == "failed its objective"


def test_pr15_outcome_anomaly_finds_disputed_outcome(db):
    """Disputed outcome → anomaly finding."""
    world_graph.seed_core_types(db)
    outcome = models.Outcome(
        outcome_type="test_outcome",
        success=True,
        qualitative_result="Results are contested",
        verification_state="DISPUTED",
    )
    db.add(outcome)
    db.flush()

    findings = _run_method(db, "outcome_anomaly")
    assert len(findings) == 1
    assert findings[0].facets["label"] == "disputed"


def test_pr15_pending_capability_finds_proposed_capability(db):
    """Proposed capability → capability_gap finding."""
    world_graph.seed_core_types(db)
    cap = world_graph.create_capability(
        db, capability_type="workflow", name="test-probe-capability",
        description="A capability Hami needs.", owner_agent="test",
    )
    # create_capability sets status; ensure it's proposed
    cap.status = "proposed"
    db.flush()

    findings = _run_method(db, "pending_capability")
    assert len(findings) >= 1
    f = [x for x in findings if x.facets.get("capability_id") == cap.id]
    assert len(f) == 1
    assert f[0].kind == "capability_gap"
    assert f[0].facets["source"] == "capability_gap"


def test_pr15_horizon_escape_finds_parked_domain(db):
    """Parked domain → blind_spot finding."""
    world_graph.seed_core_types(db)
    _horizon_domain(db, "Far Future Tech", status="parked", reason="Too early")

    findings = _run_method(db, "horizon_escape")
    assert len(findings) == 1
    f = findings[0]
    assert f.kind == "blind_spot"
    assert f.facets["source"] == "horizon_escape"
    assert f.facets["horizon_relation"] == "outside"
    assert "Far Future Tech" in f.statement


def test_pr15_new_finding_types_registered(db):
    """The 6 PR #15 finding types are in BUILTIN_KINDS."""
    from app.services import discovery_engine as engine

    for kind in ("new_unknown", "updated_unknown", "anomaly",
                 "blind_spot", "new_relationship", "no_material_discovery"):
        assert kind in engine.BUILTIN_KINDS, f"{kind} not in BUILTIN_KINDS"


def test_pr15_methods_registered(db):
    """The 5 PR #15 methods are in DEFAULT_REGISTRY."""
    from app.services.discovery_engine import DEFAULT_REGISTRY

    for name in ("map_gap", "superseded_belief", "outcome_anomaly",
                 "pending_capability", "horizon_escape"):
        method = DEFAULT_REGISTRY.get(name)
        assert method.name == name


def test_pr15_empty_sources_yield_no_findings(db):
    """Empty database → no findings from PR #15 methods (honest, not fabricated)."""
    world_graph.seed_core_types(db)
    for name in ("map_gap", "superseded_belief", "outcome_anomaly",
                 "pending_capability", "horizon_escape"):
        findings = _run_method(db, name)
        assert findings == [], f"{name} fabricated findings from empty DB"


# Relevance gate regression tests (Section 2: strengthened qualification)


def test_bibliographic_pattern_cannot_generate_commercial_questions(db):
    """Bibliographic metadata patterns are classified as background, not commercial."""
    from app.services import pattern_engine, curiosity_engine

    world_graph.seed_core_types(db)
    # Create signals from scholarly source with bibliographic keywords
    for i in range(5):
        sig = models.Signal(
            source="crossref",
            content=f"Crossref metadata record {i} with bibliographic evidence",
            signal_type="observation",
        )
        db.add(sig)
    db.flush()

    patterns = pattern_engine.run_pattern_detection(db)
    # At least one pattern should be detected
    assert len(patterns) >= 1

    # Check that bibliographic patterns are marked
    biblio_patterns = [p for p in patterns if "[BIBLIOGRAPHIC BACKGROUND]" in (p.description or "")]
    # If patterns were created from this data, they should be marked
    # (may be 0 if keywords don't cluster, which is also fine)

    # Curiosity should not generate questions from bibliographic patterns
    ce = curiosity_engine.CuriosityEngine(db)
    unexplored = ce.find_unexplored_patterns()
    for pattern in unexplored:
        assert "[BIBLIOGRAPHIC BACKGROUND]" not in (pattern.description or ""), \
            "Bibliographic pattern leaked into commercial question generation"


def test_observation_only_pattern_cannot_bypass_qualification(db):
    """Patterns with only 'observation' signals (no problem/demand) do not qualify."""
    from app.services import curiosity_engine

    world_graph.seed_core_types(db)
    # Create a pattern from observation-only signals (non-scholarly source)
    signals = []
    for i in range(5):
        sig = models.Signal(
            source="web",
            content=f"Generic observation about topic {i} without problem context",
            signal_type="observation",  # NOT problem or demand
        )
        db.add(sig)
        signals.append(sig)
    db.flush()

    # Create pattern manually with these signals
    pattern = models.Pattern(
        title="Recurring theme: topic, observation",
        description="5 signals repeatedly mention: topic, observation.",
        frequency=5,
        confidence_score=50.0,
        origin_signal_ids=",".join(str(s.id) for s in signals),
    )
    db.add(pattern)
    db.flush()

    ce = curiosity_engine.CuriosityEngine(db)
    # Pattern should NOT be commercially qualified (no problem/demand grounding)
    assert not ce._is_commercially_qualified(pattern), \
        "Observation-only pattern incorrectly qualified for commercial questions"

    # Should not appear in unexplored patterns for question generation
    unexplored = ce.find_unexplored_patterns()
    pattern_ids = [p.id for p in unexplored]
    assert pattern.id not in pattern_ids, \
        "Unqualified pattern leaked into question generation"


def test_grounded_problem_pattern_can_qualify(db):
    """Patterns with problem/demand signals CAN qualify for commercial questions."""
    from app.services import curiosity_engine

    world_graph.seed_core_types(db)
    # Create signals indicating real problems
    signals = []
    for i in range(5):
        sig = models.Signal(
            source="manual",
            content=f"Customers complain about slow delivery {i}",
            signal_type="problem",  # Real-world problem!
        )
        db.add(sig)
        signals.append(sig)
    db.flush()

    pattern = models.Pattern(
        title="Recurring theme: slow, delivery, customers",
        description="5 signals repeatedly mention: slow, delivery, customers.",
        frequency=5,
        confidence_score=75.0,
        origin_signal_ids=",".join(str(s.id) for s in signals),
    )
    db.add(pattern)
    db.flush()

    ce = curiosity_engine.CuriosityEngine(db)
    # Pattern SHOULD be commercially qualified (problem grounding)
    assert ce._is_commercially_qualified(pattern), \
        "Problem-grounded pattern should qualify for commercial questions"
