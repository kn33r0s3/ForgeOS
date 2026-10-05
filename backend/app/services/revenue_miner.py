"""Mine recorded earning outcomes into reviewable revenue proposals.

This worker searches ForgeOS records, not markets or wallets. It never sends
messages, places orders, moves money, or treats a stated price as verified
revenue.
"""

import json

from sqlalchemy.orm import Session

from app import models
from app.services import action_engine


def _proposal_params(db: Session, proposal_kind: str) -> list[dict]:
    """Decode parameters_json for every existing proposal of one kind.

    Deduplication compares decoded values, never substrings. The old
    `.contains(f'"source_earning_offer_id": {offer.id}')` check treated
    offer 1 as "already proposed" whenever offer 10, 11, or 100 had a
    row, because `"source_earning_offer_id": 1` is a prefix-substring of
    `"source_earning_offer_id": 10` — so real paid offers were silently
    never reviewed.
    """
    rows = (
        db.query(models.Action.parameters_json)
        .filter(models.Action.action_type == "manual_note")
        .filter(models.Action.parameters_json.contains(f'"proposal_kind": "{proposal_kind}"'))
        .all()
    )
    parsed = []
    for (raw,) in rows:
        try:
            data = json.loads(raw or "{}")
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            parsed.append(data)
    return parsed


def mine_revenue_proposals(db: Session, *, limit: int = 20) -> list[models.Action]:
    """Propose repeatability reviews for recorded paid offers.

    Each source offer produces at most one proposal. A human must review the
    proposal and record new evidence before any further action is considered.

    The limit caps how many NEW proposals one run creates. Pathway
    repeatability counts are always computed over every paid offer, never
    over the capped query — otherwise the miner's picture of the data would
    be an artifact of the cap, and older offers would starve under a small
    limit.
    """
    if limit < 1:
        raise ValueError("limit must be positive")

    offers = (
        db.query(models.EarningOffer)
        .filter(models.EarningOffer.status == "paid")
        .order_by(models.EarningOffer.updated_at.desc())
        .all()
    )

    reviewed_offer_ids = {
        params.get("source_earning_offer_id")
        for params in _proposal_params(db, "repeatability_review")
    }

    proposals: list[models.Action] = []
    for offer in offers:
        if offer.id in reviewed_offer_ids:
            continue
        if len(proposals) >= limit:
            break

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
        reviewed_offer_ids.add(offer.id)

    counts: dict[str, int] = {}
    for offer in offers:
        counts[offer.pathway] = counts.get(offer.pathway, 0) + 1

    reviewed_pathways = {
        params.get("ownership_pathway")
        for params in _proposal_params(db, "ownership_review")
    }
    for pathway, count in counts.items():
        if count < 2 or pathway in reviewed_pathways:
            continue
        if len(proposals) >= limit:
            break
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
        reviewed_pathways.add(pathway)
    return proposals


def revenue_miner_public_summary(db: Session) -> dict:
    """Counts only. No customer, price, title, or claimed income."""
    paid = (
        db.query(models.EarningOffer)
        .filter(models.EarningOffer.status == "paid")
        .count()
    )
    # Exact decoded comparison, not substring matching: the dedup path
    # above fixed this class of bug once already (offer 1 vs 10), and a
    # public counter must not inflate if the literal phrase ever lands
    # in a free-text parameters field.
    repeatability = sum(
        1 for params in _proposal_params(db, "repeatability_review")
        if params.get("proposal_kind") == "repeatability_review"
    )
    ownership = sum(
        1 for params in _proposal_params(db, "ownership_review")
        if params.get("proposal_kind") == "ownership_review"
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
