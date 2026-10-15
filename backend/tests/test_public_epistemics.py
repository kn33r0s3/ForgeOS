import json

from sqlalchemy import event
from datetime import datetime, timedelta, timezone

from app import models
from app.api.public import _match_for_need, _match_tokens, list_public_discoveries
from app.services.public_feed import build_public_feed
from app.services.public_epistemics import derive_public_label, public_claim_label, public_claim_labels


def _claim(db, *, state="observed", kind=None, statement="A stored public claim.", extra=None):
    provenance = dict(extra or {})
    if kind is not None:
        provenance["epistemic_type"] = kind
    row = models.Claim(
        statement=statement,
        normalized_statement=statement.casefold(),
        epistemic_state=state,
        provenance=json.dumps(provenance) if provenance else None,
    )
    db.add(row)
    db.flush()
    return row


def _evidence(
    db,
    claim,
    *,
    source,
    retrieved_at=None,
    relation="supports",
    canonical_url=None,
    direction="supports",
):
    url = f"https://{source}.example.org/report" if canonical_url is None else canonical_url
    signal = models.Signal(
        source=source,
        source_type="external",
        content=f"Evidence from {source}.",
        canonical_url=url,
        retrieved_at=retrieved_at or datetime.now(timezone.utc),
    )
    db.add(signal)
    db.flush()
    evidence = models.Evidence(
        signal_id=signal.id,
        source=source,
        content=signal.content,
        direction=direction,
        canonical_url=url,
        retrieved_at=retrieved_at or signal.retrieved_at,
        provenance_hash=f"test:{claim.id}:{source}",
    )
    db.add(evidence)
    db.flush()
    db.add(models.EvidenceRelationship(
        evidence_id=evidence.id,
        claim_id=claim.id,
        relation_type=relation,
        relation_key=f"test:{claim.id}:{source}:{relation}",
    ))
    db.flush()
    return evidence




def test_public_need_matching_uses_shared_multilingual_terms():
    devanagari = _match_tokens("नेपालको कृषि बजारमा QR भुक्तानी")
    assert {"नेपालको", "कृषि", "बजारमा", "qr", "भुक्तानी"} <= devanagari
    assert {"nepal", "krishi", "bazar", "qr"} <= _match_tokens("Nepal ko krishi bazar QR")
    assert {"世界", "物流"} <= (_match_tokens("世界物流") & _match_tokens("世界经济物流"))
    assert not ({"the", "and", "to", "मा", "र", "को", "ko", "ra"} &
                _match_tokens("the and to मा र को ko ra"))
    assert _match_tokens("नेपाल  कृषि") == _match_tokens("नेपाल कृषि")

def _verified_public_provider(db, *, name, summary, city):
    provider = models.Provider(
        name=name,
        summary=summary,
        city=city,
        country="Nepal",
        is_active=True,
        public_visible=True,
        verification_status="verified",
    )
    db.add(provider)
    db.flush()
    return provider


def test_public_need_matching_ranks_distinctive_english_overlap_first(db):
    need = models.DomainRecord(
        kind="job",
        title="QR payment reconciliation for small merchants",
        detail="Help social sellers reconcile QR settlements and unpaid orders.",
        city="Butwal",
        close_token_hash="test-only",
        status="open",
    )
    db.add(need)
    strong = _verified_public_provider(
        db,
        name="Merchant QR Settlement Support",
        summary="Reconcile QR payment settlements, unpaid orders, and social sellers.",
        city="Kathmandu",
    )
    weak = _verified_public_provider(
        db,
        name="QR Payment Poster Printing",
        summary="Print QR payment posters and shop signage.",
        city="Butwal",
    )
    city_only = _verified_public_provider(
        db,
        name="Motorcycle Repair",
        summary="Motorcycle tyre puncture repair and oil changes.",
        city="Butwal",
    )
    unrelated = _verified_public_provider(
        db,
        name="Water Pump Technician",
        summary="Plumbing and pump maintenance.",
        city="Kathmandu",
    )
    db.commit()

    match = _match_for_need(db, need)
    ranked_provider_ids = [
        candidate.id for candidate in match.candidates if candidate.kind == "provider"
    ]

    assert ranked_provider_ids[:3] == [strong.id, weak.id, city_only.id]
    assert unrelated.id not in ranked_provider_ids
    # A lexical match is still not a completed transaction or a quality verdict.
    assert "no completed outcome is tied to this provider" in match.candidates[0].unknowns


def test_public_need_matching_ranks_devanagari_overlap_above_qr_only(db):
    need = models.DomainRecord(
        kind="job",
        title="नेपाल कृषि बजार QR भुक्तानी",
        detail="साना व्यापारी QR भुक्तानी मिलान",
        close_token_hash="test-only",
        status="open",
    )
    db.add(need)
    strong = _verified_public_provider(
        db,
        name="नेपाल QR भुक्तानी सहयोग",
        summary="कृषि बजार QR भुक्तानी मिलान",
        city="Butwal",
    )
    weak = _verified_public_provider(
        db,
        name="QR पोस्टर छपाइ",
        summary="QR कोड डिजाइन",
        city="Butwal",
    )
    db.commit()

    match = _match_for_need(db, need)

    assert [candidate.id for candidate in match.candidates if candidate.kind == "provider"] == [
        strong.id,
        weak.id,
    ]


def test_public_need_matching_ranks_romanized_nepali_overlap_above_qr_only(db):
    need = models.DomainRecord(
        kind="job",
        title="Nepal ko krishi bazar QR bhuktani",
        detail="Help sellers match QR bhuktani to orders",
        close_token_hash="test-only",
        status="open",
    )
    db.add(need)
    strong = _verified_public_provider(
        db,
        name="Nepal QR bhuktani sahayata",
        summary="krishi bazar QR bhuktani orders",
        city="Kathmandu",
    )
    weak = _verified_public_provider(
        db,
        name="QR poster design",
        summary="Shop signage and printing",
        city="Butwal",
    )
    db.commit()

    match = _match_for_need(db, need)

    assert [candidate.id for candidate in match.candidates if candidate.kind == "provider"] == [
        strong.id,
        weak.id,
    ]


def test_public_matching_frozen_multilingual_synthetic_benchmark_metrics(db):
    """TEST-only ranking benchmark; these metrics are not production accuracy."""
    cases = [
        {
            "language": "English", "need_title": "QR payment reconciliation for merchant orders",
            "need_detail": "Help sellers match payment settlements to orders",
            "strong_name": "Merchant QR payment reconciliation",
            "strong_summary": "Reconcile merchant orders and QR settlement errors",
            "weak_name": "QR poster printing", "weak_summary": "Shop posters and signage",
        },
        {
            "language": "Devanagari Nepali", "need_title": "नेपाल कृषि बजार QR भुक्तानी",
            "need_detail": "साना व्यापारीका अर्डर र भुक्तानी मिलान",
            "strong_name": "नेपाल कृषि QR भुक्तानी सहयोग",
            "strong_summary": "बजारका अर्डर र भुक्तानी मिलान",
            "weak_name": "QR पोस्टर डिजाइन", "weak_summary": "पसल बोर्ड र छपाइ",
        },
        {
            "language": "Romanized Nepali", "need_title": "Nepal ko krishi bazar QR bhuktani milan",
            "need_detail": "Help seller order milan",
            "strong_name": "Nepal krishi bazar QR bhuktani sahayata",
            "strong_summary": "Milan seller order",
            "weak_name": "QR poster design", "weak_summary": "Shop signage",
        },
        {
            "language": "Code-switched", "need_title": "Facebook seller ko QR bhuktani order milan",
            "need_detail": "Facebook commerce payment matching",
            "strong_name": "Facebook QR bhuktani support",
            "strong_summary": "Seller order milan payment",
            "weak_name": "QR poster printing", "weak_summary": "Shop signage and design",
        },
        {
            "language": "CJK", "need_title": "二维码支付商户订单对账",
            "need_detail": "二维码订单支付对账",
            "strong_name": "二维码支付订单对账服务",
            "strong_summary": "商户支付对账",
            "weak_name": "二维码海报设计", "weak_summary": "广告设计",
        },
        {
            "language": "Hindi", "need_title": "छोटे व्यापारी QR भुगतान मिलान",
            "need_detail": "आदेश और भुगतान की जांच",
            "strong_name": "व्यापारी QR भुगतान सहायता",
            "strong_summary": "भुगतान मिलान और आदेश जांच",
            "weak_name": "QR पोस्टर डिजाइन", "weak_summary": "दुकान प्रचार",
        },
    ]
    reciprocal_ranks = []
    precision_at_one_hits = 0
    for index, case in enumerate(cases):
        need = models.DomainRecord(
            kind="job", title=case["need_title"], detail=case["need_detail"],
            close_token_hash=f"benchmark-need-{index}", status="open",
        )
        db.add(need)
        db.flush()
        strong = _verified_public_provider(
            db, name=case["strong_name"], summary=case["strong_summary"], city="Kathmandu"
        )
        weak = _verified_public_provider(
            db, name=case["weak_name"], summary=case["weak_summary"], city="Kathmandu"
        )
        db.commit()
        match = _match_for_need(db, need)
        pair_ranking = [
            candidate.id for candidate in match.candidates
            if candidate.kind == "provider" and candidate.id in {strong.id, weak.id}
        ]
        assert set(pair_ranking) == {strong.id, weak.id}, case["language"]
        strong_rank = pair_ranking.index(strong.id) + 1
        reciprocal_ranks.append(1 / strong_rank)
        precision_at_one_hits += int(strong_rank == 1)
        db.delete(need)
        db.delete(strong)
        db.delete(weak)
        db.commit()
    precision_at_one = precision_at_one_hits / len(cases)
    mean_reciprocal_rank = sum(reciprocal_ranks) / len(reciprocal_ranks)
    assert precision_at_one == 1.0
    assert mean_reciprocal_rank == 1.0


def test_public_label_mapping_covers_fact_observation_external_claim_conflict_and_hidden_states(db):
    now = datetime(2026, 9, 25, tzinfo=timezone.utc)

    fact_without_evidence = _claim(db, kind="FACT")
    assert derive_public_label(db, fact_without_evidence, now=now) is None

    fact = _claim(db, kind="FACT", statement="A fact backed by an explicit source relation.")
    _evidence(db, fact, source="primary-source", retrieved_at=now)
    assert derive_public_label(db, fact, now=now) == {"epistemic_state": "supported", "stale": False}

    fact_lineage_only = _claim(db, kind="FACT", statement="A fact-shaped claim with lineage only.")
    _evidence(
        db,
        fact_lineage_only,
        source="lineage-source",
        retrieved_at=now,
        relation="derived_from",
    )
    assert derive_public_label(db, fact_lineage_only, now=now) == {
        "epistemic_state": "observed", "stale": False,
    }

    corroborated = _claim(db, state="observed", kind="EXTERNAL CLAIM")
    _evidence(db, corroborated, source="source-a", retrieved_at=now)
    _evidence(db, corroborated, source="source-b", retrieved_at=now)
    assert derive_public_label(db, corroborated, now=now) == {
        "epistemic_state": "supported", "stale": False,
    }

    # Different ingestion labels and paths on one publisher host are not two
    # independent sources. Corroboration must be based on actual source identity.
    same_host = _claim(
        db,
        state="observed",
        kind="EXTERNAL CLAIM",
        statement="A second claimed fact from two adapters of the same host.",
    )
    _evidence(
        db,
        same_host,
        source="collector-alpha",
        retrieved_at=now,
        canonical_url="https://publisher.example/report-a",
    )
    _evidence(
        db,
        same_host,
        source="collector-beta",
        retrieved_at=now,
        canonical_url="https://publisher.example/report-b",
    )
    assert derive_public_label(db, same_host, now=now) == {
        "epistemic_state": "observed", "stale": False,
    }

    unnamed_sources = _claim(
        db,
        state="observed",
        kind="EXTERNAL CLAIM",
        statement="Two labels without URLs cannot independently corroborate this.",
    )
    _evidence(
        db, unnamed_sources, source="source-alpha", retrieved_at=now,
        canonical_url="",
    )
    _evidence(
        db, unnamed_sources, source="source-beta", retrieved_at=now,
        canonical_url="",
    )
    assert derive_public_label(db, unnamed_sources, now=now) == {
        "epistemic_state": "observed", "stale": False,
    }

    one_source = _claim(db, state="observed", kind="EXTERNAL CLAIM")
    _evidence(db, one_source, source="source-a", retrieved_at=now)
    assert derive_public_label(db, one_source, now=now) == {
        "epistemic_state": "observed", "stale": False,
    }

    lineage_is_not_corroboration = _claim(
        db, state="observed", kind="EXTERNAL CLAIM",
        statement="Two source links that only establish lineage are not corroboration.",
    )
    _evidence(
        db, lineage_is_not_corroboration, source="lineage-a",
        retrieved_at=now, relation="derived_from",
    )
    _evidence(
        db, lineage_is_not_corroboration, source="lineage-b",
        retrieved_at=now, relation="derived_from",
    )
    assert derive_public_label(db, lineage_is_not_corroboration, now=now) == {
        "epistemic_state": "observed", "stale": False,
    }

    observation = _claim(db, kind="OBSERVATION")
    _evidence(db, observation, source="observer", retrieved_at=now)
    _evidence(db, observation, source="second-observer", retrieved_at=now)
    assert derive_public_label(db, observation, now=now) == {
        "epistemic_state": "observed", "stale": False,
    }

    claim_specific_lineage = _claim(
        db,
        state="observed",
        kind="EXTERNAL CLAIM",
        statement="An Evidence row can be contradictory in one legacy context but only lineage here.",
    )
    _evidence(
        db,
        claim_specific_lineage,
        source="shared-evidence",
        retrieved_at=now,
        relation="derived_from",
        direction="contradicts",
    )
    assert derive_public_label(db, claim_specific_lineage, now=now) == {
        "epistemic_state": "observed", "stale": False,
    }

    conflict = _claim(db, state="contested", kind="EXTERNAL CLAIM")
    _evidence(db, conflict, source="source-a", retrieved_at=now)
    _evidence(db, conflict, source="source-b", retrieved_at=now, relation="contradicts")
    assert derive_public_label(db, conflict, now=now) == {
        "epistemic_state": "contested", "stale": False,
    }

    inference = _claim(db, kind="INFERENCE")
    unknown = _claim(db, kind="UNKNOWN")
    assert derive_public_label(db, inference, now=now) is None
    assert derive_public_label(db, unknown, now=now) is None


def test_public_claim_labels_batch_evidence_reads_without_changing_public_labels(db):
    now = datetime(2026, 9, 25, tzinfo=timezone.utc)

    fact = _claim(db, kind="FACT", statement="The sourced repair figure is observed.")
    _evidence(db, fact, source="repair-primary", retrieved_at=now)

    conflict = _claim(
        db,
        state="contested",
        kind="EXTERNAL CLAIM",
        statement="The repair availability claim has conflicting evidence.",
    )
    _evidence(db, conflict, source="repair-source-a", retrieved_at=now)
    _evidence(
        db,
        conflict,
        source="repair-source-b",
        retrieved_at=now,
        relation="contradicts",
    )

    hidden = _claim(db, kind="INFERENCE", statement="An internal inference must stay hidden.")
    _evidence(db, hidden, source="inference-source", retrieved_at=now)

    regulated = _claim(
        db,
        kind="OBSERVATION",
        statement="Stock market conditions are noted in a background report.",
    )
    _evidence(db, regulated, source="regulated-source", retrieved_at=now)

    claims = [fact, conflict, hidden, regulated]
    queries = {"evidence_relationships": 0}

    def count_evidence_link_queries(conn, cursor, statement, parameters, context, executemany):
        normalized = " ".join(statement.casefold().split())
        if normalized.startswith("select") and " from evidence_relationships " in normalized:
            queries["evidence_relationships"] += 1

    event.listen(db.get_bind(), "before_cursor_execute", count_evidence_link_queries)
    try:
        batched = public_claim_labels(db, claims, now=now)
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", count_evidence_link_queries)

    scalar = {}
    for claim in claims:
        label = public_claim_label(db, claim, now=now)
        if label is not None:
            scalar[claim.id] = label

    assert batched == scalar
    assert queries["evidence_relationships"] == 1
    assert batched[fact.id]["epistemic_state"] == "supported"
    assert batched[conflict.id]["epistemic_state"] == "contested"
    assert hidden.id not in batched
    assert regulated.id not in batched


def test_staleness_is_separate_from_the_public_epistemic_label(db):
    now = datetime(2026, 9, 25, tzinfo=timezone.utc)
    claim = _claim(db, state="supported", kind="EXTERNAL CLAIM")
    _evidence(db, claim, source="old-source", retrieved_at=now - timedelta(days=120))

    assert derive_public_label(db, claim, now=now) == {
        "epistemic_state": "observed", "stale": True,
    }


def test_regulated_asset_publication_requires_named_compliance_review(db):
    now = datetime(2026, 9, 25, tzinfo=timezone.utc)
    claim = _claim(
        db,
        state="supported",
        kind="EXTERNAL CLAIM",
        statement="The equity derivatives market has a newly reported change.",
    )
    _evidence(db, claim, source="source-a", retrieved_at=now)
    _evidence(db, claim, source="source-b", retrieved_at=now)

    assert derive_public_label(db, claim, now=now) == {"epistemic_state": "supported", "stale": False}
    assert public_claim_label(db, claim, now=now) is None

    claim.provenance = json.dumps({
        "epistemic_type": "EXTERNAL CLAIM",
        "compliance_review": {
            "status": "approved",
            "reviewer": "compliance-reviewer",
            "reference": "review-2026-09-25-001",
        },
    })
    assert public_claim_label(db, claim, now=now) == {"epistemic_state": "supported", "stale": False}


def test_discoveries_feed_context_and_matching_share_the_publication_gate(db):
    now = datetime.now(timezone.utc)
    claim = _claim(
        db,
        state="supported",
        kind="EXTERNAL CLAIM",
        statement="The equity market changed after a documented announcement.",
    )
    _evidence(db, claim, source="source-a", retrieved_at=now)
    _evidence(db, claim, source="source-b", retrieved_at=now)
    need = models.DomainRecord(
        kind="job",
        title="Equity market announcement research",
        detail="Review a documented equity market announcement.",
        close_token_hash="test-only",
        status="open",
    )
    db.add(need)
    db.flush()

    assert list_public_discoveries(limit=20, db=db) == []
    assert not any(item.entity_type == "claim" for item in build_public_feed(db))
    assert not any(candidate.kind == "knowledge" for candidate in _match_for_need(db, need).candidates)

    claim.provenance = json.dumps({
        "epistemic_type": "EXTERNAL CLAIM",
        "compliance_review": {
            "status": "approved",
            "reviewer": "compliance-reviewer",
            "reference": "review-2026-09-25-002",
        },
    })
    db.flush()

    discovery = list_public_discoveries(limit=20, db=db)
    feed = build_public_feed(db)
    matches = _match_for_need(db, need)
    assert discovery[0].epistemic_state == "supported"
    assert discovery[0].stale is False
    assert next(item for item in feed if item.entity_type == "claim").epistemic_state == "supported"
    assert any(candidate.kind == "knowledge" for candidate in matches.candidates)
