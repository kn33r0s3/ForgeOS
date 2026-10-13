"""Tests for real-world capability verification (Repair K).

world_graph.record_capability_verification() enforces the v2 invariant:
"Record a capability ONLY from a verified outcome (Event + Evidence).
Never from prose."

These tests use explicitly labeled TEST fixtures to prove the code gate.
They do NOT claim any real customer outcome.
"""

import json

import pytest

from app import models
from app.services import world_graph
from app.services.type_validation import SubstrateError


def _make_capability(db, name="test-cap", attributes="{}"):
    cap = models.ForgeCapability(
        capability_type="workflow",
        name=name,
        description="test capability",
        status="proposed",
        attributes=attributes,
        owner_agent="test",
    )
    db.add(cap)
    db.commit()
    db.refresh(cap)
    return cap


def _make_subject(db):
    """Create a substrate entity to serve as the shared real-world subject.

    TEST FIXTURE: the subject is test scaffolding, not a domain concept.
    Uses ORM with all required fields to avoid type-registry validation
    issues (bypasses create_entity which enforces registered types).
    """
    from datetime import datetime, timezone

    ent = models.SubstrateEntity(
        entity_type="test_subject",
        display_name="Test Subject",
        attributes="{}",
        status="active",
        created_by="test",
        identity_state="candidate",
        created_at=datetime.now(timezone.utc),
    )
    # Bypass ORM validation by using core insert
    from sqlalchemy import insert

    stmt = insert(models.SubstrateEntity).values(
        entity_type="test_subject",
        display_name="Test Subject",
        attributes="{}",
        status="active",
        created_by="test",
        identity_state="candidate",
        created_at=datetime.now(timezone.utc),
    )
    db.execute(stmt)
    db.commit()
    ent = db.query(models.SubstrateEntity).filter_by(entity_type="test_subject").order_by(models.SubstrateEntity.id.desc()).first()
    return ent


def _make_test_event(db, subject_id, source="test-fixture"):
    """TEST fixture: this event is not independently observed reality."""
    evt = models.WorldEvent(
        event_type="outreach.sent",
        entity_id=subject_id,
        payload="{}",
        source=source,
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    return evt


def _make_test_evidence(db, subject_id, source_type="firsthand"):
    """TEST-only evidence; deliberately ineligible for real-world verification."""
    ev = models.Evidence(
        subject_kind="entity",
        subject_id=subject_id,
        source="test-fixture",
        source_kind="TEST",
        source_type=source_type,
        source_identity="test-fixture-observer",
        provenance=json.dumps({"test_fixture": True, "note": "not a real outcome"}),
        support_level="possible",
        claim="test fixture claim — not a real outcome",
        content="test fixture evidence — not a real outcome",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev



def test_test_fixture_evidence_cannot_be_recorded_as_real_world_verification(db):
    """Test fixtures cannot establish a real-world outcome."""
    cap = _make_capability(db)
    subject = _make_subject(db)
    evt = _make_test_event(db, subject.id, source="manual")
    ev = _make_test_evidence(db, subject.id)

    with pytest.raises(SubstrateError, match="source_kind='TEST'"):
        world_graph.record_capability_verification(db, cap, evt.id, ev.id)

    assert "real_world_verifications" not in json.loads(cap.attributes)
    assert cap.status == "proposed"


def test_test_source_event_rejected(db):
    """Events from test sources cannot establish real-world verification."""
    cap = _make_capability(db)
    subject = _make_subject(db)
    evt = _make_test_event(db, subject.id, source="test")
    ev = _make_test_evidence(db, subject.id)

    with pytest.raises(SubstrateError, match="not TEST"):
        world_graph.record_capability_verification(db, cap, evt.id, ev.id)


def test_synthetic_evidence_rejected(db):
    """Agent-written/synthetic/mock evidence cannot establish verification."""
    cap = _make_capability(db)
    subject = _make_subject(db)
    evt = _make_test_event(db, subject.id, source="manual")
    for bad_source in ["agent_written", "synthetic", "mock"]:
        ev = _make_test_evidence(db, subject.id, source_type=bad_source)
        with pytest.raises(SubstrateError, match="not synthetic or mock"):
            world_graph.record_capability_verification(db, cap, evt.id, ev.id)



def test_test_evidence_is_rejected_before_subject_matching(db):
    """Fixture IDs cannot establish a real outcome, whether related or not."""
    cap = _make_capability(db)
    subject_a = _make_subject(db)
    subject_b = _make_subject(db)
    evt = _make_test_event(db, subject_a.id, source="manual")
    ev = _make_test_evidence(db, subject_b.id)

    with pytest.raises(SubstrateError, match="source_kind='TEST'"):
        world_graph.record_capability_verification(db, cap, evt.id, ev.id)


def test_missing_event_rejected(db):
    cap = _make_capability(db)
    subject = _make_subject(db)
    ev = _make_test_evidence(db, subject.id)

    with pytest.raises(SubstrateError, match="Event not found"):
        world_graph.record_capability_verification(db, cap, 99999, ev.id)


def test_missing_evidence_rejected(db):
    cap = _make_capability(db)
    subject = _make_subject(db)
    evt = _make_test_event(db, subject.id, source="manual")

    with pytest.raises(SubstrateError, match="Evidence not found"):
        world_graph.record_capability_verification(db, cap, evt.id, 99999)



def test_evidence_without_provenance_rejected(db):
    """Substantive evidence cannot be persisted without a traceable origin."""
    subject = _make_subject(db)
    ev = models.Evidence(
        subject_kind="entity",
        subject_id=subject.id,
        source="reviewed-public-source",
        source_kind="REAL",
        source_type="third_party",
        support_level="supported",
        claim="A report-backed statement requiring traceability.",
        content="candidate source evidence without an origin record",
    )
    db.add(ev)
    with pytest.raises(SubstrateError, match="provenance"):
        db.commit()



def test_repeated_test_fixture_attempts_never_create_verification_markers(db):
    """Repeating rejected test evidence never turns it into a REAL outcome."""
    cap = _make_capability(db)
    subject = _make_subject(db)
    evt = _make_test_event(db, subject.id, source="manual")
    ev = _make_test_evidence(db, subject.id)

    for _ in range(2):
        with pytest.raises(SubstrateError, match="source_kind='TEST'"):
            world_graph.record_capability_verification(db, cap, evt.id, ev.id)

    assert "real_world_verifications" not in json.loads(cap.attributes)


def test_malformed_attributes_handled(db):
    """Non-JSON attributes are handled gracefully (defensive).

    Note: the ForgeCapability model validates attributes as JSON on write,
    so malformed data cannot persist. This tests the defensive _parse_json
    path directly.
    """
    from app.services.world_graph import _parse_json

    # _parse_json returns {} for malformed input instead of raising.
    assert _parse_json("not-valid-json{{{") == {}
    assert _parse_json(None) == {}
    assert _parse_json("") == {}
    # Valid JSON parses normally.
    assert _parse_json('{"a": 1}') == {"a": 1}



def test_existing_attributes_preserved_when_verification_is_rejected(db):
    existing = {"custom_key": "custom_value", "nested": {"a": 1}}
    cap = _make_capability(db, attributes=json.dumps(existing))
    subject = _make_subject(db)
    evt = _make_test_event(db, subject.id, source="manual")
    ev = _make_test_evidence(db, subject.id)

    with pytest.raises(SubstrateError, match="source_kind='TEST'"):
        world_graph.record_capability_verification(db, cap, evt.id, ev.id)

    attrs = json.loads(cap.attributes)
    assert attrs["custom_key"] == "custom_value"
    assert attrs["nested"] == {"a": 1}
    assert "real_world_verifications" not in attrs



def test_implementation_status_unchanged_on_rejected_verification(db):
    """A rejected fixture cannot mutate lifecycle state or test provenance."""
    cap = _make_capability(db)
    original_status = cap.status
    original_test_ref = cap.test_ref
    subject = _make_subject(db)
    evt = _make_test_event(db, subject.id, source="manual")
    ev = _make_test_evidence(db, subject.id)

    with pytest.raises(SubstrateError, match="source_kind='TEST'"):
        world_graph.record_capability_verification(db, cap, evt.id, ev.id)

    assert cap.status == original_status
    assert cap.test_ref == original_test_ref
    assert "real_world_verifications" not in json.loads(cap.attributes)
