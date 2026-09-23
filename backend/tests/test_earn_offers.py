import pytest
from fastapi import HTTPException

from app.api.earn import (
    ChecklistItem,
    EarningOfferChecklistUpdate,
    EarningOfferCreate,
    EarningOfferStatusUpdate,
    create_offer,
    list_offers,
    update_offer_checklist,
    update_offer_status,
)


def payload(key="workspace-token-123456"):
    return EarningOfferCreate(
        workspace_key=key,
        pathway="local-service",
        title="Three social posts for a cafe",
        skill="Can design in Canva",
        customer="local cafe owner",
        price_npr=1500,
        age_band="18_plus",
    )


def test_offer_persists_and_is_scoped_to_workspace(db):
    row = create_offer(payload(), db)
    assert row.status == "draft"
    assert row.next_actions
    assert [x.id for x in list_offers(payload().workspace_key, db)] == [row.id]
    assert list_offers("another-workspace-token-123", db) == []


def test_status_progression_is_enforced_server_side(db):
    row = create_offer(payload(), db)
    with pytest.raises(HTTPException) as exc:
        update_offer_status(row.id, EarningOfferStatusUpdate(
            workspace_key=payload().workspace_key, status="paid", outcome_note="Paid in cash"
        ), db)
    assert exc.value.status_code == 409

    row = update_offer_status(row.id, EarningOfferStatusUpdate(
        workspace_key=payload().workspace_key, status="customer_confirmed"
    ), db)
    assert row.status == "customer_confirmed"
    row = update_offer_status(row.id, EarningOfferStatusUpdate(
        workspace_key=payload().workspace_key, status="paid", outcome_note="NPR 1,500 received in cash"
    ), db)
    assert row.status == "paid"
    assert row.outcome_note == "NPR 1,500 received in cash"


def test_terminal_status_requires_an_honest_outcome_note(db):
    row = create_offer(payload(), db)
    with pytest.raises(HTTPException) as exc:
        update_offer_status(row.id, EarningOfferStatusUpdate(
            workspace_key=payload().workspace_key, status="failed"
        ), db)
    assert exc.value.status_code == 422


def test_terminal_status_cannot_be_rewritten(db):
    row = create_offer(payload(), db)
    row = update_offer_status(row.id, EarningOfferStatusUpdate(
        workspace_key=payload().workspace_key, status="failed", outcome_note="Customer declined the price"
    ), db)
    with pytest.raises(HTTPException) as exc:
        update_offer_status(row.id, EarningOfferStatusUpdate(
            workspace_key=payload().workspace_key, status="paid", outcome_note="Later payment"
        ), db)
    assert exc.value.status_code == 409


def test_per_offer_checklist_is_persisted_and_workspace_scoped(db):
    row = create_offer(payload(), db)
    items = [
        ChecklistItem(text="Visit the cafe", completed=True),
        ChecklistItem(text="Ask for a paid trial", completed=False),
    ]
    updated = update_offer_checklist(row.id, EarningOfferChecklistUpdate(
        workspace_key=payload().workspace_key, next_actions=items
    ), db)
    assert [item.completed for item in updated.next_actions] == [True, False]
    assert list_offers(payload().workspace_key, db)[0].next_actions[0].text == "Visit the cafe"

    with pytest.raises(HTTPException) as exc:
        update_offer_checklist(row.id, EarningOfferChecklistUpdate(
            workspace_key="another-workspace-token-123", next_actions=items
        ), db)
    assert exc.value.status_code == 404
