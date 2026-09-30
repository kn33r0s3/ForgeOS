import json
from datetime import datetime, timedelta, timezone

from app import models
from app.api.public import _match_for_need, list_public_discoveries
from app.services.public_feed import build_public_feed
from app.services.public_epistemics import derive_public_label, public_claim_label


def _claim(db, *, state="observed", kind=None, statement="A stored public claim.", extra=None):
    provenance = dict(extra or {})
    if kind is not None:
        provenance["epistemic_type"] = kind
    row = models.Claim(
        statement=statement,
        normalized_statement=statement.casefold(),
        epistemic_state=state,
        provenance=json.dumps(provenance) if provenance else None,
    )
    db.add(row)
    db.flush()
    return row


def _evidence(db, claim, *, source, retrieved_at=None, relation="supports"):
    url = f"https://{source}.example.org/report"
    signal = models.Signal(
        source=source,
        source_type="external",
        content=f"Evidence from {source}.",
        canonical_url=url,
        retrieved_at=retrieved_at or datetime.now(timezone.utc),
    )
    db.add(signal)
    db.flush()
    evidence = models.Evidence(
        signal_id=signal.id,
        source=source,
        content=signal.content,
        canonical_url=url,
        retrieved_at=retrieved_at or signal.retrieved_at,
        provenance_hash=f"test:{claim.id}:{source}",
    )
    db.add(evidence)
    db.flush()
    db.add(models.EvidenceRelationship(
        evidence_id=evidence.id,
        claim_id=claim.id,
        relation_type=relation,
        relation_key=f"test:{claim.id}:{source}:{relation}",
    ))
    db.flush()
    return evidence


def test_public_label_mapping_covers_fact_observation_external_claim_conflict_and_hidden_states(db):
    now = datetime(2026, 9, 25, tzinfo=timezone.utc)

    fact = _claim(db, kind="FACT")
    assert derive_public_label(db, fact, now=now) == {"epistemic_state": "supported", "stale": False}

    corroborated = _claim(db, state="observed", kind="EXTERNAL CLAIM")
    _evidence(db, corroborated, source="source-a", retrieved_at=now)
    _evidence(db, corroborated, source="source-b", retrieved_at=now)
    assert derive_public_label(db, corroborated, now=now) == {
        "epistemic_state": "supported", "stale": False,
    }

    one_source = _claim(db, state="observed", kind="EXTERNAL CLAIM")
    _evidence(db, one_source, source="source-a", retrieved_at=now)
    assert derive_public_label(db, one_source, now=now) == {
        "epistemic_state": "observed", "stale": False,
    }

    observation = _claim(db, kind="OBSERVATION")
    _evidence(db, observation, source="observer", retrieved_at=now)
    _evidence(db, observation, source="second-observer", retrieved_at=now)
    assert derive_public_label(db, observation, now=now) == {
        "epistemic_state": "observed", "stale": False,
    }

    conflict = _claim(db, state="contested", kind="EXTERNAL CLAIM")
    _evidence(db, conflict, source="source-a", retrieved_at=now)
    _evidence(db, conflict, source="source-b", retrieved_at=now, relation="contradicts")
    assert derive_public_label(db, conflict, now=now) == {
        "epistemic_state": "contested", "stale": False,
    }

    inference = _claim(db, kind="INFERENCE")
    unknown = _claim(db, kind="UNKNOWN")
    assert derive_public_label(db, inference, now=now) is None
    assert derive_public_label(db, unknown, now=now) is None


def test_staleness_is_separate_from_the_public_epistemic_label(db):
    now = datetime(2026, 9, 25, tzinfo=timezone.utc)
    claim = _claim(db, state="supported", kind="EXTERNAL CLAIM")
    _evidence(db, claim, source="old-source", retrieved_at=now - timedelta(days=120))

    assert derive_public_label(db, claim, now=now) == {
        "epistemic_state": "observed", "stale": True,
    }


def test_regulated_asset_publication_requires_named_compliance_review(db):
    now = datetime(2026, 9, 25, tzinfo=timezone.utc)
    claim = _claim(
        db,
        state="supported",
        kind="EXTERNAL CLAIM",
        statement="The equity derivatives market has a newly reported change.",
    )
    _evidence(db, claim, source="source-a", retrieved_at=now)
    _evidence(db, claim, source="source-b", retrieved_at=now)

    assert derive_public_label(db, claim, now=now) == {"epistemic_state": "supported", "stale": False}
    assert public_claim_label(db, claim, now=now) is None

    claim.provenance = json.dumps({
        "epistemic_type": "EXTERNAL CLAIM",
        "compliance_review": {
            "status": "approved",
            "reviewer": "compliance-reviewer",
            "reference": "review-2026-09-25-001",
        },
    })
    assert public_claim_label(db, claim, now=now) == {"epistemic_state": "supported", "stale": False}


def test_discoveries_feed_context_and_matching_share_the_publication_gate(db):
    now = datetime.now(timezone.utc)
    claim = _claim(
        db,
        state="supported",
        kind="EXTERNAL CLAIM",
        statement="The equity market changed after a documented announcement.",
    )
    _evidence(db, claim, source="source-a", retrieved_at=now)
    _evidence(db, claim, source="source-b", retrieved_at=now)
    need = models.DomainRecord(
        kind="job",
        title="Equity market announcement research",
        detail="Review a documented equity market announcement.",
        close_token_hash="test-only",
        status="open",
    )
    db.add(need)
    db.flush()

    assert list_public_discoveries(limit=20, db=db) == []
    assert not any(item.entity_type == "claim" for item in build_public_feed(db))
    assert not any(candidate.kind == "knowledge" for candidate in _match_for_need(db, need).candidates)

    claim.provenance = json.dumps({
        "epistemic_type": "EXTERNAL CLAIM",
        "compliance_review": {
            "status": "approved",
            "reviewer": "compliance-reviewer",
            "reference": "review-2026-09-25-002",
        },
    })
    db.flush()

    discovery = list_public_discoveries(limit=20, db=db)
    feed = build_public_feed(db)
    matches = _match_for_need(db, need)
    assert discovery[0].epistemic_state == "supported"
    assert discovery[0].stale is False
    assert next(item for item in feed if item.entity_type == "claim").epistemic_state == "supported"
    assert any(candidate.kind == "knowledge" for candidate in matches.candidates)
