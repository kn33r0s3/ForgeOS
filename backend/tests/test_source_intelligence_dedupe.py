"""Source-intelligence extraction must be idempotent and must not drop
distinct long claims (cycle 66).

Regression coverage:
- re-running extract_claims / extract_ideas_from_claims on the same
  document does not duplicate rows (the /world/ingest path returns the
  existing doc for identical text, then re-extracts);
- the within-run dedupe key covers the full claim text, not a 120-char
  prefix (two distinct long sentences sharing a 120-char prefix must both
  be kept).
"""

from app import models
from app.services import source_intelligence

_SHARED = (
    "The platform takes a 10% commission on all business sales "
    "transactions processed through checkout, and the payout happens "
)


def _sample_text():
    # Two distinct opinion claims (>20 chars, 'business' keeps them) that
    # share a >=120-char prefix but differ in the tail.
    assert len(_SHARED) >= 120
    claim_a = _SHARED + "within seven days of delivery confirmation, no exceptions."
    claim_b = _SHARED + "within thirty days unless the buyer disputes the order first."
    assert len(claim_a) < 400 and len(claim_b) < 400
    assert claim_a[:120] == claim_b[:120]
    assert claim_a != claim_b
    return (
        f"{claim_a}\n{claim_b}\n"
        "Our business model works when customers pay every month.\n"
        "Buy when the stock price crosses above the moving average, "
        "and sell when it breaks below."
    )


def test_rerun_does_not_duplicate_claims_and_ideas(db):
    doc = source_intelligence.ingest_document(db, _sample_text())
    claims_first = source_intelligence.extract_claims(db, doc.id)
    ideas_first = source_intelligence.extract_ideas_from_claims(db, doc.id)

    assert len(claims_first) == 4
    assert len(ideas_first) == 1  # the "buy when" trading claim

    # Same path as a second POST /world/ingest of identical text: existing
    # doc returned, extraction re-run.
    doc2 = source_intelligence.ingest_document(db, _sample_text())
    assert doc2.id == doc.id
    claims_second = source_intelligence.extract_claims(db, doc2.id)
    ideas_second = source_intelligence.extract_ideas_from_claims(db, doc2.id)

    assert claims_second == []
    assert ideas_second == []

    assert db.query(models.WorldClaim).filter_by(document_id=doc.id).count() == 4
    assert db.query(models.WorldIdea).filter_by(document_id=doc.id).count() == 1


def test_distinct_long_claims_sharing_prefix_are_both_kept(db):
    doc = source_intelligence.ingest_document(db, _sample_text())
    claims = source_intelligence.extract_claims(db, doc.id)
    texts = [c.claim_text for c in claims]
    assert any("no exceptions" in t for t in texts)
    assert any("disputes the order" in t for t in texts)
