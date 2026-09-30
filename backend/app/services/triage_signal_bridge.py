"""Persist a paid evidence-triage result into the existing discovery loop.

The proxy returns the TypeScript triage JSON to the buyer. This module
stores the raw text and the extraction as a Signal, then runs the
existing opportunity discovery and action evaluation. It does not start
actions, contact anyone, or write revenue.
"""

import json
import logging

from sqlalchemy.orm import Session

from app import models
from app.services import autonomy_engine, execution_engine, opportunity_engine
from app.services.observer_engine import ObserverEngine

logger = logging.getLogger(__name__)

SOURCE = "evidence_triage"


def record_paid_triage(db: Session, request_body: dict, triage_body: dict) -> dict:
    text = request_body.get("text")
    if not isinstance(text, str) or not text.strip():
        return {"persisted": False, "reason": "no text"}
    evidence = triage_body.get("evidence")
    if not isinstance(evidence, dict):
        return {"persisted": False, "reason": "no extraction"}

    fulfillment_id = triage_body.get("fulfillment_id")
    reliability = request_body.get("source_reliability")
    metadata = {
        "source_type": "external",
        "external_id": str(fulfillment_id) if fulfillment_id else None,
        "provenance": {
            "kind": "paid_evidence_triage",
            "fulfillment_id": fulfillment_id,
            "input_hash": triage_body.get("input_hash"),
            "output_hash": triage_body.get("output_hash"),
            "source_kind": request_body.get("source_kind"),
            "source_reliability": reliability if isinstance(reliability, (int, float)) else None,
            "extraction": evidence,
            "eligibility": triage_body.get("eligibility"),
        },
    }
    # Observer requires canonical_url for source_type external. Paid triage
    # has no URL; store it as a manual observation with the fulfillment id.
    metadata["source_type"] = "manual"
    signal = ObserverEngine(db).observe(text.strip(), source=SOURCE, metadata=metadata)

    discovery = opportunity_engine.run_autonomous_opportunity_discovery(db)
    opportunity = _opportunity_for_signal(db, signal.id)

    action = None
    if opportunity is not None:
        autonomy_engine.seed_default_policy(db)
        action = (
            db.query(models.Experiment)
            .filter_by(opportunity_id=opportunity.id, action_type="customer_interview")
            .order_by(models.Experiment.id.asc())
            .first()
        )
        if action is None:
            action = execution_engine.create_action(
                db,
                opportunity.id,
                "customer_interview",
                f'Approval required before any contact about "{opportunity.problem[:80]}"',
                estimated_cost=0.0,
            )

    return {
        "persisted": True,
        "signal_id": signal.id,
        "opportunity_id": opportunity.id if opportunity else None,
        "action_id": action.id if action else None,
        "policy_decision": action.policy_decision if action else None,
        "action_status": action.status if action else None,
        "discovery": discovery,
    }


def _opportunity_for_signal(db: Session, signal_id: int):
    needle = str(signal_id)
    for opportunity in db.query(models.Opportunity).all():
        raw = opportunity.problem_evidence_signal_ids or ""
        ids = {part.strip() for part in raw.split(",") if part.strip()}
        if needle in ids:
            return opportunity
    return None


def safe_record_paid_triage(db: Session, raw_request: bytes, raw_response: bytes, status_code: int) -> None:
    """Best-effort hook for the HTTP proxy. A persistence failure must not
    change the paid response the buyer already earned."""
    if status_code != 200:
        return
    try:
        request_body = json.loads(raw_request.decode("utf-8"))
        triage_body = json.loads(raw_response.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return
    if not isinstance(request_body, dict) or not isinstance(triage_body, dict):
        return
    try:
        record_paid_triage(db, request_body, triage_body)
    except Exception:
        db.rollback()
        logger.exception("paid triage signal bridge failed")
