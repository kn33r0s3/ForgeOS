"""Mine recorded earning outcomes into reviewable revenue proposals.

This worker searches ForgeOS records, not markets or wallets. It never sends
messages, places orders, moves money, or treats a stated price as verified
revenue.
"""

from sqlalchemy.orm import Session

from app import models
from app.services import action_engine


def mine_revenue_proposals(db: Session, *, limit: int = 20) -> list[models.Action]:
    """Propose repeatability reviews for recorded paid offers.

    Each source offer produces at most one proposal. A human must review the
    proposal and record new evidence before any further action is considered.
    """
    if limit < 1:
        raise ValueError("limit must be positive")

    offers = (
        db.query(models.EarningOffer)
        .filter(models.EarningOffer.status == "paid")
        .order_by(models.EarningOffer.updated_at.desc())
        .limit(limit)
        .all()
    )
    proposals: list[models.Action] = []
    for offer in offers:
        marker = f'"source_earning_offer_id": {offer.id}'
        existing = (
            db.query(models.Action)
            .filter(models.Action.action_type == "manual_note")
            .filter(models.Action.parameters_json.contains(marker))
            .first()
        )
        if existing:
            continue

        proposal = action_engine.propose_action(
            db,
            objective=(
                f"Review whether earning offer {offer.id} is repeatable using "
                "new human evidence; do not assume another sale."
            ),
            action_type="manual_note",
            parameters={
                "source_earning_offer_id": offer.id,
                "proposal_kind": "repeatability_review",
                "recorded_status": offer.status,
                "stated_price_npr": offer.price_npr,
                "next_step": "Record a separate real customer response or refusal.",
            },
            estimated_cost=0.0,
            risk_score=10.0,
        )
        proposals.append(proposal)

    counts: dict[str, int] = {}
    for offer in offers:
        counts[offer.pathway] = counts.get(offer.pathway, 0) + 1
    for pathway, count in counts.items():
        if count < 2:
            continue
        marker = f'"ownership_pathway": "{pathway}"'
        existing = (
            db.query(models.Action)
            .filter(models.Action.action_type == "manual_note")
            .filter(models.Action.parameters_json.contains(marker))
            .first()
        )
        if existing:
            continue
        proposal = action_engine.propose_action(
            db,
            objective=(
                f"Review whether repeated paid {pathway} work can become an owned checklist. "
                "This records demand that already happened. It is not a new sale."
            ),
            action_type="manual_note",
            parameters={
                "proposal_kind": "ownership_review",
                "ownership_pathway": pathway,
                "paid_offer_count": count,
                "next_step": "A person reviews the repeated paid work. The miner does not create an asset or a price.",
            },
            estimated_cost=0.0,
            risk_score=10.0,
        )
        proposals.append(proposal)
    return proposals


def revenue_miner_public_summary(db: Session) -> dict:
    """Counts only. No customer, price, title, or claimed income."""
    paid = (
        db.query(models.EarningOffer)
        .filter(models.EarningOffer.status == "paid")
        .count()
    )
    notes = db.query(models.Action).filter(models.Action.action_type == "manual_note")
    repeatability = notes.filter(
        models.Action.parameters_json.contains('"proposal_kind": "repeatability_review"')
    ).count()
    ownership = (
        db.query(models.Action)
        .filter(models.Action.action_type == "manual_note")
        .filter(models.Action.parameters_json.contains('"proposal_kind": "ownership_review"'))
        .count()
    )
    return {
        "paid_offers_recorded": paid,
        "repeatability_reviews": repeatability,
        "ownership_reviews": ownership,
        "note": (
            "The miner only reviews offers already marked paid. "
            "It does not create income, send messages, or move money."
        ),
    }
