import json
from unittest.mock import MagicMock

import pytest

from app import models, security
from app.api.products import (
    create_offer_draft,
    update_offer_approval,
)
from app.schemas import OfferApprovalUpdate, OfferDraftCreate
from app.services import offer_preparation


@pytest.fixture
def owner_request(monkeypatch):
    """Mock owner request presenting the key (products writes are owner-keyed, Step 1)."""
    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "offer-test-key")
    req = MagicMock()
    req.headers = {"X-API-Key": "offer-test-key"}
    return req


def test_owner_problem_becomes_reviewable_offer_without_commercial_claims(db, owner_request):
    product = create_offer_draft(
        owner_request,
        OfferDraftCreate(
            problem="A repair shop loses time following up on missed appointments.",
            target_customer="independent repair shop",
            data_scope="SANDBOX",
        ),
        db,
    )

    assert product.approval_status == "PENDING_REVIEW"
    assert product.offer_brief["problem_statement"].startswith("A repair shop")
    assert product.offer_brief["price_hypothesis"].startswith("UNRESOLVED")
    assert "No automatic external outreach" in product.offer_brief["exclusions"]
    assert db.query(models.CustomerEvent).count() == 0
    assert db.query(models.Outcome).count() == 0
    assert db.query(models.Action).count() == 0


def test_offer_approval_is_persisted_and_does_not_execute_action(db, owner_request):
    product = create_offer_draft(
        owner_request,
        OfferDraftCreate(
            problem="A business needs a clearer internal reporting workflow.",
            data_scope="SANDBOX",
        ),
        db,
    )
    approved = update_offer_approval(
        owner_request,
        product.id,
        OfferApprovalUpdate(status="APPROVED", note="Owner can deliver the review manually."),
        db,
    )
    assert approved.approval_status == "APPROVED"
    assert approved.approved_at is not None
    assert approved.approval_note.startswith("Owner can")

    db.expire_all()
    reopened = db.get(models.Product, product.id)
    assert reopened.approval_status == "APPROVED"
    assert json.loads(reopened.offer_brief_json)["authorization_requirements"]
    assert db.query(models.Action).count() == 0


def test_offer_draft_capability_inventory_reports_real_availability(db):
    inventory = offer_preparation._capability_inventory()
    assert inventory
    assert all(item["status"] in {"currently_available", "possible"} for item in inventory)
    assert any(item["name"] == "offline-mock" and item["status"] == "currently_available" for item in inventory)
