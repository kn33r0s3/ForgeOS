"""GET /forge/unknowns: the public projection reads stored Claim primitives.

Every item the page displays comes from this endpoint with its truth
label (epistemic_state) and source (provenance) — nothing hand-written.
"""
from fastapi.testclient import TestClient

from app import models
from app.config import settings
from app.database import get_db
from app.main import app


def _client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_unknowns_come_from_claim_primitives_with_truth_label_and_source(db):
    settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED = True
    db.add(models.Claim(
        statement="What is the actual COD remittance window?",
        normalized_statement="what is the actual cod remittance window?",
        epistemic_state="unknown",
        confidence=0.0,
        provenance='UNKNOWN_MAP.md \u00a7D row D60 (banked 2026-10-04). Cheapest test: Ask 5 sellers',
    ))
    db.add(models.Claim(
        statement="Legacy operational question",
        normalized_statement="legacy operational question",
        epistemic_state="blocked",
        confidence=0.0,
        provenance="ops review",
    ))
    db.commit()

    for client in _client(db):
        resp = client.get("/forge/unknowns")

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 2

    d60 = next(i for i in items if i["row_id"] == "D60")
    assert d60["question"] == "What is the actual COD remittance window?"
    assert d60["epistemic_state"] == "unknown"  # the truth label
    assert "Ask 5 sellers" in d60["cheapest_test"]
    assert "UNKNOWN_MAP.md" in (d60["provenance"] or "")  # the source

    legacy = next(i for i in items if i["row_id"] != "D60")
    assert legacy["epistemic_state"] == "blocked"


def test_unknowns_empty_state_is_honest(db):
    settings.FORGEOS_LEGACY_INTELLIGENCE_ENABLED = True
    for client in _client(db):
        resp = client.get("/forge/unknowns")
    assert resp.status_code == 200
    assert resp.json() == []
