from app import models
from app.services import money_engine


def _source(db, **overrides):
    fields = {
        "name": "Named channel",
        "source_type": "other",
        "payout_structure": "Unspecified.",
    }
    fields.update(overrides)
    row = models.RevenueSource(**fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_startup_does_not_insert_platform_payout_figures(db):
    money_engine.seed_default_revenue_sources(db)

    assert db.query(models.RevenueSource).count() == 0


def test_unsourced_seed_percentages_are_withdrawn_and_cited_rows_stay(db):
    seeded = _source(
        db,
        name="Amazon Associates",
        source_type="affiliate",
        payout_structure="Most physical goods pay about 1-4.5%.",
        payout_share_percent_min=1.0,
        payout_share_percent_max=20.0,
        minimum_payout=10.0,
        payment_frequency="monthly (net-60)",
        requires_approval=True,
        source_citation="Multiple affiliate-marketing guides current as of 2026 (web search, this session)",
        data_as_of="2026-08",
    )
    cited = _source(
        db,
        name="Operator record",
        source_type="other",
        payout_structure="The stored terms page states 12%.",
        payout_share_percent_min=12.0,
        payout_share_percent_max=12.0,
        source_citation="https://example.com/terms",
        data_as_of="2026-09-25",
    )

    money_engine.seed_default_revenue_sources(db)
    db.refresh(seeded)
    db.refresh(cited)

    assert seeded.payout_share_percent_min is None
    assert seeded.payout_share_percent_max is None
    assert seeded.minimum_payout is None
    assert seeded.payment_frequency is None
    assert seeded.requires_approval is False
    assert seeded.data_as_of is None
    assert "unknown" in seeded.payout_structure.lower()
    assert "web search" not in seeded.source_citation
    assert cited.payout_share_percent_min == 12.0
    assert cited.source_citation == "https://example.com/terms"


def test_grounding_bonus_requires_an_https_citation_and_a_figure(db):
    unsourced = _source(
        db,
        name="Name only",
        payout_structure=money_engine.UNKNOWN_PAYOUT_TEXT,
        source_citation=money_engine.UNKNOWN_CITATION,
    )
    cited = _source(
        db,
        name="Cited terms",
        payout_structure="The stored terms page states 12%.",
        payout_share_percent_min=12.0,
        source_citation="https://example.com/terms",
    )
    fields = {
        "implementation_difficulty": 50.0,
        "acquisition_difficulty": 50.0,
        "uncertainty": 0.0,
        "owner_priority": 0.0,
        "market_confidence": 0.0,
        "revenue_confidence": 0.0,
    }
    plain = models.Opportunity(problem="A repair shop records no payout terms.", **fields)
    linked_unsourced = models.Opportunity(
        problem="A repair shop is linked to a name without terms.",
        revenue_source_id=unsourced.id,
        **fields,
    )
    linked_cited = models.Opportunity(
        problem="A repair shop is linked to a stored terms page.",
        revenue_source_id=cited.id,
        **fields,
    )
    db.add_all([plain, linked_unsourced, linked_cited])
    db.commit()

    plain_score = money_engine.score_opportunity(db, plain)["money_score"]
    unsourced_score = money_engine.score_opportunity(db, linked_unsourced)
    cited_score = money_engine.score_opportunity(db, linked_cited)

    assert unsourced_score["revenue_source_grounded"] is False
    assert unsourced_score["money_score"] == plain_score
    assert cited_score["revenue_source_grounded"] is True
    assert cited_score["money_score"] == round(plain_score + money_engine.REVENUE_SOURCE_GROUNDING_BONUS, 1)
    assert money_engine.classify_evidence(linked_cited)["revenue_source"]["status"] == "unknown"
