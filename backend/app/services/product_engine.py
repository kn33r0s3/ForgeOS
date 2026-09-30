"""Product / Distribution / Customer workflow engine.

Turns validated-pain Opportunities into concrete, tracked Products and an
honest distribution ledger. THE CARDINAL RULE, matching the rest of ForgeOS:

    A Product's revenue/customer/cost numbers are NEVER fabricated.
    They are rolled up ONLY from real Outcome rows of type ACTUAL_* that
    carry this product's product_id. Zero invoices, zero customers, until a
    real Outcome records one. (This is the anti-fake-metrics guarantee.)

The Product entity formalizes the discovery->build->distribute handoff:
- Opportunity = named problem + customer + willingness to pay (detected).
- Product    = the concrete offer + launch state we choose to build & ship.
- Channel    = one distribution channel for that product (a campaign leaf).
- CustomerEvent = ground-truth ledger of who was actually reached & where
  they are in the funnel (lead -> paid_customer). Only real contacts.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app import models


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

def create_product(db: Session, *, opportunity_id=None, goal_id=None,
                   name, offer, target_customer=None, pricing=None,
                   mvp_scope=None, hypothesis=None, launch_state="not_launched",
                   data_scope="REAL") -> models.Product:
    data_scope = _scope(data_scope)
    if launch_state not in (None, "not_launched"):
        raise ValueError("New offers must begin unlaunched; validate first")
    p = models.Product(
        opportunity_id=opportunity_id,
        goal_id=goal_id,
        name=name,
        offer=offer,
        target_customer=target_customer,
        pricing=pricing,
        mvp_scope=mvp_scope,
        hypothesis=hypothesis,
        status="concept",
        launch_state=launch_state,
        data_scope=data_scope,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def get_product(db: Session, product_id: int) -> Optional[models.Product]:
    return db.query(models.Product).filter_by(id=product_id).first()


def list_products(db: Session) -> list[models.Product]:
    return db.query(models.Product).order_by(models.Product.created_at.desc()).all()


def update_product(db: Session, product_id: int, *, name=None, offer=None,
                   target_customer=None, pricing=None, mvp_scope=None,
                   hypothesis=None, status=None, launch_state=None,
                   retirement_reason=None) -> Optional[models.Product]:
    p = get_product(db, product_id)
    if p is None:
        return None
    if status is not None and status not in {"concept", "validating", "launched", "iterating", "retired"}:
        raise ValueError("Invalid product status")
    if launch_state is not None and launch_state not in {"not_launched", "piloting", "public", "paused"}:
        raise ValueError("Invalid launch state")
    if status in {"launched", "iterating"} or launch_state in {"piloting", "public"}:
        from app.services import orchestrator
        if p.opportunity_id is None:
            raise ValueError("Link and validate an opportunity before launch")
        confirmed, willing = orchestrator.validation_counts(db, p.opportunity_id, p.data_scope)
        if confirmed < orchestrator.DEFAULT_Y_CONFIRM_PROBLEM or willing < orchestrator.DEFAULT_Z_WILLING_TO_PAY:
            raise ValueError("Recorded demand validation is required before launch")
    for field, val in {
        "name": name, "offer": offer, "target_customer": target_customer,
        "pricing": pricing, "mvp_scope": mvp_scope, "hypothesis": hypothesis,
        "status": status, "launch_state": launch_state,
        "retirement_reason": retirement_reason,
    }.items():
        if val is not None:
            setattr(p, field, val)
    if status == "retired":
        from datetime import datetime, timezone
        p.retired_at = datetime.now(timezone.utc)
    p.updated_at = _now()
    db.commit()
    db.refresh(p)
    return p


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def rollup_product(db: Session, product: models.Product) -> dict:
    """Recount a product's REAL numbers from its ACTUAL outcomes only.

    Never a cached/derived guess — always a fresh query over the product's
    own Outcome rows whose outcome_type is one of ACTUAL_*. Returns the
    field values that should be persisted back to the Product row.
    """
    rows = db.query(models.Outcome).filter_by(product_id=product.id, data_scope=product.data_scope).all()
    revenue = 0.0
    cost = 0.0
    customers = 0
    for o in rows:
        if o.outcome_type == "ACTUAL_REVENUE" and o.actual_value is not None and (o.unit or "USD").upper() == "USD":
            revenue += o.actual_value
        elif o.outcome_type == "ACTUAL_COST" and o.actual_value is not None and (o.unit or "USD").upper() == "USD":
            cost += o.actual_value
        elif o.outcome_type == "ACTUAL_CUSTOMERS" and o.actual_value is not None:
            customers += int(o.actual_value)
    return {"actual_revenue": revenue, "actual_cost": cost, "actual_customers": customers}


def product_summary(db: Session, product: models.Product) -> dict:
    """Persist the honest rollup back onto the product row, then return it."""
    nums = rollup_product(db, product)
    # GET summaries compute rollups without mutating rows or committing.

    channels = db.query(models.DistributionChannel).filter_by(product_id=product.id).all()
    leads = (
        db.query(models.CustomerEvent)
        .filter_by(product_id=product.id)
        .filter(models.CustomerEvent.stage.in_(["lead", "contacted", "interested"]))
        .count()
    )
    paid = (
        db.query(models.CustomerEvent)
        .filter_by(product_id=product.id, stage="paid_customer")
        .count()
    )
    return {
        "id": product.id,
        "opportunity_id": product.opportunity_id,
        "goal_id": product.goal_id,
        "name": product.name,
        "offer": product.offer,
        "target_customer": product.target_customer,
        "pricing": product.pricing,
        "mvp_scope": product.mvp_scope,
        "status": product.status,
        "launch_state": product.launch_state,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
        "retired_at": product.retired_at,
        "retirement_reason": product.retirement_reason,
        "hypothesis": product.hypothesis,
        "data_scope": product.data_scope,
        "offer_brief": product.offer_brief,
        "approval_status": product.approval_status,
        "approval_note": product.approval_note,
        "approved_at": product.approved_at,
        "actual_customers": nums["actual_customers"],
        "actual_revenue": nums["actual_revenue"],
        "actual_cost": nums["actual_cost"],
        "channel_count": len(channels),
        "lead_count": leads,
        "paid_customer_count": paid,
    }


# ---------------------------------------------------------------------------
# Distribution channels
# ---------------------------------------------------------------------------

def create_channel(db: Session, *, product_id=None, opportunity_id=None,
                   channel_type, name, description=None, status="planned",
                   action_id=None, data_scope="REAL") -> models.DistributionChannel:
    data_scope = _scope(data_scope)
    if product_id:
        parent = _parent(db, models.Product, product_id, data_scope)
        opportunity_id = opportunity_id or parent.opportunity_id
    c = models.DistributionChannel(
        product_id=product_id,
        opportunity_id=opportunity_id,
        channel_type=channel_type,
        name=name,
        description=description,
        status=status,
        action_id=action_id,
        data_scope=data_scope,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def update_channel(db: Session, channel_id: int, *, status=None, name=None,
                   description=None) -> Optional[models.DistributionChannel]:
    c = db.query(models.DistributionChannel).filter_by(id=channel_id).first()
    if c is None:
        return None
    for field, val in {"status": status, "name": name, "description": description}.items():
        if val is not None:
            setattr(c, field, val)
    c.updated_at = _now()
    db.commit()
    db.refresh(c)
    return c


def rollup_channel(db: Session, channel: models.DistributionChannel) -> dict:
    """Recount a channel's real funnel numbers from its CustomerEvents.

    Honest derivation only: outreach = real contacts logged, response =
    events that moved past 'lead', conversion = events that became
    'paid_customer'. Never invented.
    """
    events = db.query(models.CustomerEvent).filter_by(channel_id=channel.id, data_scope=channel.data_scope).all()
    outreach = len([e for e in events if e.stage != "lead"])
    response = conv = 0
    for e in events:
        if e.stage in ("contacted", "interested", "paid_customer"):
            response += 1
        if e.stage == "paid_customer":
            conv += 1
    return {
        "id": channel.id, "product_id": channel.product_id,
        "opportunity_id": channel.opportunity_id, "channel_type": channel.channel_type,
        "name": channel.name, "description": channel.description, "status": channel.status,
        "action_id": channel.action_id, "created_at": channel.created_at,
        "updated_at": channel.updated_at, "data_scope": channel.data_scope, "outreach_count": len(events),
        "response_count": response, "conversion_count": conv,
    }


# ---------------------------------------------------------------------------
# Customer ledger
# ---------------------------------------------------------------------------

def create_customer_event(db: Session, *, product_id=None, channel_id=None,
                          opportunity_id=None, contact_name=None,
                          contact_identifier=None, segment=None,
                          stage="lead", event_type=None, notes=None,
                          action_id=None, outcome_id=None, data_scope="REAL", commit=True) -> models.CustomerEvent:
    data_scope = _scope(data_scope)
    if stage not in {"lead", "contacted", "interested", "paid_customer", "churned"}:
        raise ValueError("Invalid customer event stage")
    if channel_id:
        channel = _parent(db, models.DistributionChannel, channel_id, data_scope)
        if product_id and product_id != channel.product_id:
            raise ValueError("Customer event product must match channel")
        product_id = product_id or channel.product_id
        opportunity_id = opportunity_id or channel.opportunity_id
    if product_id:
        product = _parent(db, models.Product, product_id, data_scope)
        opportunity_id = opportunity_id or product.opportunity_id
    outcome = None
    if outcome_id:
        outcome = _parent(db, models.Outcome, outcome_id, data_scope)
    action = None
    if action_id:
        action = db.get(models.Action, action_id)
        if action is None:
            raise ValueError("Linked action does not exist")
        if action.experiment_id:
            experiment = db.get(models.Experiment, action.experiment_id)
            if experiment is None or experiment.data_scope != data_scope:
                raise ValueError("Linked action experiment does not exist or scope does not match")
    if stage == "contacted":
        action_started = bool(
            action is not None
            and action.experiment_id is not None
            and action.started_at is not None
            and (
                action.policy_result == "ALLOW"
                or (
                    action.policy_result == "REQUIRE_APPROVAL"
                    and action.approved_at is not None
                )
            )
        )
        response_recorded = bool(
            outcome is not None
            and outcome.outcome_type == "ACTUAL_RESPONSE"
            and outcome.verification_state != "DISPUTED"
            and (outcome.qualitative_result or "").strip()
        )
        if not action_started and not response_recorded:
            raise ValueError("contacted stage requires a recorded authorized action or response outcome")
    elif stage == "interested":
        if not (
            outcome is not None
            and outcome.outcome_type == "ACTUAL_RESPONSE"
            and outcome.verification_state != "DISPUTED"
            and (outcome.qualitative_result or "").strip()
        ):
            raise ValueError("interested stage requires a linked actual response outcome")
    elif stage == "paid_customer":
        if not (
            outcome is not None
            and outcome.outcome_type == "ACTUAL_REVENUE"
            and outcome.verification_state == "VERIFIED"
            and outcome.actual_value is not None
            and outcome.actual_value > 0
        ):
            raise ValueError("paid_customer stage requires linked verified positive revenue evidence")
    elif stage == "churned":
        if outcome is None:
            raise ValueError("churned stage requires a linked outcome")
    ev = models.CustomerEvent(
        product_id=product_id,
        channel_id=channel_id,
        opportunity_id=opportunity_id,
        contact_name=contact_name,
        contact_identifier=contact_identifier,
        segment=segment,
        stage=stage,
        event_type=event_type,
        notes=notes,
        action_id=action_id,
        outcome_id=outcome_id,
        data_scope=data_scope,
    )
    db.add(ev)
    db.commit() if commit else db.flush()
    return ev


# ---------------------------------------------------------------------------
# Pipeline snapshot
# ---------------------------------------------------------------------------

def pipeline(db: Session) -> dict:
    products = db.query(models.Product).order_by(models.Product.created_at.desc()).all()
    summaries = [product_summary(db, p) for p in products]
    channels = db.query(models.DistributionChannel).order_by(models.DistributionChannel.created_at.desc()).all()
    events = db.query(models.CustomerEvent).order_by(models.CustomerEvent.created_at.desc()).all()

    channel_dicts = [rollup_channel(db, c) for c in channels]
    real_summaries = [x for x in summaries if x["data_scope"] == "REAL"]
    real_channels = [x for x in channel_dicts if x["data_scope"] == "REAL"]
    real_events = [x for x in events if x.data_scope == "REAL"]
    sandbox_summaries = [x for x in summaries if x["data_scope"] == "SANDBOX"]

    def ev(out):
        return {
            "id": out.id, "product_id": out.product_id, "channel_id": out.channel_id,
            "opportunity_id": out.opportunity_id, "contact_name": out.contact_name,
            "contact_identifier": out.contact_identifier, "segment": out.segment,
            "stage": out.stage, "event_type": out.event_type, "notes": out.notes,
            "action_id": out.action_id, "outcome_id": out.outcome_id,
            "occurred_at": out.occurred_at, "created_at": out.created_at,
            "data_scope": out.data_scope,
        }

    totals = {
        "total_products": len(real_summaries),
        "launched_products": sum(
            1 for s in real_summaries if s["status"] in ("launched", "iterating")
            and s["launch_state"] in ("piloting", "public")
        ),
        "total_outreach": sum(c["outreach_count"] for c in real_channels),
        "total_leads": sum(s["lead_count"] for s in real_summaries),
        "total_paid_customers": sum(s["paid_customer_count"] for s in real_summaries),
        "realized_revenue": round(sum(s["actual_revenue"] for s in real_summaries), 2),
        "sandbox_revenue": round(sum(s["actual_revenue"] for s in sandbox_summaries), 2),
        "sandbox_products": len(sandbox_summaries),
    }

    return {
        "products": summaries,
        "channels": channel_dicts,
        "customer_events": [ev(e) for e in events],
        **totals,
    }



def _scope(scope):
    if scope not in {"REAL", "SANDBOX"}:
        raise ValueError("data_scope must be REAL or SANDBOX")
    return scope


def _parent(db, model, id, scope):
    row = db.get(model, id)
    if row is None or row.data_scope != scope:
        raise ValueError("Linked record does not exist or scope does not match")
    return row
