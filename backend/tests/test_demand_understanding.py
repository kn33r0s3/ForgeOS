import json
from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.migrations import run_migrations
from app.services import demand_understanding, source_clearance_registry, world_graph


def _observation(db, text, key):
    return demand_understanding.record_raw_observation(
        db,
        text,
        metadata={
            "identity_key": key,
            "source_type": "synthetic",
            "provenance": {"fixture": "demand-understanding-test"},
        },
    )


def _authorized_fixture_observation(
    db,
    *,
    when,
    observation_id="fixture-record-1",
    authorized_at=datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc),
):
    entry = next(
        item
        for item in source_clearance_registry.source_clearances()
        if item.registry_id == "crossref-public-works-metadata"
    )
    authorization = source_clearance_registry.authorize_request(
        entry.url,
        collector=entry.collector,
        db=db,
        now=authorized_at,
    )
    return demand_understanding.record_authorized_source_observation(
        db,
        "Synthetic fixture: independent report says ingredient X is unavailable. Contact: sample.person@example.test +1-202-555-0147",
        authorization=authorization,
        source_reference=entry.url,
        observation_field="title",
        source_timestamp=when,
        observation_identity=observation_id,
        metadata={"provenance": {"fixture": "synthetic adapter response"}},
    )


def test_authorized_clearance_observation_persists_event_evidence_and_provenance(db):
    signal = _authorized_fixture_observation(
        db, when=datetime(2026, 9, 27, 10, 0, tzinfo=timezone.utc)
    )
    assert signal.source_type == "external"
    assert signal.canonical_url == "https://api.crossref.org/works"
    assert "[redacted-email]" in signal.content
    assert "[redacted-phone]" in signal.content
    assert "sample.person@example.test" not in signal.content
    assert signal.category is None
    assert signal.external_id != "fixture-record-1"
    assert db.get(models.SourceFetchGate, "crossref-public-works-metadata") is not None
    event = db.query(models.WorldEvent).filter_by(event_type="demand_observed").one()
    assert json.loads(event.payload)["signal_id"] == signal.id
    signal_entity = db.query(models.SubstrateEntity).filter_by(
        source_system="signals", source_id=str(signal.id)
    ).one()
    evidence = db.query(models.Evidence).filter_by(
        idempotency_key=f"demand-observation-evidence:{signal.id}:v1"
    ).one()
    provenance = json.loads(evidence.provenance)
    assert evidence.support_level == "possible"
    assert provenance["metadata"]["provenance"]["source_registry_id"] == (
        "crossref-public-works-metadata"
    )
    assert signal_entity.entity_type == "signal"
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.Action).count() == 0
    assert db.query(models.SubstrateEntity).filter_by(entity_type="customer").count() == 0
    assert db.query(models.IntegrationDelivery).count() == 0


def test_uncleared_or_stale_source_authorization_is_rejected(db):
    entry = next(
        item
        for item in source_clearance_registry.source_clearances()
        if item.registry_id == "crossref-public-works-metadata"
    )
    with __import__("pytest").raises(PermissionError):
        demand_understanding.record_authorized_source_observation(
            db,
            "Unverified public page.",
            authorization=None,
            source_reference=entry.url,
            observation_field="title",
            source_timestamp=None,
            observation_identity="untrusted",
        )
    authorization = source_clearance_registry.authorize_request(
        entry.url,
        collector=entry.collector,
        db=db,
        now=datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc),
    )
    with __import__("pytest").raises(PermissionError):
        demand_understanding.record_authorized_source_observation(
            db,
            "Wrong endpoint.",
            authorization=authorization,
            source_reference="https://example.com/public",
            observation_field="title",
            source_timestamp=None,
            observation_identity="wrong-endpoint",
        )
    with __import__("pytest").raises(PermissionError):
        demand_understanding.record_authorized_source_observation(
            db,
            "Uncleared abstract text.",
            authorization=authorization,
            source_reference=entry.url,
            observation_field="abstract",
            source_timestamp=None,
            observation_identity="wrong-field",
        )
    assert db.query(models.Signal).count() == 0


def test_duplicate_and_independent_observations_are_distinct_and_idempotent(db):
    first_time = datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc)
    first = _authorized_fixture_observation(db, when=first_time)
    duplicate = demand_understanding.record_authorized_source_observation(
        db,
        "Synthetic fixture: independent report says ingredient X is unavailable. Contact: sample.person@example.test +1-202-555-0147",
        authorization=source_clearance_registry.CollectionAuthorization(
            entry=source_clearance_registry.clearance_for_url(first.canonical_url),
            reserved_at=datetime(2026, 9, 28, 12, 0, tzinfo=timezone.utc),
        ),
        source_reference=first.canonical_url,
        observation_field="title",
        source_timestamp=first_time,
        observation_identity="fixture-record-1",
        metadata={"provenance": {"fixture": "synthetic adapter response"}},
    )
    independent = _authorized_fixture_observation(
        db,
        when=datetime(2026, 9, 27, 10, 0, tzinfo=timezone.utc),
        observation_id="fixture-record-2",
        authorized_at=datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc),
    )
    assert duplicate.id == first.id
    assert independent.id != first.id
    assert independent.supersedes_signal_id is None
    assert db.query(models.Signal).count() == 2


def test_raw_observation_is_event_evidence_and_uncategorized(db):
    signal = _observation(db, "Buyer repeatedly seeks an item unavailable locally.", "obs-a")
    assert signal.id
    assert db.query(models.WorldEvent).filter_by(event_type="demand_observed").count() == 1
    entity = db.query(models.SubstrateEntity).filter_by(
        source_system="signals", source_id=str(signal.id)
    ).one()
    evidence = db.query(models.Evidence).filter_by(subject_id=entity.id).one()
    assert evidence.support_level == "possible"
    assert json.loads(evidence.provenance)["signal_id"] == signal.id
    assert entity.entity_type == "signal"


def test_possible_demand_has_no_need_until_understood(db):
    signal = _observation(db, "Someone wants something but the outcome is unclear.", "obs-b")
    result = demand_understanding.understand(db, [signal.id])
    assert result.state == "possible_demand"
    assert result.inferred_need_id is None
    assert db.query(models.SubstrateEntity).filter_by(entity_type="need").count() == 0
    assert db.query(models.Opportunity).count() == 0


def test_demand_layer_adds_no_vertical_or_parallel_observation_tables(db):
    table_names = set(inspect(db.get_bind()).get_table_names())
    assert not table_names.intersection(
        {"observations", "demands", "orders", "event_bus"}
    )


def test_multiple_observations_strengthen_hypothesis_without_market_claim(db):
    first = _observation(db, "Buyer repeatedly requests X.", "obs-c1")
    second = _observation(db, "Another buyer reports X is unavailable.", "obs-c2")
    result = demand_understanding.understand(
        db,
        [first.id, second.id],
        object_description="X",
        desired_outcome="obtain acceptable X",
    )
    assert result.state == "hypothesized"
    assert "recurring demand" in result.possible_demand
    assert all("customer" not in (row.claim or "").lower() for row in db.query(models.Evidence).all())
    assert db.query(models.Opportunity).count() == 0


def test_unresolved_questions_prevent_sufficient_need(db):
    signal = _observation(db, "A business cannot reliably obtain Y.", "obs-d")
    result = demand_understanding.understand(
        db,
        [signal.id],
        object_description="Y",
        desired_outcome="receive acceptable Y",
    )
    assert result.state == "hypothesized"
    assert result.unresolved_questions
    assert result.inferred_need_id is None


def test_adequate_capability_is_reused_without_research(db):
    signal = _observation(db, "A repair shop needs a documented incidence estimate.", "obs-e")
    result = demand_understanding.understand(
        db,
        [signal.id],
        object_description="an incidence estimate",
        desired_outcome="receive a bounded estimate",
        unresolved_questions=[],
        sufficient=True,
    )
    match = demand_understanding.search_existing_capabilities(
        db,
        result,
        requirement_id="scholarly_evidence",
        required_evidence_type="scholarly_metadata",
    )
    assert result.inferred_need_id is not None
    assert match["matched_sources"]
    assert match["capability_gap_id"] is None
    assert db.query(models.ResearchQuestion).count() == 0


def test_inadequate_capability_enters_existing_gap_path(db):
    signal = _observation(db, "A farm needs local postharvest observations.", "obs-f")
    result = demand_understanding.understand(
        db,
        [signal.id],
        object_description="local postharvest observations",
        desired_outcome="receive crop loss observations",
        unresolved_questions=[],
        sufficient=True,
    )
    match = demand_understanding.search_existing_capabilities(
        db,
        result,
        requirement_id="primary_agriculture_observation",
        required_evidence_type="primary_agriculture_observation",
        geographic_scope="Nepal",
        population_scope="smallholder farmers",
    )
    gap = db.get(models.ForgeCapability, match["capability_gap_id"])
    assert match["research_eligible"] is True
    assert json.loads(gap.attributes)["capability_discovery"]["record_kind"] == "research_capability_gap"
    gap_data = json.loads(gap.attributes)["capability_discovery"]
    gap_evidence = db.get(models.Evidence, gap_data["search_result"]["evidence_id"])
    assert gap_evidence is not None
    assert gap_evidence.support_level == "possible"
    assert json.loads(gap_evidence.provenance)["capability_gap_id"] == gap.id


def test_repeated_observations_and_need_are_idempotent(db):
    signal = _observation(db, "A business needs recurring access to ingredient X.", "obs-g")
    args = {
        "object_description": "ingredient X",
        "desired_outcome": "receive acceptable ingredient X weekly",
        "unresolved_questions": [],
        "sufficient": True,
    }
    first = demand_understanding.understand(db, [signal.id], **args)
    second = demand_understanding.understand(db, [signal.id], **args)
    assert first.inferred_need_id == second.inferred_need_id
    assert db.query(models.SubstrateEntity).filter_by(entity_type="need").count() == 1
    assert db.query(models.WorldEvent).filter_by(event_type="demand_understood").count() == 1


def test_sqlite_reopen_preserves_demand_to_capability_gap(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'demand.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    run_migrations(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        adequate_signal = _authorized_fixture_observation(
            session,
            when=datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc),
            observation_id="sqlite-adequate-record",
        )
        adequate_result = demand_understanding.understand(
            session,
            [adequate_signal.id],
            object_description="a bounded scholarly estimate",
            desired_outcome="obtain a cited estimate",
            unresolved_questions=[],
            sufficient=True,
        )
        adequate_match = demand_understanding.search_existing_capabilities(
            session,
            adequate_result,
            requirement_id="scholarly_evidence",
            required_evidence_type="scholarly_metadata",
        )
        assert adequate_match["matched_sources"]
        assert adequate_match["capability_gap_id"] is None
        assert session.query(models.ResearchQuestion).count() == 0

        insufficient_signal = _authorized_fixture_observation(
            session,
            when=datetime(2026, 9, 27, 10, 0, tzinfo=timezone.utc),
            observation_id="sqlite-insufficient-record",
            authorized_at=datetime(2026, 9, 28, 13, 0, tzinfo=timezone.utc),
        )
        insufficient_result = demand_understanding.understand(
            session,
            [insufficient_signal.id],
            object_description="a local postharvest observation",
            desired_outcome="obtain crop loss evidence",
            unresolved_questions=[],
            sufficient=True,
        )
        insufficient_match = demand_understanding.search_existing_capabilities(
            session,
            insufficient_result,
            requirement_id="primary_agriculture_observation",
            required_evidence_type="primary_agriculture_observation",
            geographic_scope="Nepal",
            population_scope="smallholder farmers",
        )
        gap = session.get(models.ForgeCapability, insufficient_match["capability_gap_id"])
        gap_data = json.loads(gap.attributes)["capability_discovery"]
        ids = {
            "adequate_signal": adequate_signal.id,
            "adequate_need": adequate_result.inferred_need_id,
            "insufficient_signal": insufficient_signal.id,
            "insufficient_need": insufficient_result.inferred_need_id,
            "gap": gap.id,
            "gap_event": gap_data["search_result"]["event_id"],
            "gap_evidence": gap_data["search_result"]["evidence_id"],
        }
        assert insufficient_match["research_eligible"] is True
    with factory() as reopened:
        assert reopened.get(models.Signal, ids["adequate_signal"]) is not None
        assert reopened.get(models.Signal, ids["insufficient_signal"]) is not None
        assert reopened.get(models.SubstrateEntity, ids["adequate_need"]).entity_type == "need"
        assert reopened.get(models.SubstrateEntity, ids["insufficient_need"]).entity_type == "need"
        for signal_id in (ids["adequate_signal"], ids["insufficient_signal"]):
            persisted_signal = reopened.get(models.Signal, signal_id)
            provenance = json.loads(persisted_signal.provenance)
            assert persisted_signal.published_at is not None
            assert persisted_signal.retrieved_at is not None
            assert provenance["source_registry_id"] == "crossref-public-works-metadata"
            assert provenance["source_reference"] == "https://api.crossref.org/works"
            assert provenance["authorization_reserved_at"]
            assert provenance["ingested_at"]
        source_entry = source_clearance_registry.clearance_for_url(
            "https://api.crossref.org/works"
        )
        assert source_entry is not None
        assert source_entry.registry_id == "crossref-public-works-metadata"
        persisted_gap = reopened.get(models.ForgeCapability, ids["gap"])
        persisted_gap_data = json.loads(persisted_gap.attributes)["capability_discovery"]
        assert reopened.get(models.WorldEvent, ids["gap_event"]) is not None
        assert reopened.get(models.Evidence, ids["gap_evidence"]).support_level == "possible"
        assert persisted_gap_data["search_result"]["registered_sources_considered"] == []
        assert reopened.get(
            models.SourceFetchGate, "crossref-public-works-metadata"
        ) is not None
        assert reopened.query(models.WorldRelation).filter_by(
            relation_type="derived_from"
        ).count() == 2
        assert reopened.query(models.Evidence).filter(
            models.Evidence.subject_id.in_(
                (ids["adequate_need"], ids["insufficient_need"])
            ),
            models.Evidence.support_level == "hypothesized",
        ).count() == 2
        assert reopened.query(models.ResearchTask).count() == 0
        observation_evidence = reopened.query(models.Evidence).filter(
            models.Evidence.idempotency_key.like("demand-observation-evidence:%")
        ).all()
        assert len(observation_evidence) == 2
        assert all(
            "crossref-public-works-metadata"
            in json.loads(row.provenance)["metadata"]["provenance"]["source_registry_id"]
            for row in observation_evidence
        )
        assert reopened.query(models.Opportunity).count() == 0
        assert reopened.query(models.Decision).count() == 0
        print(
            json.dumps(
                {
                    **ids,
                    "research_questions": reopened.query(models.ResearchQuestion).count(),
                    "research_tasks": reopened.query(models.ResearchTask).count(),
                    "opportunities": reopened.query(models.Opportunity).count(),
                    "decisions": reopened.query(models.Decision).count(),
                },
                sort_keys=True,
            )
        )
    engine.dispose()
