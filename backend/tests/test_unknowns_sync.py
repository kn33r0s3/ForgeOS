"""unknowns_sync: production self-syncs the map into Claim primitives."""
from unittest.mock import patch

from app import models
from app.services.unknowns_sync import sync_unknowns_from_map


MAP_TEXT = """# Hami unknowns map

| D1 | First test question? | UNKNOWN | Ask one seller | Stakes one |
| D2 | Second test question? | UNKNOWN | Ask two sellers | Stakes two |
"""


def test_sync_imports_new_rows_idempotently(db):
    with patch("app.services.unknowns_sync.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = MAP_TEXT.encode()
        first = sync_unknowns_from_map(db)
        second = sync_unknowns_from_map(db)
    assert first == 2
    assert second == 0  # dedup: nothing new the second time
    rows = db.query(models.Claim).filter(models.Claim.provenance.like("%UNKNOWN_MAP.md%")).all()
    assert len(rows) == 2
    assert {r.epistemic_state for r in rows} == {"unknown"}


def test_sync_failure_never_raises(db):
    with patch(
        "app.services.unknowns_sync.urllib.request.urlopen",
        side_effect=Exception("network down"),
    ):
        assert sync_unknowns_from_map(db) == 0
    assert db.query(models.Claim).count() == 0


def test_sync_updates_row_in_place_when_map_text_revised(db):
    with patch("app.services.unknowns_sync.urllib.request.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = MAP_TEXT.encode()
        assert sync_unknowns_from_map(db) == 2
        revised = MAP_TEXT.replace("First test question?", "First test question, reworded?")
        mock_open.return_value.__enter__.return_value.read.return_value = revised.encode()
        assert sync_unknowns_from_map(db) == 0  # update-in-place, not an insert
    rows = (
        db.query(models.Claim)
        .filter(models.Claim.provenance.like("%row D1 %"))
        .order_by(models.Claim.id)
        .all()
    )
    assert len(rows) == 1  # no duplicate revision
    assert "reworded" in rows[0].statement


def _duplicate_claim_pair(db, row_id, *, older_opportunity_id=None):
    old = models.Claim(
        statement="Older wording?",
        normalized_statement="older wording?",
        epistemic_state="unknown",
        confidence=0.0,
        opportunity_id=older_opportunity_id,
        provenance=f"UNKNOWN_MAP.md §D row {row_id} (imported 2026-10-04). Cheapest test: x",
    )
    new = models.Claim(
        statement="Newer wording?",
        normalized_statement="newer wording?",
        epistemic_state="unknown",
        confidence=0.0,
        provenance=f"UNKNOWN_MAP.md §D row {row_id} (imported 2026-10-11). Cheapest test: x",
    )
    db.add_all([old, new])
    db.flush()
    return old, new


def _apply_map_revision(db, row_id):
    from app.cli.import_unknowns import import_unknowns, parse_unknown_map

    unknowns = parse_unknown_map(f"| {row_id} | Newer wording? | UNKNOWN | Ask | Stakes |\n")
    return import_unknowns(unknowns, db, apply=True)


def test_sync_retires_older_duplicate_rows_when_unreferenced(db):
    old, new = _duplicate_claim_pair(db, "D9")
    db.commit()
    stats = _apply_map_revision(db, "D9")
    assert stats["skipped_existing"] == 1
    assert stats["retired_dupes"] == 1
    remaining = db.query(models.Claim).filter(models.Claim.provenance.like("%row D9 %")).all()
    assert len(remaining) == 1
    assert remaining[0].id == new.id


def test_sync_preserves_older_duplicate_claim_with_inbound_foreign_key(db):
    old, _new = _duplicate_claim_pair(db, "D10")
    question = models.ResearchQuestion(
        question="Follow-up that depends on the older claim ID?",
        source_claim_id=old.id,
    )
    db.add(question)
    db.commit()

    stats = _apply_map_revision(db, "D10")

    assert stats["retired_dupes"] == 0
    assert db.get(models.Claim, old.id) is not None
    assert db.get(models.ResearchQuestion, question.id).source_claim_id == old.id


def test_sync_preserves_older_claim_that_owns_an_outgoing_foreign_key(db):
    opportunity = models.Opportunity(problem="Opportunity attached to old claim")
    db.add(opportunity)
    db.flush()
    old, _new = _duplicate_claim_pair(
        db, "D11", older_opportunity_id=opportunity.id
    )
    db.commit()

    stats = _apply_map_revision(db, "D11")

    assert stats["retired_dupes"] == 0
    preserved = db.get(models.Claim, old.id)
    assert preserved is not None
    assert preserved.opportunity_id == opportunity.id


def test_sync_preserves_claim_with_canonical_substrate_identity(db):
    from app.services import world_graph

    old, _new = _duplicate_claim_pair(db, "D12")
    entity = world_graph.ensure_canonical_entity(
        db,
        "claim",
        old.id,
        created_by="legacy_record_substrate_adapter",
    )
    db.commit()

    stats = _apply_map_revision(db, "D12")

    assert stats["retired_dupes"] == 0
    assert db.get(models.Claim, old.id) is not None
    assert db.get(models.SubstrateEntity, entity.id).source_id == str(old.id)


def test_sync_preserves_legacy_canonical_ref_wrapper(db):
    import json

    from app.services import world_graph

    old, _new = _duplicate_claim_pair(db, "D13")
    legacy_attributes = json.dumps(
        {"canonical_ref": {"entity_type": "claim", "entity_id": old.id}},
        sort_keys=True,
        separators=(",", ":"),
    )
    entity = models.SubstrateEntity(
        entity_type="claim",
        display_name="Legacy canonical claim wrapper",
        attributes=legacy_attributes,
        created_by="legacy_test",
        source_system=None,
        source_id=None,
        identity_key=None,
    )
    db.add(entity)
    db.commit()

    assert world_graph.find_canonical_entity(db, "claim", old.id).id == entity.id
    stats = _apply_map_revision(db, "D13")

    assert stats["retired_dupes"] == 0
    assert db.get(models.Claim, old.id) is not None
    assert db.get(models.SubstrateEntity, entity.id).attributes == legacy_attributes
