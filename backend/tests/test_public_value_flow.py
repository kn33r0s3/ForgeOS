import asyncio
import sqlite3
import time

import pytest
from fastapi import BackgroundTasks
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from app import models, schemas
from app.api.analyze import analyze_idea
from app.database import Base, get_db
from app.main import app
from app.migrations import run_migrations
from app.services import collector_runner, research_task_engine
from app.services.collectors.base import SourceCollector


@pytest.fixture
def client_with_db(db):
    def override_get_db():
        try:
            yield db
        finally:
            db.rollback()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app, raise_server_exceptions=True)
    yield client
    app.dependency_overrides.clear()
    client.close()


def test_public_problem_submission_starts_real_research_and_defers_opportunity(
    client_with_db, db, monkeypatch
):
    class CrossrefFixture(SourceCollector):
        source_name = "crossref"

        def collect(self, query, *, authorization=None):
            assert authorization is not None
            return [
                {
                    "content": "Crossref metadata record: Repair scheduling evidence study.",
                    "title": "Repair scheduling evidence study",
                    "canonical_url": "https://doi.org/10.1234/repair.1",
                    "external_id": "10.1234/repair.1",
                    "timestamp": "2026-09-27T12:00:00+00:00",
                    "published_at": "2025-04-01T00:00:00+00:00",
                    "retrieved_at": "2026-09-27T12:00:00+00:00",
                    "provenance": {"metadata_only": True, "query": query},
                    "metadata": {"source_type": "external", "collection_status": "collected"},
                }
            ]

    monkeypatch.setitem(collector_runner.COLLECTORS, "crossref", CrossrefFixture)
    response = client_with_db.post(
        "/analyze",
        json={
            "idea": "Independent repair shops lose hours every week manually explaining appointment status to customers."
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["opportunity_id"] is None
    assert payload["research_question_id"] is not None
    assert payload["research_task_ids"]
    assert payload["research_status"] == "research_started"
    assert payload["evidence_count"] == 0
    assert payload["research_sources"] == []
    progress = client_with_db.get(payload["research_status_url"])
    assert progress.status_code == 200, progress.text
    progress_payload = progress.json()
    assert progress_payload["phase"] == "blocked"
    assert progress_payload["research_status"] == "research_terminal_unresolved"
    assert progress_payload["research_plan"]["terminal_reason"] == (
        "one_or_more_requirements_remain_unresolved_under_current_source_clearances"
    )
    assert len(progress_payload["research_plan"]["requirements"]) == 5
    assert progress_payload["research_plan"]["requirements"][0]["status"] == "satisfied"
    assert progress_payload["research_sources"][0]["url"] == "https://doi.org/10.1234/repair.1"
    assert any(task["status"] == "completed" for task in progress_payload["tasks"])
    assert progress_payload["evidence_count"] == 1
    assert "repair" in payload["problem"].lower()
    assert payload["unknowns"]
    assert any("willingness to pay" in item.lower() for item in payload["unknowns"])
    assert db.query(models.Signal).count() >= 1
    assert db.query(models.ResearchQuestion).filter_by(id=payload["research_question_id"]).count() == 1
    assert db.query(models.ResearchTask).filter(models.ResearchTask.question_id == payload["research_question_id"]).count() >= 1
    assert db.query(models.Opportunity).count() == 0


def test_public_problem_submission_rejects_empty_input(client_with_db):
    response = client_with_db.post("/analyze", json={"idea": "   "})
    assert response.status_code == 422


def test_api_root_uses_hami_product_identity(client_with_db):
    response = client_with_db.get("/")

    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Hami"


def test_analyze_acknowledges_before_the_collector_background_task(db, monkeypatch):
    collector_calls = []

    def record_background_collection(database, task):
        collector_calls.append(task.id)

    monkeypatch.setattr(
        "app.api.analyze.collector_runner.execute_task",
        record_background_collection,
    )
    background_tasks = BackgroundTasks()
    started_at = time.perf_counter()
    response = analyze_idea(
        schemas.AnalyzeRequest(
            idea="Developer timing fixture only: synthetic problem for background handoff."
        ),
        background_tasks,
        db,
    )
    acknowledgement_ms = (time.perf_counter() - started_at) * 1000

    assert acknowledgement_ms < 500
    assert response.research_status == "research_started"
    assert response.research_status_url == (
        f"/analyze/{response.research_question_id}/status"
    )
    assert response.evidence_count == 0
    assert response.research_sources == []
    assert collector_calls == []
    assert len(background_tasks.tasks) == 1

    asyncio.run(background_tasks())

    assert collector_calls == [background_tasks.tasks[0].args[0]]


@pytest.mark.parametrize(
    ("task_status", "expected_phase"),
    [
        ("planned", "queued"),
        ("running", "researching"),
        ("completed", "awaiting_evidence"),
        ("needs_research", "awaiting_evidence"),
        ("failed", "blocked"),
    ],
)
def test_research_status_distinguishes_queued_from_running_work(
    client_with_db, db, task_status, expected_phase
):
    question = models.ResearchQuestion(question=f"Status fixture: {task_status}")
    db.add(question)
    db.commit()
    task = models.ResearchTask(
        question_id=question.id,
        source="crossref",
        query="Developer status fixture only",
        status=task_status,
    )
    db.add(task)
    db.commit()

    response = client_with_db.get(f"/analyze/{question.id}/status")

    assert response.status_code == 200, response.text
    assert response.json()["phase"] == expected_phase
    assert response.json()["tasks"][0]["status"] == task_status
    assert response.json()["evidence_count"] == 0


def test_analyze_does_not_report_completed_for_mixed_empty_task_results(
    client_with_db, db, monkeypatch
):
    def plan_with_mixed_results(database, question):
        completed = research_task_engine.create_task(
            database,
            question_id=question.id,
            source="crossref",
            query="completed but empty",
            objective="Check one subquestion.",
        )
        failed = research_task_engine.create_task(
            database,
            question_id=question.id,
            source="crossref",
            query="failed source",
            objective="Check another subquestion.",
        )
        completed.status = "completed"
        completed.evidence_ids = ""
        failed.status = "failed"
        database.commit()
        return [completed, failed]

    monkeypatch.setattr(
        "app.api.analyze.research_planner.plan_tasks_for_question",
        plan_with_mixed_results,
    )
    monkeypatch.setattr(
        "app.api.analyze.collector_runner.run_pending_tasks",
        lambda database, limit: [
            {"status": "completed", "evidence_found": 0},
            {"status": "failed", "reason": "source unavailable"},
        ],
    )

    response = client_with_db.post(
        "/analyze",
        json={"idea": "Does a public service reduce crop storage losses?"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["evidence_count"] == 0
    assert payload["research_status"] == "research_failed"


def test_analyze_requires_persisted_evidence_before_source_collection_can_complete(
    client_with_db, db, monkeypatch
):
    def plan_with_stale_evidence_reference(database, question):
        task = research_task_engine.create_task(
            database,
            question_id=question.id,
            source="crossref",
            query="completed task with a stale evidence reference",
            objective="Check that its evidence still exists.",
        )
        task.status = "completed"
        task.evidence_ids = "999999"
        database.commit()
        return [task]

    monkeypatch.setattr(
        "app.api.analyze.research_planner.plan_tasks_for_question",
        plan_with_stale_evidence_reference,
    )
    monkeypatch.setattr(
        "app.api.analyze.collector_runner.run_pending_tasks",
        lambda database, limit: [],
    )

    response = client_with_db.post(
        "/analyze",
        json={"idea": "Could an unfamiliar question reveal a recurring unmet need?"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["research_status"] == "research_needs_evidence"
    assert payload["evidence_count"] == 0
    assert "No external research evidence" in payload["unknowns"][0]


def test_public_provider_and_service_visibility_requires_verified_status(client_with_db, db):
    unverified = models.Provider(
        name="Unverified provider",
        category="Service",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="unverified",
    )
    verified = models.Provider(
        name="Verified provider",
        category="Service",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    db.add_all([unverified, verified])
    db.flush()
    db.add(
        models.ServiceListing(
            provider_id=unverified.id,
            title="Unverified service",
            description="Should not appear publicly",
            price_from="1200",
            public_visible=True,
            is_active=True,
        )
    )
    db.add(
        models.ServiceListing(
            provider_id=verified.id,
            title="Verified service",
            description="Should appear publicly",
            price_from="1500",
            public_visible=True,
            is_active=True,
        )
    )
    db.commit()

    provider_response = client_with_db.get("/public/providers")
    assert provider_response.status_code == 200
    provider_ids = {row["id"] for row in provider_response.json()}
    assert verified.id in provider_ids
    assert unverified.id not in provider_ids

    service_response = client_with_db.get("/public/services")
    assert service_response.status_code == 200
    service_payload = service_response.json()
    service_ids = {row["id"] for row in service_payload}
    assert any(row["provider_id"] == verified.id for row in service_payload)
    assert all(row["provider_id"] != unverified.id for row in service_payload)


def test_public_booking_requests_are_rejected_for_unverified_or_non_public_providers(client_with_db, db):
    provider = models.Provider(
        name="Provider",
        category="Service",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="unverified",
    )
    db.add(provider)
    db.commit()

    blocked = client_with_db.post(
        "/public/booking-requests",
        json={
            "provider_id": provider.id,
            "requester_name": "Asha",
            "requester_phone": "9800000001",
            "requester_email": "asha@example.com",
            "requested_service": "Repair",
        },
    )
    assert blocked.status_code == 404
    assert db.query(models.Outcome).count() == 0


def test_public_booking_enters_our_outcome_record_without_requester_pii(client_with_db, db):
    provider = models.Provider(
        name="Verified provider",
        category="Repair",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    db.add(provider)
    db.commit()
    created = client_with_db.post(
        "/public/booking-requests",
        json={
            "provider_id": provider.id,
            "requester_name": "Asha Shah",
            "requester_phone": "9800000001",
            "requester_email": "asha@example.com",
            "requested_service": "Refrigerator repair",
            "notes": "Needs same-day visit.",
        },
    )
    assert created.status_code == 200, created.text
    outcome = db.query(models.Outcome).one()
    assert outcome.source == "booking_request"
    assert outcome.outcome_type == "QUALITATIVE"
    assert outcome.success is None
    assert outcome.actual_value is None
    text = f"{outcome.qualitative_result} {outcome.notes}"
    assert "Asha" not in text
    assert "9800000001" not in text
    assert "asha@example.com" not in text
    assert "same-day" not in text


def test_domain_record_is_ours_and_closes_into_an_outcome(client_with_db, db):
    created = client_with_db.post(
        "/public/domain",
        json={"kind": "job", "title": "Evening shop helper", "detail": "Need someone in Kathmandu for four evenings.", "city": "Kathmandu"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert "close_token" in body
    listed = client_with_db.get("/public/domain", params={"q": "shop helper"})
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == body["id"]
    assert "close_token" not in listed.json()[0]
    assert "close_token_hash" not in listed.json()[0]

    denied = client_with_db.post(
        f"/public/domain/{body['id']}/close",
        json={"close_token": "nope", "result": "withdrawn", "note": "Not this token"},
    )
    assert denied.status_code == 403

    unpaid = client_with_db.post(
        f"/public/domain/{body['id']}/close",
        json={"close_token": body["close_token"], "result": "paid", "note": "They paid me"},
    )
    assert unpaid.status_code == 422

    closed = client_with_db.post(
        f"/public/domain/{body['id']}/close",
        json={"close_token": body["close_token"], "result": "paid", "note": "Cash received for four evenings", "amount_npr": 2000},
    )
    assert closed.status_code == 200, closed.text
    assert client_with_db.get("/public/domain").json() == []
    outcome = db.query(models.Outcome).filter(models.Outcome.source == "domain_record", models.Outcome.success.is_(True)).one()
    assert outcome.actual_value == 2000
    assert outcome.unit == "NPR"
    assert "Cash received for four evenings" in outcome.qualitative_result


def test_public_connection_responses_are_idempotent_and_not_acceptance(client_with_db, db):
    provider = models.Provider(
        name="Repair response provider",
        category="Repair",
        country="Nepal",
        city="Kathmandu",
        summary="Repair response service",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    db.add(provider)
    db.flush()
    db.add(models.ServiceListing(
        provider_id=provider.id,
        title="Repair response service",
        description="Repair response availability",
        public_visible=True,
        is_active=True,
    ))
    db.commit()
    created = client_with_db.post(
        "/public/domain",
        json={"kind": "job", "title": "Repair response test", "detail": "Need a repair response.", "city": "Kathmandu"},
    )
    assert created.status_code == 200
    body = created.json()
    connection = models.NetworkConnection(
        left_kind="domain_record",
        left_id=body["id"],
        right_kind="provider",
        right_id=provider.id,
        state="proposed",
        reason="recorded candidate",
        agreement_gap="terms are not accepted",
        public_visible=True,
    )
    db.add(connection)
    db.commit()
    db.refresh(connection)

    first = client_with_db.post(
        f"/public/domain/{body['id']}/connections/{connection.id}/response",
        json={"close_token": body["close_token"], "note": "Asked for availability."},
    )
    second = client_with_db.post(
        f"/public/domain/{body['id']}/connections/{connection.id}/response",
        json={"close_token": body["close_token"], "note": "Shared the requested dates."},
    )
    duplicate = client_with_db.post(
        f"/public/domain/{body['id']}/connections/{connection.id}/response",
        json={"close_token": body["close_token"], "note": "Shared the requested dates."},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert duplicate.status_code == 200
    assert connection.state == "proposed"
    assert db.query(models.Outcome).filter(
        models.Outcome.notes.like(f"idempotency:network-connection:{connection.id}:response:%")
    ).count() == 2
    assert db.query(models.Outcome).filter(
        models.Outcome.notes.like(f"idempotency:network-connection:{connection.id}:paid%")
    ).count() == 0
    assert second.json()["latest_response"].endswith("Shared the requested dates.")

    denied = client_with_db.post(
        f"/public/domain/{body['id']}/connections/{connection.id}/response",
        json={"close_token": "wrong", "note": "Should be rejected."},
    )
    assert denied.status_code == 403

    listed = client_with_db.get("/public/connections")
    assert listed.status_code == 200
    assert listed.json()[0]["latest_response"].endswith("Shared the requested dates.")
    matches = client_with_db.get("/public/matches")
    assert matches.status_code == 200
    candidate = next(
        item for item in matches.json()[0]["candidates"]
        if item["connection_id"] == connection.id
    )
    assert candidate["latest_response"].endswith("Shared the requested dates.")


def test_public_booking_status_does_not_leak_requester_pii(client_with_db, db):
    provider = models.Provider(
        name="Verified provider",
        category="Service",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    db.add(provider)
    db.commit()
    request = models.BookingRequest(
        provider_id=provider.id,
        requester_name="Asha Shah",
        requester_phone="9800000001",
        requester_email="asha@example.com",
        requested_service="Plumbing",
        status="pending",
        notes="Needs same-day visit.",
    )
    db.add(request)
    db.commit()
    db.refresh(request)

    response = client_with_db.get(f"/public/booking-requests/{request.id}")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == request.id
    assert payload["requested_service"] == "Plumbing"
    assert "requester_name" not in payload
    assert "requester_phone" not in payload
    assert "requester_email" not in payload
    assert "notes" not in payload


def test_approved_actions_onboard_verify_and_publish_without_auto_public(client_with_db, db):
    from app.services import action_engine

    candidate = action_engine.propose_action(
        db,
        objective="Record a named repair shop as a non-public candidate",
        action_type="provider_candidate",
        parameters={"name": "Hill Repair", "category": "Repair", "city": "Kathmandu"},
    )
    assert candidate.policy_result == "ALLOW"
    executed = action_engine.start_and_execute_action(db, candidate.id)
    assert executed.status == "SUCCEEDED"
    provider_id = int(executed.external_ref)
    hidden = client_with_db.get("/public/providers")
    assert hidden.status_code == 200
    assert hidden.json() == []

    verify = action_engine.propose_action(
        db,
        objective="Verify Hill Repair from a cited registration record",
        action_type="provider_verify",
        parameters={
            "provider_id": provider_id,
            "evidence_type": "registration",
            "evidence_reference": "Kathmandu ward office file 2026-14",
            "reviewed_by": "operator",
        },
    )
    assert verify.status == "APPROVAL_REQUIRED"
    blocked = action_engine.start_and_execute_action(db, verify.id)
    assert blocked.status == "APPROVAL_REQUIRED"
    action_engine.approve_action(db, verify.id)
    verified = action_engine.start_and_execute_action(db, verify.id)
    assert verified.status == "SUCCEEDED"
    assert client_with_db.get("/public/providers").json() == []

    publish = action_engine.propose_action(
        db,
        objective="Publish the verified shop and its stated repair listing",
        action_type="provider_publish",
        parameters={
            "provider_id": provider_id,
            "service_title": "Refrigerator repair",
            "service_description": "Home visit when a fridge will not cool",
            "availability_status": "weekdays",
            "price_from": "1500",
        },
    )
    action_engine.approve_action(db, publish.id)
    published = action_engine.start_and_execute_action(db, publish.id)
    assert published.status == "SUCCEEDED"
    providers = client_with_db.get("/public/providers", params={"q": "refrigerator"})
    services = client_with_db.get("/public/services")
    assert [row["id"] for row in providers.json()] == [provider_id]
    assert services.json()[0]["title"] == "Refrigerator repair"
    assert "phone" not in services.json()[0]


def test_public_discoveries_are_sourced_observations_without_internal_scores(client_with_db, db):
    visible = models.Signal(
        source="rss",
        source_type="external",
        content="A Kathmandu workshop posted a stated repair price.",
        title="Workshop note",
        canonical_url="https://example.com/workshop",
        importance_score=99,
        quality_score=88,
    )
    hidden = models.Signal(
        source="manual",
        source_type="manual",
        content="Operator note that must stay internal.",
        title="Hidden",
        canonical_url="https://example.com/hidden",
    )
    db.add_all([visible, hidden])
    db.commit()
    evidence = models.Evidence(signal_id=visible.id, source="rss", content=visible.content, canonical_url=visible.canonical_url)
    claim = models.Claim(
        statement=visible.content,
        normalized_statement="kathmandu workshop posted a stated repair price",
        epistemic_state="observed",
        confidence=91.0,
    )
    db.add_all([evidence, claim])
    db.commit()
    db.add(models.EvidenceRelationship(evidence_id=evidence.id, claim_id=claim.id, relation_type="derived_from", relation_key=f"{evidence.id}:{claim.id}"))
    db.commit()
    response = client_with_db.get("/public/discoveries")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == claim.id
    assert body[0]["epistemic_state"] == "observed"
    assert body[0]["canonical_url"] == "https://example.com/workshop"
    assert "importance_score" not in body[0]
    assert "quality_score" not in body[0]
    assert "confidence" not in body[0]
    assert "Hidden" not in response.text


def test_public_match_uses_recorded_terms_and_names_unknowns(client_with_db, db):
    provider = models.Provider(
        name="Hill Repair",
        category="Repair",
        city="Kathmandu",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    hidden = models.Provider(
        name="Hidden Repair",
        city="Kathmandu",
        country="Nepal",
        public_visible=False,
        is_active=True,
        verification_status="unverified",
    )
    db.add_all([provider, hidden])
    db.commit()
    db.add(models.ServiceListing(
        provider_id=provider.id,
        title="Refrigerator repair",
        description="Home visit when a fridge will not cool",
        location="Kathmandu",
        availability_status="weekdays",
        public_visible=True,
        is_active=True,
    ))
    need = models.DomainRecord(
        kind="job",
        title="Need refrigerator help",
        detail="Fridge will not cool in Kathmandu",
        city="Kathmandu",
        status="open",
        close_token_hash="test",
    )
    db.add(need)
    db.commit()
    response = client_with_db.get("/public/matches")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    names = [row["name"] for row in body[0]["candidates"]]
    assert "Hill Repair" in names
    assert "Hidden Repair" not in names
    hill = next(row for row in body[0]["candidates"] if row["name"] == "Hill Repair")
    assert hill["kind"] == "provider"
    assert hill["entity_type"] == "provider"
    assert "same city" in hill["reasons"]
    assert "price not stated" in hill["unknowns"]
    assert hill["stated_availability"] == "weekdays"
    assert "score" not in response.text
    assert "confidence" not in response.text
    outside = models.Signal(
        source="rss",
        source_type="external",
        content="A journal notes refrigerator failure rates in city kitchens.",
        title="Refrigerator failure note",
        canonical_url="https://example.com/fridge-note",
    )
    db.add(outside)
    db.commit()
    evidence = models.Evidence(signal_id=outside.id, source="rss", content=outside.content, canonical_url=outside.canonical_url)
    claim = models.Claim(
        statement=outside.content,
        normalized_statement="journal notes refrigerator failure rates",
        epistemic_state="observed",
    )
    db.add_all([evidence, claim])
    db.commit()
    db.add(models.EvidenceRelationship(evidence_id=evidence.id, claim_id=claim.id, relation_type="derived_from", relation_key=f"k-{evidence.id}-{claim.id}"))
    db.commit()
    again = client_with_db.get("/public/matches").json()
    knowledge = [row for row in again[0]["candidates"] if row["kind"] == "knowledge"]
    assert knowledge
    assert knowledge[0]["id"] == claim.id
    assert knowledge[0]["kind"] == "knowledge"
    assert knowledge[0]["entity_type"] == "claim"
    assert "not a verified counterparty" in knowledge[0]["unknowns"]
    assert any(item.startswith("evidence is ") for item in knowledge[0]["unknowns"])


def test_domain_dispute_records_an_event_and_names_a_winner_nowhere(client_with_db, db):
    created = client_with_db.post(
        "/public/domain",
        json={"kind": "trade", "title": "Used pump", "detail": "Working pump in Lalitpur", "stated_price": "8000"},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    closed = client_with_db.post(
        f"/public/domain/{body['id']}/close",
        json={"close_token": body["close_token"], "result": "paid", "note": "Cash handed over", "amount_npr": 8000},
    )
    assert closed.status_code == 200, closed.text
    denied = client_with_db.post(
        f"/public/domain/{body['id']}/dispute",
        json={"close_token": "nope", "note": "The pump was not as described"},
    )
    assert denied.status_code == 403
    disputed = client_with_db.post(
        f"/public/domain/{body['id']}/dispute",
        json={"close_token": body["close_token"], "note": "The pump was not as described"},
    )
    assert disputed.status_code == 200, disputed.text
    events = disputed.json()
    assert events["payments"]
    assert events["disputes"]
    assert "No winner is recorded" in events["disputes"][0]
    assert "8000" in events["payments"][0] or "8,000" in events["payments"][0] or "8000.0" in events["payments"][0]


def test_public_alerts_are_only_recorded_changes(client_with_db, db):
    empty = client_with_db.get("/public/alerts")
    assert empty.status_code == 200
    assert empty.json() == []
    created = client_with_db.post(
        "/public/domain",
        json={"kind": "offer", "title": "Spare filter", "detail": "Unused filter in Bhaktapur"},
    )
    assert created.status_code == 200, created.text
    db.add(models.Outcome(
        outcome_type="QUALITATIVE",
        source="internal",
        qualitative_result="Operator-only note with phone 9800000001",
        data_scope="REAL",
    ))
    db.commit()
    alerts = client_with_db.get("/public/alerts")
    assert alerts.status_code == 200
    body = alerts.json()
    assert len(body) == 1
    assert "Spare filter" in body[0]["text"]
    assert "9800000001" not in alerts.text
    assert "close_token" not in alerts.text


def test_unmatched_need_becomes_a_research_gap_and_not_an_offer(client_with_db, db):
    from app.services import network_connections

    need = models.DomainRecord(
        kind="job",
        title="Need a welder in Biratnagar",
        detail="Gate hinge is broken",
        city="Biratnagar",
        status="open",
        close_token_hash="tok",
    )
    db.add(need)
    db.commit()
    assert network_connections.scan_candidates(db) == []
    question = db.query(models.ResearchQuestion).filter(
        models.ResearchQuestion.question.like("Gap: open job #%")
    ).one()
    assert question.status == "open"
    assert "no recorded counterparty" in question.question
    assert "not an offer" in question.question
    assert db.query(models.Opportunity).count() == 0
    assert db.query(models.Provider).count() == 0
    again = network_connections.record_unmatched_gaps(db)
    assert again == []
    assert db.query(models.ResearchQuestion).count() == 1

    provider = models.Provider(
        name="East Weld",
        city="Biratnagar",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    db.add(provider)
    db.commit()
    db.add(models.ServiceListing(
        provider_id=provider.id,
        title="Welder for a broken gate hinge",
        description="Need a welder in Biratnagar for a gate hinge",
        location="Biratnagar",
        public_visible=True,
        is_active=True,
    ))
    db.commit()
    created = network_connections.scan_candidates(db)
    assert len(created) == 1
    db.refresh(question)
    assert question.status == "closed"
    created[0].state = "failed"
    db.commit()
    reopened = network_connections.record_unmatched_gaps(db)
    assert reopened[0].id == question.id
    assert reopened[0].status == "open"


def test_candidate_connection_cannot_skip_states_or_publish_early(client_with_db, db):
    from app.services import network_connections

    provider = models.Provider(
        name="Hill Repair",
        city="Kathmandu",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    db.add(provider)
    db.commit()
    db.add(models.ServiceListing(
        provider_id=provider.id,
        title="Refrigerator repair",
        description="Home visit",
        location="Kathmandu",
        public_visible=True,
        is_active=True,
    ))
    db.add(models.DomainRecord(
        kind="job",
        title="Need refrigerator help",
        detail="Fridge will not cool",
        city="Kathmandu",
        status="open",
        close_token_hash="tok",
    ))
    db.commit()
    created = network_connections.scan_candidates(db)
    assert len(created) == 1
    assert created[0].state == "candidate"
    assert created[0].public_visible is False
    hypothesis = db.query(models.Opportunity).filter(models.Opportunity.identity_key.like("connection:%")).one()
    assert hypothesis.status == "identified"
    assert hypothesis.estimated_price is None
    assert hypothesis.estimated_revenue is None
    assert "No buyer has been recorded" in hypothesis.target_customer
    assert network_connections.scan_candidates(db) == []
    assert client_with_db.get("/public/connections").json() == []
    skipped = client_with_db.post(f"/forge/connections/{created[0].id}/advance", params={"next_state": "paid"})
    assert skipped.status_code == 409
    bare = client_with_db.post(f"/forge/connections/{created[0].id}/advance", params={"next_state": "evidenced"})
    assert bare.status_code == 409
    missing = client_with_db.post(
        f"/forge/connections/{created[0].id}/advance",
        params={"next_state": "evidenced", "evidence_reference": "https://example.com/not-stored"},
    )
    assert missing.status_code == 409
    db.add(models.Signal(
        source="rss",
        source_type="external",
        content="A stored note about refrigerator repair.",
        title="Stored fridge note",
        canonical_url="https://example.com/fridge-note",
    ))
    db.commit()
    evidenced = client_with_db.post(
        f"/forge/connections/{created[0].id}/advance",
        params={"next_state": "evidenced", "evidence_reference": "https://example.com/fridge-note"},
    )
    assert evidenced.status_code == 200, evidenced.text
    viable = client_with_db.post(f"/forge/connections/{created[0].id}/advance", params={"next_state": "viable"})
    assert viable.status_code == 200, viable.text
    proposed = client_with_db.post(f"/forge/connections/{created[0].id}/advance", params={"next_state": "proposed"})
    assert proposed.status_code == 200, proposed.text
    early = client_with_db.post(f"/forge/connections/{created[0].id}/publish")
    assert early.status_code == 409
    authorized = client_with_db.post(f"/forge/connections/{created[0].id}/advance", params={"next_state": "authorized"})
    assert authorized.status_code == 200
    published = client_with_db.post(f"/forge/connections/{created[0].id}/publish")
    assert published.status_code == 200
    visible = client_with_db.get("/public/connections").json()
    assert visible[0]["state"] == "authorized"
    assert visible[0]["forge_role"] == "introducer"
    assert visible[0]["owns_either_side"] is False
    assert "score" not in client_with_db.get("/public/connections").text
    failed = client_with_db.post(f"/forge/connections/{created[0].id}/advance", params={"next_state": "failed"})
    assert failed.status_code == 200
    again = network_connections.scan_candidates(db)
    assert len(again) == 1
    assert again[0].id != created[0].id


def test_paid_connection_records_an_amount_and_stays_unconfirmed_until_verified(client_with_db, db):
    row = models.NetworkConnection(
        left_kind="domain_record",
        left_id=1,
        right_kind="provider",
        right_id=2,
        state="fulfilled",
        reason="same city",
        agreement_gap="Payment is still unrecorded.",
        public_visible=False,
    )
    db.add(row)
    db.commit()
    missing = client_with_db.post(f"/forge/connections/{row.id}/advance", params={"next_state": "paid"})
    assert missing.status_code == 422
    paid = client_with_db.post(
        f"/forge/connections/{row.id}/advance",
        params={"next_state": "paid", "amount_npr": 2500},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["payment"] == "reported"
    outcome = db.query(models.Outcome).filter(models.Outcome.notes == f"idempotency:network-connection:{row.id}:paid").one()
    assert outcome.actual_value == 2500
    assert outcome.unit == "NPR"
    assert outcome.verification_state == "REPORTED"
    listed = client_with_db.get("/forge/connections").json()
    match = next(item for item in listed if item["id"] == row.id)
    assert isinstance(match["seconds_to_recorded_payment"], int)
    assert match["seconds_to_recorded_payment"] >= 0
    confirmed = client_with_db.post(f"/forge/connections/{row.id}/confirm-payment")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["payment"] == "verified"
    db.refresh(outcome)
    assert outcome.verification_state == "VERIFIED"


def test_public_trust_lists_recorded_payments_without_a_score(client_with_db, db):
    provider = models.Provider(
        name="Hill Repair",
        city="Kathmandu",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    hidden = models.Provider(
        name="Hidden",
        country="Nepal",
        public_visible=False,
        is_active=True,
        verification_status="unverified",
    )
    db.add_all([provider, hidden])
    db.commit()
    hidden_trust = client_with_db.get(f"/public/trust/provider/{hidden.id}")
    assert hidden_trust.status_code == 404
    empty = client_with_db.get(f"/public/trust/provider/{provider.id}")
    assert empty.status_code == 200
    assert empty.json()["unknowns"]
    assert "score" not in empty.text
    connection = models.NetworkConnection(
        left_kind="domain_record",
        left_id=1,
        right_kind="provider",
        right_id=provider.id,
        state="fulfilled",
        reason="same city",
        agreement_gap="Payment is still unrecorded.",
        public_visible=True,
    )
    db.add(connection)
    db.commit()
    paid = client_with_db.post(
        f"/forge/connections/{connection.id}/advance",
        params={"next_state": "paid", "amount_npr": 900},
    )
    assert paid.status_code == 200, paid.text
    reported = client_with_db.get(f"/public/trust/provider/{provider.id}").json()
    assert reported["reported_payments"][0]["amount"] == 900
    assert reported["verified_payments"] == []
    client_with_db.post(f"/forge/connections/{connection.id}/confirm-payment")
    verified = client_with_db.get(f"/public/trust/provider/{provider.id}").json()
    assert verified["verified_payments"][0]["verification"] == "VERIFIED"
    assert verified["reported_payments"] == []
    assert "score" not in client_with_db.get(f"/public/trust/provider/{provider.id}").text


def test_accepted_work_requires_a_complete_economic_contract(client_with_db, db):
    from app.api.public import terms_complete
    complete = {
        "requested": "Find one verified supplier",
        "who_can_submit": "Anyone with a named supplier",
        "success": "Supplier accepts the stated terms",
        "evidence_required": "Supplier name and stated price",
        "ownership": "The submitter keeps the introduction; Forge may resell only the accepted result",
        "payment_due": "When the supplier acceptance is recorded",
        "amount_npr": 1500,
        "partial": "No payment",
        "rejection": "No payment",
        "resale": "Only after acceptance",
        "costs": "Submitter bears their own search cost",
    }
    assert terms_complete(__import__("json").dumps(complete))
    need = models.DomainRecord(
        kind="job",
        title="Find a supplier",
        detail="Named supplier under the stated terms",
        status="open",
        close_token_hash="tok",
    )
    db.add(need)
    db.commit()
    connection = models.NetworkConnection(
        left_kind="domain_record",
        left_id=need.id,
        right_kind="provider",
        right_id=1,
        state="contacted",
        reason="shared words",
        agreement_gap="Terms are not complete.",
        public_visible=False,
    )
    db.add(connection)
    db.commit()
    blocked = client_with_db.post(f"/forge/connections/{connection.id}/advance", params={"next_state": "accepted"})
    assert blocked.status_code == 409
    need.terms = __import__("json").dumps(complete)
    db.commit()
    allowed = client_with_db.post(f"/forge/connections/{connection.id}/advance", params={"next_state": "accepted"})
    assert allowed.status_code == 200, allowed.text


def test_disputed_payment_settles_only_when_an_amount_is_stated(client_with_db, db):
    provider = models.Provider(
        name="Hill Repair",
        city="Kathmandu",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    db.add(provider)
    db.commit()
    connection = models.NetworkConnection(
        left_kind="domain_record",
        left_id=4,
        right_kind="provider",
        right_id=provider.id,
        state="fulfilled",
        reason="same city",
        agreement_gap="Payment is still unrecorded.",
        public_visible=True,
    )
    db.add(connection)
    db.commit()
    client_with_db.post(f"/forge/connections/{connection.id}/advance", params={"next_state": "paid", "amount_npr": 900})
    client_with_db.post(f"/forge/connections/{connection.id}/confirm-payment")
    disputed = client_with_db.post(
        f"/forge/connections/{connection.id}/dispute-payment",
        params={"note": "The work was incomplete"},
    )
    assert disputed.status_code == 200, disputed.text
    assert disputed.json()["winner"] is None
    trust = client_with_db.get(f"/public/trust/provider/{provider.id}").json()
    assert trust["verified_payments"] == []
    assert trust["disputed_payments"][0]["verification"] == "DISPUTED"
    missing = client_with_db.post(f"/forge/connections/{connection.id}/settle-payment", params={"note": "Agreed", "amount_npr": -1})
    assert missing.status_code == 422
    settled = client_with_db.post(
        f"/forge/connections/{connection.id}/settle-payment",
        params={"note": "Both recorded 700 NPR", "amount_npr": 700},
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["winner"] is None
    final = client_with_db.get(f"/public/trust/provider/{provider.id}").json()
    assert final["settled_payments"][0]["amount"] == 700
    assert final["disputed_payments"] == []
    assert db.query(models.LearningEvent).count() >= 2


def test_connection_response_is_not_acceptance_and_is_alerted(client_with_db, db):
    row = models.NetworkConnection(
        left_kind="domain_record",
        left_id=9,
        right_kind="provider",
        right_id=3,
        state="contacted",
        reason="same city",
        agreement_gap="No response yet.",
        public_visible=False,
    )
    db.add(row)
    db.commit()
    replied = client_with_db.post(
        f"/forge/connections/{row.id}/response",
        params={"note": "I can come Thursday"},
    )
    assert replied.status_code == 200, replied.text
    assert replied.json()["accepted"] is False
    assert replied.json()["state"] == "contacted"
    alerts = client_with_db.get("/public/alerts").json()
    assert any("not acceptance" in item["text"] for item in alerts)
    listed = client_with_db.get("/forge/connections").json()
    match = next(item for item in listed if item["id"] == row.id)
    assert match["state"] == "contacted"
    assert "not acceptance" in match["latest_response"]


def test_stale_evidence_cannot_promote_a_candidate(client_with_db, db):
    from datetime import datetime, timedelta, timezone
    row = models.NetworkConnection(
        left_kind="domain_record",
        left_id=1,
        right_kind="provider",
        right_id=1,
        state="candidate",
        reason="same city",
        agreement_gap="Evidence is old.",
        public_visible=False,
    )
    db.add(models.Signal(
        source="rss",
        source_type="external",
        content="An old note.",
        title="Old note",
        canonical_url="https://example.com/old-note",
        retrieved_at=datetime.now(timezone.utc) - timedelta(days=200),
    ))
    db.add(row)
    db.commit()
    stale = client_with_db.post(
        f"/forge/connections/{row.id}/advance",
        params={"next_state": "evidenced", "evidence_reference": "https://example.com/old-note"},
    )
    assert stale.status_code == 409
    assert row.state == "candidate"


def test_authorization_rejects_a_cost_that_is_not_in_the_evidence(client_with_db, db):
    row = models.NetworkConnection(
        left_kind="domain_record",
        left_id=1,
        right_kind="provider",
        right_id=1,
        state="evidenced",
        reason="same city",
        evidence_reference="https://example.com/cost-note",
        agreement_gap="Cost is not recorded.",
        public_visible=False,
    )
    db.add(models.Signal(
        source="rss",
        source_type="external",
        content="The note mentions a workshop in Kathmandu.",
        title="Workshop note",
        canonical_url="https://example.com/cost-note",
    ))
    db.add(row)
    db.commit()
    invented = client_with_db.post(
        f"/forge/connections/{row.id}/advance",
        params={"next_state": "viable", "constraints": '{"landed_cost": "NPR 50000"}'},
    )
    assert invented.status_code == 409
    quoted = client_with_db.post(
        f"/forge/connections/{row.id}/advance",
        params={"next_state": "viable", "constraints": '{"buyer": "Kathmandu"}'},
    )
    assert quoted.status_code == 200, quoted.text
    saved = client_with_db.get("/forge/connections").json()
    match = next(item for item in saved if item["id"] == row.id)
    assert "Kathmandu" in match["constraints"]
    assert "landed_cost" in match["constraints"]


def test_public_connection_shows_a_response_only_after_publication(client_with_db, db):
    need = models.DomainRecord(
        kind="job", title="Public response need", detail="An open need.",
        close_token_hash="test-hash", status="open",
    )
    provider = models.Provider(
        name="Verified response provider", country="Nepal", public_visible=True,
        is_active=True, verification_status="verified",
    )
    db.add_all([need, provider])
    db.flush()
    row = models.NetworkConnection(
        left_kind="domain_record",
        left_id=need.id,
        right_kind="provider",
        right_id=provider.id,
        state="contacted",
        reason="same city",
        agreement_gap="No response yet.",
        public_visible=False,
    )
    db.add(row)
    db.commit()
    replied = client_with_db.post(f"/forge/connections/{row.id}/response", params={"note": "Thursday works"})
    assert replied.status_code == 200
    assert client_with_db.get("/public/connections").json() == []
    row.public_visible = True
    row.state = "authorized"
    db.commit()
    visible = client_with_db.get("/public/connections").json()
    assert visible[0]["latest_response"]
    assert "not acceptance" in visible[0]["latest_response"]
    assert "Thursday works" in visible[0]["latest_response"]


def test_fulfillment_records_the_work_and_not_a_payment(client_with_db, db):
    need = models.DomainRecord(
        kind="job", title="Public fulfillment need", detail="An open need.",
        close_token_hash="test-hash", status="open",
    )
    provider = models.Provider(
        name="Verified fulfillment provider", country="Nepal", public_visible=True,
        is_active=True, verification_status="verified",
    )
    db.add_all([need, provider])
    db.flush()
    row = models.NetworkConnection(
        left_kind="domain_record",
        left_id=need.id,
        right_kind="provider",
        right_id=provider.id,
        state="accepted",
        reason="same city",
        agreement_gap="Work is not recorded.",
        public_visible=True,
    )
    db.add(row)
    db.commit()
    missing = client_with_db.post(f"/forge/connections/{row.id}/advance", params={"next_state": "fulfilled"})
    assert missing.status_code == 422
    done = client_with_db.post(
        f"/forge/connections/{row.id}/advance",
        params={"next_state": "fulfilled", "note": "The fridge cools again"},
    )
    assert done.status_code == 200, done.text
    assert done.json()["state"] == "fulfilled"
    assert done.json()["payment"] is None
    outcome = db.query(models.Outcome).filter(models.Outcome.notes == f"idempotency:network-connection:{row.id}:fulfilled").one()
    assert outcome.actual_value is None
    assert "not a payment" in outcome.qualitative_result
    visible = client_with_db.get("/public/connections").json()
    assert "The fridge cools again" in visible[0]["latest_fulfillment"]
    assert "not a payment" in visible[0]["latest_fulfillment"]


def test_world_research_agenda_opens_once_and_does_not_state_prices(db):
    from app.services.curiosity_engine import WORLD_RESEARCH_AGENDA, CuriosityEngine
    from app.services import research_planner

    engine = CuriosityEngine(db)
    opened = engine.open_world_research()
    assert len(opened) == len(WORLD_RESEARCH_AGENDA)
    assert len(set(WORLD_RESEARCH_AGENDA)) == len(WORLD_RESEARCH_AGENDA)
    assert engine.open_world_research() == []
    assert all("$" not in question.question for question in opened)
    assert all("trillion" not in question.question.lower() for question in opened)
    agenda_text = " ".join(WORLD_RESEARCH_AGENDA).casefold()
    assert "derivatives" in agenda_text
    assert "hedge-fund" in agenda_text
    assert "reinsurance" in agenda_text
    tasks = research_planner.plan_tasks_for_question(db, opened[0])
    assert tasks
    assert all(task.query for task in tasks)


def test_public_search_matches_service_wording_and_city(client_with_db, db):
    repair = models.Provider(
        name="Hill Repair",
        category="Repair",
        city="Kathmandu",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    tutor = models.Provider(
        name="River Tutors",
        category="Tutoring",
        city="Pokhara",
        country="Nepal",
        public_visible=True,
        is_active=True,
        verification_status="verified",
    )
    db.add_all([repair, tutor])
    db.flush()
    db.add_all([
        models.ServiceListing(
            provider_id=repair.id,
            title="Refrigerator repair",
            description="Home visit for a fridge that will not cool",
            category="Repair",
            location="Kathmandu",
            price_from="1500",
            public_visible=True,
            is_active=True,
        ),
        models.ServiceListing(
            provider_id=tutor.id,
            title="Math tutoring",
            description="Secondary school maths",
            category="Tutoring",
            location="Pokhara",
            public_visible=True,
            is_active=True,
        ),
    ])
    db.commit()

    by_need = client_with_db.get("/public/providers", params={"q": "refrigerator"})
    assert by_need.status_code == 200
    assert {row["id"] for row in by_need.json()} == {repair.id}

    by_city = client_with_db.get("/public/services", params={"city": "Pokhara"})
    assert by_city.status_code == 200
    assert {row["provider_id"] for row in by_city.json()} == {tutor.id}


def test_public_table_migration_preserves_legacy_data_and_keeps_integrity_ok(tmp_path):
    db_path = tmp_path / "legacy-forge.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE legacy_records (id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
        conn.execute("INSERT INTO legacy_records (id, label) VALUES (?, ?)", (1, "preserved"))
        conn.commit()

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)

    with sqlite3.connect(db_path) as probe:
        table_names = {row[0] for row in probe.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        assert {"public_providers", "public_service_listings", "public_verification_records", "public_booking_requests"}.issubset(table_names)
        assert probe.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert probe.execute("SELECT label FROM legacy_records WHERE id = 1").fetchone()[0] == "preserved"
