import json

from app.api.earn import EarningOfferCreate, EarningOfferStatusUpdate, create_offer, update_offer_status
from app.services.revenue_miner import mine_revenue_proposals


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


def test_miner_proposes_review_for_recorded_paid_offer_without_executing(db):
    offer = create_offer(payload(), db)
    update_offer_status(
        offer.id,
        EarningOfferStatusUpdate(
            workspace_key=payload().workspace_key,
            status="customer_confirmed",
        ),
        db,
    )
    update_offer_status(
        offer.id,
        EarningOfferStatusUpdate(
            workspace_key=payload().workspace_key,
            status="paid",
            outcome_note="Customer paid in cash.",
        ),
        db,
    )

    proposals = mine_revenue_proposals(db)

    assert len(proposals) == 1
    assert proposals[0].status == "PROPOSED"
    assert proposals[0].policy_result == "ALLOW"
    assert proposals[0].verification_state == "UNVERIFIED"
    assert proposals[0].execution_result is None
    assert proposals[0].parameters_json


def test_miner_is_idempotent_and_ignores_drafts(db):
    draft = create_offer(payload(), db)
    assert mine_revenue_proposals(db) == []

    update_offer_status(
        draft.id,
        EarningOfferStatusUpdate(
            workspace_key=payload().workspace_key,
            status="customer_confirmed",
        ),
        db,
    )
    update_offer_status(
        draft.id,
        EarningOfferStatusUpdate(
            workspace_key=payload().workspace_key,
            status="paid",
            outcome_note="Paid in cash.",
        ),
        db,
    )
    assert len(mine_revenue_proposals(db)) == 1
    assert mine_revenue_proposals(db) == []


def _mark_paid(db, offer):
    update_offer_status(
        offer.id,
        EarningOfferStatusUpdate(
            workspace_key=payload().workspace_key,
            status="customer_confirmed",
        ),
        db,
    )
    update_offer_status(
        offer.id,
        EarningOfferStatusUpdate(
            workspace_key=payload().workspace_key,
            status="paid",
            outcome_note="Customer paid in cash.",
        ),
        db,
    )


def test_two_paid_offers_on_one_pathway_add_one_ownership_review(db):
    first = create_offer(payload(), db)
    second = create_offer(
        payload().model_copy(update={"title": "Menu board for the same cafe"}),
        db,
    )
    _mark_paid(db, first)
    _mark_paid(db, second)

    proposals = mine_revenue_proposals(db)
    kinds = [json.loads(proposal.parameters_json)["proposal_kind"] for proposal in proposals]

    assert sorted(kinds) == ["ownership_review", "repeatability_review", "repeatability_review"]
    assert mine_revenue_proposals(db) == []
    joined = " ".join(proposal.parameters_json for proposal in proposals)
    assert "local cafe owner" not in joined


def test_revenue_miner_worker_does_not_schedule_followups(db):
    from app.models import WorkerTask
    from app.services.worker_manager import revenue_miner_handler

    task = WorkerTask(worker_type="revenue_miner", task_name="mine_recorded_paid_offers", priority=1, inputs={})
    db.add(task)
    db.commit()
    result = revenue_miner_handler(db, task)

    assert result["executed"] is False
    assert result["proposals_created"] == 0
    assert db.query(WorkerTask).count() == 1


def test_public_revenue_miner_counts_reviews_without_customer_or_price(db):
    from fastapi.testclient import TestClient
    from app.database import get_db
    from app.main import app

    def override():
        yield db

    app.dependency_overrides[get_db] = override
    try:
        client = TestClient(app)
        empty = client.get("/public/revenue-miner")
        assert empty.status_code == 200
        body = empty.json()
        assert set(body) == {
            "paid_offers_recorded",
            "repeatability_reviews",
            "ownership_reviews",
            "note",
        }
        assert body["paid_offers_recorded"] == 0
        assert "income" in body["note"]

        offer = create_offer(payload(), db)
        _mark_paid(db, offer)
        mine_revenue_proposals(db)
        filled = client.get("/public/revenue-miner")
        text = filled.text
        assert filled.status_code == 200
        assert filled.json()["paid_offers_recorded"] == 1
        assert filled.json()["repeatability_reviews"] == 1
        assert filled.json()["ownership_reviews"] == 0
        assert "local cafe owner" not in text
        assert "1500" not in text
    finally:
        app.dependency_overrides.clear()


def test_cycle_runs_the_miner_and_does_not_invent_a_paid_offer(db):
    from app.services import forge_loop

    summary = forge_loop.run_cycle(db)
    assert summary["revenue_miner"]["executed"] is False
    assert summary["revenue_miner"]["proposals_created"] == 0
