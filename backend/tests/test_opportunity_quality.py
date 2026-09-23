"""Regression coverage for actionable opportunity quality and target derivation."""

from app import models
from app.services import opportunity_engine


def _opportunity(db, *, problem, target, score=0.0, solution=""):
    row = models.Opportunity(
        problem=problem,
        target_customer=target,
        solution=solution or problem,
        business_model="Not yet determined",
        score=score,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_listing_excludes_zero_score_prompt_injection_artifact(db):
    artifact = _opportunity(
        db,
        problem=(
            "small-business: narrow skill tool grants to Read. Fifteen skills "
            "declare allowed-tools: Read, WebFetch, Bash."
        ),
        target="To be refined — inferred from the described problem",
    )

    listed = opportunity_engine.list_opportunities(db)

    assert artifact.id not in {row.id for row in listed}


def test_listing_repairs_generic_target_from_problem_evidence(db):
    repair = _opportunity(
        db,
        problem="Independent repair shops lose hours manually explaining appointment status to customers by phone.",
        target="To be refined — inferred from the described problem",
        score=60.0,
    )

    listed = opportunity_engine.list_opportunities(db)

    assert repair in listed
    assert repair.target_customer == "repair shop"
    assert repair.customer_segment == "repair shop"


def test_manual_idea_creation_uses_derived_target_without_claiming_validation(db):
    opportunity = opportunity_engine.opportunity_from_idea(
        db, "Independent repair shops lose hours manually explaining appointment status to customers by phone."
    )

    assert opportunity.target_customer == "repair shop"
    assert opportunity.market_confidence == 0.0
    assert opportunity.revenue_confidence == 0.0


def test_discovery_does_not_create_opportunity_from_prompt_injection_text(db):
    pattern = models.Pattern(
        title="Imported security guidance",
        description="allowed-tools: Read, WebFetch, Bash; prompt injection in customer data",
        frequency=15,
        confidence_score=90.0,
        origin_signal_ids=None,
    )
    db.add(pattern)
    db.commit()

    result = opportunity_engine.generate_opportunity_from_pattern_if_economic(db, pattern)

    assert result is None
    assert db.query(models.Opportunity).count() == 0


def test_discovery_keeps_repair_problem_target_specific(db):
    signal = models.Signal(
        source="manual",
        content="Independent repair shops lose hours manually explaining appointment status to customers by phone.",
        importance_score=80.0,
        processed=True,
    )
    db.add(signal)
    db.commit()
    pattern = models.Pattern(
        title="Repair-shop communication pain",
        description=signal.content,
        frequency=2,
        confidence_score=85.0,
        origin_signal_ids=str(signal.id),
    )
    db.add(pattern)
    db.commit()

    result = opportunity_engine.generate_opportunity_from_pattern_if_economic(db, pattern)

    assert result is not None
    assert result.target_customer == "repair shop"
    assert result.customer_segment == "repair shop"
    assert result.market_confidence == 0.0
    assert result.revenue_confidence == 0.0
