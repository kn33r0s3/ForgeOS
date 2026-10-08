"""Product / Distribution / Customer-workflow API.

Facilitates the discovery -> build -> distribute -> measure -> learn loop at
the product layer. All revenue/customer metrics are evidence-gated: they come
only from real ACTUAL_* Outcome rows, never fabricated by this system.

    POST   /products                 -> form a concrete Offer from an Opportunity
    GET    /products                 -> list products (+ honest rollup)
    GET    /products/pipeline        -> consolidated build->distribute snapshot
    GET    /products/channels        -> list distribution channels
    GET    /products/customers       -> list customer ledger
    GET    /products/{id}            -> one product with rollup
    PATCH  /products/{id}            -> update name/status/launch state/etc
    POST   /products/{id}/channels   -> add a distribution channel
    PATCH  /products/channels/{id}   -> update channel status
    POST   /products/channels/{id}/customers -> log a real customer/lead contact
    POST   /products/customers       -> log a real customer/lead (global)
"""


from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app import schemas, models, security
from app.services import product_engine
from app.services import offer_preparation

router = APIRouter(prefix="/products", tags=["products"])


def _owner(request: Request) -> None:
    security.require_owner_api_key(request)


# ----------------------------------------------------------------- products
@router.post("", response_model=schemas.ProductOut)
def create_product(request: Request, body: schemas.ProductCreate, db: Session = Depends(get_db)):
    _owner(request)
    if body.opportunity_id is not None:
        opp = db.query(models.Opportunity).filter_by(id=body.opportunity_id).first()
        if opp is None:
            raise HTTPException(404, "opportunity not found")
    return product_engine.create_product(
        db,
        opportunity_id=body.opportunity_id,
        goal_id=body.goal_id,
        name=body.name,
        offer=body.offer,
        target_customer=body.target_customer,
        pricing=body.pricing,
        mvp_scope=body.mvp_scope,
        hypothesis=body.hypothesis,
        launch_state=body.launch_state,
        data_scope=body.data_scope,
    )


@router.post("/offer-drafts", response_model=schemas.ProductOut, status_code=201)
def create_offer_draft(request: Request, body: schemas.OfferDraftCreate, db: Session = Depends(get_db)):
    _owner(request)
    """Prepare an owner-reviewable offer hypothesis without contacting anyone."""
    try:
        return offer_preparation.create_offer_draft(
            db,
            problem=body.problem,
            target_customer=body.target_customer,
            data_scope=body.data_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[schemas.ProductSummary])
def list_products(db: Session = Depends(get_db)):
    return [product_engine.product_summary(db, p) for p in product_engine.list_products(db)]


# ---- static paths MUST be declared before /{product_id} (route order) -----
@router.get("/pipeline", response_model=schemas.ProductPipeline)
def pipeline(db: Session = Depends(get_db)):
    return product_engine.pipeline(db)


@router.get("/channels", response_model=list[schemas.ChannelOut])
def list_channels(db: Session = Depends(get_db)):
    return [
        product_engine.rollup_channel(db, c)
        for c in db.query(models.DistributionChannel).order_by(models.DistributionChannel.created_at.desc()).all()
    ]


@router.get("/customers", response_model=list[schemas.CustomerEventOut])
def list_customers(db: Session = Depends(get_db)):
    return db.query(models.CustomerEvent).order_by(models.CustomerEvent.created_at.desc()).all()


@router.post("/customers", response_model=schemas.CustomerEventOut)
def add_customer_event_global(request: Request, body: schemas.CustomerEventCreate, db: Session = Depends(get_db)):
    _owner(request)
    try:
        return product_engine.create_customer_event(
            db,
            product_id=body.product_id,
            channel_id=body.channel_id,
            opportunity_id=body.opportunity_id,
            contact_name=body.contact_name,
            contact_identifier=body.contact_identifier,
            segment=body.segment,
            stage=body.stage,
            event_type=body.event_type,
            notes=body.notes,
            action_id=body.action_id,
            outcome_id=body.outcome_id,
            data_scope=body.data_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/channels/{channel_id}", response_model=schemas.ChannelOut)
def update_channel(request: Request, channel_id: int, body: schemas.ChannelUpdate, db: Session = Depends(get_db)):
    _owner(request)
    c = product_engine.update_channel(
        db, channel_id,
        status=body.status, name=body.name, description=body.description,
    )
    if c is None:
        raise HTTPException(404, "channel not found")
    return product_engine.rollup_channel(db, c)


@router.post("/channels/{channel_id}/customers", response_model=schemas.CustomerEventOut)
def add_customer_event(request: Request, channel_id: int, body: schemas.CustomerEventCreate, db: Session = Depends(get_db)):
    _owner(request)
    ch = db.query(models.DistributionChannel).filter_by(id=channel_id).first()
    if ch is None:
        raise HTTPException(404, "channel not found")
    try:
        return product_engine.create_customer_event(
            db,
            product_id=ch.product_id or body.product_id,
            channel_id=channel_id,
            opportunity_id=body.opportunity_id or ch.opportunity_id,
            contact_name=body.contact_name,
            contact_identifier=body.contact_identifier,
            segment=body.segment,
            stage=body.stage,
            event_type=body.event_type,
            notes=body.notes,
            action_id=body.action_id,
            outcome_id=body.outcome_id,
            data_scope=body.data_scope,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# ---------------------------------------------------------------- product by id
@router.get("/{product_id}", response_model=schemas.ProductSummary)
def get_product(product_id: int, db: Session = Depends(get_db)):
    p = product_engine.get_product(db, product_id)
    if p is None:
        raise HTTPException(404, "product not found")
    return product_engine.product_summary(db, p)


@router.post("/{product_id}/offer-approval", response_model=schemas.ProductOut)
def update_offer_approval(
    request: Request,
    product_id: int,
    body: schemas.OfferApprovalUpdate,
    db: Session = Depends(get_db),
):
    _owner(request)
    product = offer_preparation.set_offer_approval(
        db, product_id, status=body.status, note=body.note
    )
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    return product


@router.patch("/{product_id}", response_model=schemas.ProductOut)
def update_product(request: Request, product_id: int, body: schemas.ProductUpdate, db: Session = Depends(get_db)):
    _owner(request)
    p = product_engine.update_product(
        db, product_id,
        name=body.name, offer=body.offer, target_customer=body.target_customer,
        pricing=body.pricing, mvp_scope=body.mvp_scope, hypothesis=body.hypothesis,
        status=body.status, launch_state=body.launch_state,
        retirement_reason=body.retirement_reason,
    )
    if p is None:
        raise HTTPException(404, "product not found")
    return p


@router.post("/{product_id}/channels", response_model=schemas.ChannelOut)
def add_channel(request: Request, product_id: int, body: schemas.ChannelCreate, db: Session = Depends(get_db)):
    _owner(request)
    if product_engine.get_product(db, product_id) is None:
        raise HTTPException(404, "product not found")
    return product_engine.create_channel(
        db,
        product_id=product_id,
        opportunity_id=body.opportunity_id,
        channel_type=body.channel_type,
        name=body.name,
        description=body.description,
        status=body.status,
        action_id=body.action_id,
        data_scope=body.data_scope,
    )
