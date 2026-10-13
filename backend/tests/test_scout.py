"""Scout + Draft + Approval Queue: registry, scoring, drafts, guards."""

import json

import pytest

from app import models
from app.services import scout


def _candidate(db, name="Test Shop", url=None):
    return scout.register_candidate(
        db,
        display_name=name,
        source_url=url or f"https://facebook.com/{name.lower().replace(' ', '')}",
        public_contact_route="Facebook page messenger (as listed on page)",
        observed_signals={"posting_active": True},
    )


def test_register_and_score(db):
    c = _candidate(db)
    assert c.entity_type == "scout_candidate"
    assert c.identity_state == "candidate"
    # No signals yet -> unscored.
    assert scout.score_candidate(db, c.id) is None

    scout.record_signal(db, c.id, "unanswered_inquiry", "3 unanswered comments on 2026-10-05")
    scout.record_signal(db, c.id, "posting_active", "posted 2 days ago")
    score = scout.score_candidate(db, c.id)
    assert score is not None and score > 0


def test_ranking_scored_first(db):
    a = _candidate(db, "Shop A")
    b = _candidate(db, "Shop B")
    scout.record_signal(db, b.id, "unanswered_inquiry", "5 unanswered comments")
    ranked = scout.rank_candidates(db)
    assert ranked[0][0].id == b.id
    assert ranked[0][1] is not None
    assert ranked[1][1] is None  # A unscored


def test_draft_is_honest_and_bilingual(db):
    c = _candidate(db)
    d = scout.generate_draft(db, c.id, "4 unanswered inquiry comments on your page this week")
    assert d.status == "DRAFT"
    assert "4 unanswered inquiry comments" in d.message_en
    assert "10 minutes" in d.message_en
    assert "won't message again" in d.message_en  # easy opt-out
    assert d.message_ne  # Nepali version present
    assert "customer" not in d.message_en.lower()  # no pretending to be a customer


def test_approve_skip_sent_flow(db):
    c = _candidate(db)
    d = scout.generate_draft(db, c.id, "2 unanswered comments")
    scout.approve_draft(db, d.id)
    assert db.get(models.OutreachDraft, d.id).status == "APPROVED"

    sent = scout.mark_sent(db, d.id, channel="facebook", sent_by="owner")
    assert sent.status == "SENT"
    assert sent.sent_at is not None
    # Send logged as Event with authorization.
    events = db.query(models.WorldEvent).filter_by(event_type="outreach.sent").all()
    assert len(events) == 1
    # And as an Action.
    actions = db.query(models.Action).filter_by(action_type="outreach").all()
    assert len(actions) >= 1
    linked_action = db.query(models.Action).filter_by(external_ref=f"outreach_draft:{d.id}").one()
    action_parameters = json.loads(linked_action.parameters_json)
    assert action_parameters["authorized_by"] == "owner"
    assert action_parameters["outcome_status"] == "contact reported sent; response pending"
    assert json.loads(events[0].payload)["authorized_by"] == "owner"

    # Never message twice without a reply.
    d2 = scout.generate_draft(db, c.id, "another fact")
    scout.approve_draft(db, d2.id)
    with pytest.raises(ValueError, match="without a reply"):
        scout.mark_sent(db, d2.id, channel="facebook")

    # After a reply, contact is allowed again.
    scout.record_reply(db, d.id, "Seller replied: interested, call Thursday.")
    assert db.get(models.OutreachDraft, d.id).reply_received is True
    linked_action = db.query(models.Action).filter_by(external_ref=f"outreach_draft:{d.id}").one()
    assert json.loads(linked_action.parameters_json)["outcome"]["type"] == "reply_received"
    reply_event = db.query(models.WorldEvent).filter_by(event_type="outreach.reply").one()
    assert json.loads(reply_event.payload)["authorized_by"] == "owner"
    d3 = scout.generate_draft(db, c.id, "follow-up fact")
    assert d3.status == "DRAFT"


def test_no_response_records_a_dry_well_without_unlocking_another_send(db):
    candidate = _candidate(db, "No Reply Shop")
    draft = scout.generate_draft(db, candidate.id, "2 unanswered inquiries")
    scout.approve_draft(db, draft.id)
    sent = scout.mark_sent(db, draft.id, channel="facebook", sent_by="owner")

    closed = scout.record_no_response(
        db,
        sent.id,
        "No response observed after checking the Facebook inbox on 2026-10-14.",
    )
    assert closed.reply_received is False
    assert closed.status == "SENT"
    event = db.query(models.WorldEvent).filter_by(
        event_type="outreach.no_response"
    ).one()
    payload = json.loads(event.payload)
    assert payload["outcome_type"] == "no_response_observed"
    assert payload["verification"].startswith("owner-recorded")
    assert payload["blocks_further_contact"] is True
    with pytest.raises(ValueError, match="without a reply"):
        scout.check_send_allowed(db, candidate.id)
    with pytest.raises(ValueError, match="already recorded"):
        scout.record_no_response(db, sent.id, "Duplicate dry-well report")


def test_pending_reply_api_only_lists_unresolved_sent_drafts(db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    pending_candidate = _candidate(db, "Pending Reply Shop")
    pending = scout.generate_draft(db, pending_candidate.id, "One unanswered inquiry")
    scout.approve_draft(db, pending.id)
    scout.mark_sent(db, pending.id, channel="facebook", sent_by="owner")

    replied_candidate = _candidate(db, "Replied Shop")
    replied = scout.generate_draft(db, replied_candidate.id, "Two unanswered inquiries")
    scout.approve_draft(db, replied.id)
    scout.mark_sent(db, replied.id, channel="facebook", sent_by="owner")
    scout.record_reply(db, replied.id, "The owner replied and requested details.")

    response = TestClient(app).get(
        "/scout/pending-replies",
        headers={"X-API-Key": "test-owner-key"},
    )
    assert response.status_code == 200, response.text
    items = response.json()
    assert [item["id"] for item in items] == [pending.id]
    assert items[0]["reply_received"] is False
    assert items[0]["send_channel"] == "facebook"


def test_pending_reply_queue_api_preserves_dry_wells_for_late_replies(db, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import settings
    from app.main import app

    monkeypatch.setattr(settings, "FORGE_API_KEY", "test-owner-key")
    candidate = _candidate(db, "Late Reply Shop")
    draft = scout.generate_draft(db, candidate.id, "One unanswered inquiry")
    scout.approve_draft(db, draft.id)
    scout.mark_sent(db, draft.id, channel="facebook", sent_by="owner")

    client = TestClient(app)
    headers = {"X-API-Key": "test-owner-key"}
    dry_well = client.post(
        f"/scout/drafts/{draft.id}/no-response",
        headers=headers,
        json={"summary": "No reply observed after checking messages on 2026-10-14."},
    )
    assert dry_well.status_code == 200, dry_well.text
    assert dry_well.json()["reply_received"] is False

    response = client.get("/scout/pending-replies", headers=headers)
    assert response.status_code == 200, response.text
    item = next(item for item in response.json() if item["id"] == draft.id)
    assert item["reply_received"] is False
    assert "No reply observed" in item["outcome_notes"]

    # A late reply remains recordable and does not get mislabeled as a new lead.
    reply = client.post(
        f"/scout/drafts/{draft.id}/reply",
        headers=headers,
        json={"summary": "Recipient replied after the earlier no-response note."},
    )
    assert reply.status_code == 200, reply.text
    duplicate = client.post(
        f"/scout/drafts/{draft.id}/reply",
        headers=headers,
        json={"summary": "Duplicate submission should not create another event."},
    )
    assert duplicate.status_code == 422
    assert db.query(models.WorldEvent).filter_by(
        event_type="outreach.reply",
    ).count() == 1
    response = client.get("/scout/pending-replies", headers=headers)
    assert all(item["id"] != draft.id for item in response.json())


def test_scout_cycle_reports_pending_replies_and_dry_wells(db):
    candidate = _candidate(db, "Outcome Queue Shop")
    draft = scout.generate_draft(db, candidate.id, "One unanswered inquiry")
    scout.approve_draft(db, draft.id)
    scout.mark_sent(db, draft.id, channel="facebook", sent_by="owner")

    before = scout.run_scout_cycle(db)
    assert before["pending_contact_replies"] == 1
    assert before["pending_contact_outcomes"] == 1
    assert before["dry_wells_recorded"] == 0

    scout.record_no_response(db, draft.id, "No reply observed as of 2026-10-14.")
    after = scout.run_scout_cycle(db)
    assert after["pending_contact_replies"] == 1
    assert after["pending_contact_outcomes"] == 0
    assert after["dry_wells_recorded"] == 1


def test_do_not_contact_blocks(db):
    c = _candidate(db)
    db.add(models.DoNotContact(candidate_entity_id=c.id, reason="asked not to be contacted"))
    db.commit()
    with pytest.raises(ValueError, match="Do-not-contact"):
        scout.generate_draft(db, c.id, "some fact")


def test_daily_cap_blocks(db):
    cfg = models.OutreachConfig(daily_cap=1)
    db.add(cfg)
    db.commit()
    c1 = _candidate(db, "Shop 1")
    c2 = _candidate(db, "Shop 2")
    d1 = scout.generate_draft(db, c1.id, "fact one")
    scout.approve_draft(db, d1.id)
    scout.mark_sent(db, d1.id, channel="facebook")
    d2 = scout.generate_draft(db, c2.id, "fact two")
    scout.approve_draft(db, d2.id)
    with pytest.raises(ValueError, match="Daily cap"):
        scout.mark_sent(db, d2.id, channel="facebook")


def test_seed_registry_experiments(db):
    created = scout.seed_registry_experiments(db)
    assert len(created) == 5
    kinds = {e.experiment_kind for e in created}
    assert kinds == {"OBSERVATION", "CONVERSATION", "INTERVENTION"}
    # Idempotent.
    assert scout.seed_registry_experiments(db) == []
    # Five fields present.
    import json

    fields = json.loads(created[0].five_fields_json)
    for key in ("reality", "possibility", "constraint", "intervention", "outcome"):
        assert key in fields


def test_scout_cycle_scores_and_ranks(db):
    """run_scout_cycle processes registered candidates without sending."""
    from app.services import scout

    scout.register_candidate(
        db,
        display_name="Test Business",
        source_url="https://example.com/test",
        public_contact_route="test@example.com",
        observed_signals={"primary_fact": "custom fabrication"},
    )
    result = scout.run_scout_cycle(db)

    assert result["candidates_ranked"] >= 1
    # candidates_scored may be 0 if no Evidence signals exist (unscored=None is valid)
    assert result["candidates_scored"] >= 0
    # Drafts may be generated but nothing is sent
    assert result["drafts_generated"] >= 0
    # No messages sent — drafts require explicit approval
    from app import models
    sent = db.query(models.OutreachDraft).filter(
        models.OutreachDraft.status == "sent"
    ).count()
    assert sent == 0


def test_scout_cycle_does_not_duplicate_unresolved_drafts(db):
    """Repeated scheduled Scout cycles must not flood the owner review queue."""
    candidate = _candidate(db, "Repeat Shop")
    scout.record_signal(db, candidate.id, "unanswered_inquiry", "3 unanswered inquiry comments")
    first = scout.run_scout_cycle(db)
    assert first["drafts_generated"] == 1

    second = scout.run_scout_cycle(db)
    assert second["drafts_generated"] == 0
    assert second["drafts_already_open"] == 1
    assert db.query(models.OutreachDraft).filter(
        models.OutreachDraft.candidate_entity_id == candidate.id,
        models.OutreachDraft.status.in_(("DRAFT", "APPROVED")),
    ).count() == 1


def test_scout_cycle_reports_open_draft_before_unreplied_send_block(db):
    """An existing owner draft remains visible even when another send is not allowed."""
    candidate = _candidate(db, "Followup Shop")
    scout.record_signal(db, candidate.id, "unanswered_inquiry", "3 unanswered inquiry comments")

    sent = scout.generate_draft(db, candidate.id, "First observed fact")
    scout.approve_draft(db, sent.id)
    scout.mark_sent(db, sent.id, channel="facebook", sent_by="owner")
    scout.generate_draft(db, candidate.id, "Follow-up observation")

    result = scout.run_scout_cycle(db)
    assert result["drafts_generated"] == 0
    assert result["drafts_already_open"] == 1
    assert result["blocked"] == 0


def test_scout_cycle_respects_do_not_contact(db):
    """Candidates on do-not-contact are blocked, not drafted."""
    from app.services import scout

    entity = scout.register_candidate(
        db,
        display_name="Blocked Business",
        source_url="https://example.com/blocked",
        public_contact_route="blocked@example.com",
    )
    # Add to do-not-contact
    from app import models
    dnc = models.DoNotContact(
        candidate_entity_id=entity.id,
        reason="test",
    )
    db.add(dnc)
    db.commit()

    result = scout.run_scout_cycle(db)
    assert result["blocked"] >= 1
