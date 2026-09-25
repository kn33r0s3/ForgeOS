"""The operational action/outcome/learning rows remain authoritative."""

from datetime import timedelta
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.migrations import run_migrations
from app.services import world_graph


def _attempt(db, *, experiment_id=None, policy="ALLOW", approved=True, started=True, status="SUCCEEDED"):
    now = models.utcnow()
    row = models.Action(
        experiment_id=experiment_id,
        action_type="research",
        objective="Contact an authorized participant",
        status=status if started else "PROPOSED",
        policy_result=policy,
        policy_reason="test authorization record",
        approved_at=now if approved else None,
        started_at=now if started else None,
        completed_at=now + timedelta(seconds=1) if status in {"SUCCEEDED", "FAILED", "VERIFIED"} and started else None,
        verification_state="UNVERIFIED",
        adapter_name="test-adapter",
    )
    db.add(row)
    db.flush()
    return row


def test_action_outcome_learning_adapter_preserves_sources_and_is_idempotent(db):
    experiment = models.Experiment(
        action="Conduct a research interview",
        hypothesis="The participant has encountered this problem.",
        expected_result="A response is recorded.",
        authorization_status="allowed",
        authorized_at=models.utcnow(),
    )
    db.add(experiment)
    db.flush()
    action = _attempt(db, experiment_id=experiment.id, policy="REQUIRE_APPROVAL", approved=True)
    outcome = models.Outcome(
        action_id=action.id,
        experiment_id=experiment.id,
        outcome_type="ACTUAL_RESPONSE",
        qualitative_result="The participant confirmed the problem.",
        source="human_interview",
        verification_state="REPORTED",
        data_scope="REAL",
    )
    db.add(outcome)
    db.flush()
    learning = models.LearningEvent(
        experiment_id=experiment.id,
        prediction="The participant reports the problem.",
        actual="The participant confirmed the problem.",
        lesson="One report is evidence but does not establish prevalence.",
        data_scope="REAL",
    )
    db.add(learning)
    db.commit()

    first = world_graph.sync_action_outcome_learning_path(db)
    assert first == {"entities_created": 3, "relations_created": 2, "events_created": 4, "ambiguous_links": 0}

    action_entity = world_graph.find_canonical_entity(db, "action", action.id)
    outcome_entity = world_graph.find_canonical_entity(db, "outcome", outcome.id)
    learning_entity = world_graph.find_canonical_entity(db, "learning_event", learning.id)
    assert action_entity.source_system == "actions"
    assert action_entity.source_id == str(action.id)
    assert json.loads(action_entity.identity_provenance)["source_id"] == action.id
    assert outcome_entity.source_system == "outcomes"
    assert learning_entity.source_system == "learning_events"

    edges = db.query(models.WorldRelation).order_by(models.WorldRelation.id).all()
    assert [(edge.from_entity_id, edge.to_entity_id) for edge in edges] == [
        (outcome_entity.id, action_entity.id),
        (learning_entity.id, outcome_entity.id),
    ]
    assert json.loads(edges[0].attributes)["link_basis"] == "outcome.action_id"
    assert json.loads(edges[1].attributes)["link_basis"] == "shared_experiment_id_and_data_scope"
    assert all(edge.truth_state == "hypothesized" for edge in edges)

    events_before = db.query(models.WorldEvent).count()
    relations_before = db.query(models.WorldRelation).count()
    second = world_graph.sync_action_outcome_learning_path(db)
    assert second == {"entities_created": 0, "relations_created": 0, "events_created": 0, "ambiguous_links": 0}
    assert db.query(models.WorldEvent).count() == events_before
    assert db.query(models.WorldRelation).count() == relations_before

    action.status = "VERIFIED"
    db.commit()
    refreshed = world_graph.sync_action_outcome_learning_path(db)
    assert refreshed["events_created"] == 1
    status_event = db.query(models.WorldEvent).filter_by(
        idempotency_key=f"action-attempt-status:actions:{action.id}:VERIFIED"
    ).one()
    status_payload = json.loads(status_event.payload)
    assert status_payload["source_id"] == action.id
    assert status_payload["from_status"] == "SUCCEEDED"

    outcome.outcome_type = "QUALITATIVE"
    db.commit()
    world_graph.sync_action_outcome_learning_path(db)
    refreshed_outcome = world_graph.find_canonical_entity(db, "outcome", outcome.id)
    assert refreshed_outcome.display_name == f"QUALITATIVE #{outcome.id}"
    source_refresh = db.query(models.WorldEvent).filter_by(
        event_type="entity_source_refreshed", entity_id=refreshed_outcome.id
    ).one()
    assert "display_name" in json.loads(source_refresh.payload)["changed_fields"]


def test_unstarted_or_unapproved_operational_actions_are_not_substrate_attempts(db):
    proposed = _attempt(db, policy="ALLOW", started=False)
    approval_missing = _attempt(db, policy="REQUIRE_APPROVAL", approved=False, started=True)
    blocked = _attempt(db, policy="BLOCK", approved=False, started=True)
    db.commit()

    result = world_graph.sync_action_outcome_learning_path(db)
    assert result["entities_created"] == 0
    assert db.query(models.SubstrateEntity).filter_by(entity_type="action").count() == 0
    assert db.query(models.WorldEvent).filter(
        models.WorldEvent.event_type == "action_attempt_started"
    ).count() == 0
    for source in (proposed, approval_missing, blocked):
        with pytest.raises(world_graph.SubstrateError, match="not a substrate Action attempt"):
            world_graph.ensure_canonical_entity(db, "action", source.id)


def test_ambiguous_legacy_links_are_not_guessed_and_scope_must_match(db):
    experiment = models.Experiment(action="Run a bounded participant test")
    db.add(experiment)
    db.flush()
    first = _attempt(db, experiment_id=experiment.id)
    _attempt(db, experiment_id=experiment.id)
    outcome = models.Outcome(
        experiment_id=experiment.id,
        outcome_type="ACTUAL_RESPONSE",
        qualitative_result="A response was observed.",
        source="manual",
        data_scope="REAL",
    )
    db.add(outcome)
    db.flush()
    learning = models.LearningEvent(
        experiment_id=experiment.id,
        prediction="Expected a response.",
        actual="A response was observed.",
        lesson="Record the observation for later comparison.",
        data_scope="SANDBOX",
    )
    db.add(learning)
    db.commit()

    result = world_graph.sync_action_outcome_learning_path(db)
    assert result["ambiguous_links"] == 1
    assert db.query(models.WorldRelation).count() == 0
    assert world_graph.find_canonical_entity(db, "action", first.id) is not None
    assert world_graph.find_canonical_entity(db, "outcome", outcome.id) is not None
    assert world_graph.find_canonical_entity(db, "learning_event", learning.id) is not None


def test_experiment_is_a_deduplicated_action_fallback_when_actions_row_is_absent(db):
    now = models.utcnow()
    experiment = models.Experiment(
        action="Interview a participant",
        action_type="customer_interview",
        authorization_status="allowed",
        authorized_at=now,
        status="completed",
        execution_status="completed",
        started_at=now,
        completed_at=now + timedelta(minutes=2),
    )
    db.add(experiment)
    db.flush()
    outcome = models.Outcome(
        experiment_id=experiment.id,
        outcome_type="ACTUAL_RESPONSE",
        qualitative_result="The participant described the issue.",
        source="human_interview",
        data_scope="REAL",
    )
    learning = models.LearningEvent(
        experiment_id=experiment.id,
        prediction="The participant encounters the issue.",
        actual="The participant described the issue.",
        lesson="A report exists, while broader prevalence remains unknown.",
        data_scope="REAL",
    )
    db.add_all([outcome, learning])
    db.commit()

    first = world_graph.sync_action_outcome_learning_path(db)
    assert first == {"entities_created": 3, "relations_created": 2, "events_created": 4, "ambiguous_links": 0}
    experiment_action = world_graph.find_canonical_entity(
        db, "action", experiment.id, source_system="experiments"
    )
    assert experiment_action is not None
    assert experiment_action.source_system == "experiments"
    assert world_graph.find_canonical_entity(db, "action", experiment.id) is None

    action_record = _attempt(
        db,
        experiment_id=experiment.id,
        policy="ALLOW",
        approved=False,
        started=True,
        status="SUCCEEDED",
    )
    db.commit()
    second = world_graph.sync_action_outcome_learning_path(db)
    assert second == {"entities_created": 0, "relations_created": 0, "events_created": 2, "ambiguous_links": 0}
    assert world_graph.find_canonical_entity(
        db, "action", experiment.id, source_system="experiments"
    ).id == experiment_action.id
    assert world_graph.find_canonical_entity(db, "action", action_record.id) is None
    assert db.query(models.WorldRelation).count() == 2


def test_action_outcome_learning_projection_survives_restart_and_repeated_migration(tmp_path):
    path = tmp_path / "operational-adapter.sqlite"
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    run_migrations(engine)
    Session = sessionmaker(bind=engine, autoflush=False)

    with Session() as before_restart:
        experiment = models.Experiment(action="Run a source-backed action")
        before_restart.add(experiment)
        before_restart.flush()
        action = _attempt(before_restart, experiment_id=experiment.id)
        outcome = models.Outcome(
            action_id=action.id,
            experiment_id=experiment.id,
            outcome_type="ACTUAL_RESPONSE",
            qualitative_result="A response was recorded.",
            source="manual",
            data_scope="REAL",
        )
        before_restart.add(outcome)
        before_restart.flush()
        learning = models.LearningEvent(
            experiment_id=experiment.id,
            prediction="A response will be recorded.",
            actual="A response was recorded.",
            lesson="Keep the observation and its source link.",
            data_scope="REAL",
        )
        before_restart.add(learning)
        before_restart.commit()
        first = world_graph.sync_action_outcome_learning_path(before_restart)
        before_restart.commit()
        assert first["entities_created"] == 3
        assert first["relations_created"] == 2
    engine.dispose()

    engine = create_engine(f"sqlite:///{path}")
    assert run_migrations(engine) == []
    with sessionmaker(bind=engine, autoflush=False)() as after_restart:
        second = world_graph.sync_action_outcome_learning_path(after_restart)
        after_restart.commit()
        assert second == {"entities_created": 0, "relations_created": 0, "events_created": 0, "ambiguous_links": 0}
        source_action = after_restart.query(models.Action).one()
        source_outcome = after_restart.query(models.Outcome).one()
        source_learning = after_restart.query(models.LearningEvent).one()
        action_entity = world_graph.find_canonical_entity(after_restart, "action", source_action.id)
        outcome_entity = world_graph.find_canonical_entity(after_restart, "outcome", source_outcome.id)
        learning_entity = world_graph.find_canonical_entity(after_restart, "learning_event", source_learning.id)
        assert action_entity.source_id == str(source_action.id)
        assert outcome_entity.source_id == str(source_outcome.id)
        assert learning_entity.source_id == str(source_learning.id)
        assert after_restart.query(models.WorldRelation).count() == 2
        assert after_restart.query(models.WorldEvent).filter_by(
            event_type="outcome_recorded",
            idempotency_key=f"outcome-recorded:{source_outcome.id}",
        ).count() == 1
    engine.dispose()


def test_canonical_cycle_runs_the_registered_substrate_adapters(db):
    from app.services import forge_loop

    signal = models.Signal(
        source="manual",
        source_type="manual",
        title="Observed workflow interruption",
        content="A local operator reports repeated delays while coordinating an everyday service.",
    )
    db.add(signal)
    action = _attempt(db)
    outcome = models.Outcome(
        action_id=action.id,
        outcome_type="ACTUAL_RESPONSE",
        qualitative_result="A human response was recorded.",
        source="manual",
        data_scope="REAL",
    )
    db.add(outcome)
    db.add(models.LearningEvent(
        prediction="A response will be recorded.",
        actual="A human response was recorded.",
        lesson="The response is recorded without inferring broader demand.",
        data_scope="REAL",
    ))
    provider = models.Provider(
        name="Cycle provider",
        country="Nepal",
        verification_status="verified",
        public_visible=True,
    )
    db.add(provider)
    db.flush()
    listing = models.ServiceListing(
        provider_id=provider.id,
        title="Cycle service",
        description="An existing service listing.",
        public_visible=True,
        is_active=True,
    )
    db.add(listing)
    decision = models.Decision(
        title="Research a repeated interruption",
        rationale="The claim is not sufficient for an action yet.",
    )
    db.add(decision)
    db.flush()
    claim = models.Claim(
        statement="Operators report repeated workflow interruptions.",
        normalized_statement="operators report repeated workflow interruptions",
        decision_id=decision.id,
    )
    db.add(claim)
    db.flush()
    research_question = models.ResearchQuestion(
        question="What evidence would verify those interruptions?",
        source_claim_id=claim.id,
    )
    domain_record = models.DomainRecord(
        kind="job",
        title="Cycle job record",
        detail="An existing domain record.",
        close_token_hash="test-token-hash",
    )
    db.add_all([research_question, domain_record])
    db.commit()

    summary = forge_loop.run_cycle(db)

    assert "substrate_adapters" not in summary["stage_errors"]
    assert summary["substrate_entities_created"] >= 4
    assert summary["substrate_relations_created"] >= 1
    assert summary["substrate_events_created"] >= 3
    assert summary["substrate_public_services_projected"] >= 1
    assert summary["substrate_evidence_created"] == 1
    assert summary["substrate_capabilities_created"] > 0
    assert summary["substrate_capability_events_created"] > 0
    assert summary["substrate_legacy_records_projected"] >= 4
    assert world_graph.find_canonical_entity(db, "signal", signal.id) is not None
    assert world_graph.find_canonical_entity(db, "action", action.id) is not None
    assert world_graph.find_canonical_entity(db, "outcome", outcome.id) is not None
    assert world_graph.find_canonical_entity(db, "provider", provider.id) is not None
    assert world_graph.find_canonical_entity(db, "service_listing", listing.id) is not None
    assert world_graph.find_canonical_entity(db, "claim", claim.id) is not None
    assert world_graph.find_canonical_entity(db, "research_question", research_question.id) is not None
    assert world_graph.find_canonical_entity(db, "domain_record", domain_record.id) is not None
    assert world_graph.find_canonical_entity(db, "decision", decision.id) is not None
    assert db.query(models.ForgeCapability).filter_by(status="proposed").count() > 0
