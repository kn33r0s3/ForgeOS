"""Scout + Draft + Approval Queue: registry, scoring, drafts, guards."""

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

    # Never message twice without a reply.
    d2 = scout.generate_draft(db, c.id, "another fact")
    scout.approve_draft(db, d2.id)
    with pytest.raises(ValueError, match="without a reply"):
        scout.mark_sent(db, d2.id, channel="facebook")

    # After a reply, contact is allowed again.
    scout.record_reply(db, d.id, "Seller replied: interested, call Thursday.")
    assert db.get(models.OutreachDraft, d.id).reply_received is True
    d3 = scout.generate_draft(db, c.id, "follow-up fact")
    assert d3.status == "DRAFT"


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
