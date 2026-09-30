from datetime import datetime, timedelta, timezone

from app import models
from app.services.rare_signal_engine import detect_rare_signals, handoff_rare_signal, trigger_research_for_rare_signals
import json


def add_signal(db, content, source, timestamp, *, quality=85.0, importance=75.0, provenance=None):
    signal = models.Signal(
        source=source,
        content=content,
        timestamp=timestamp,
        signal_type="problem",
        importance_score=importance,
        processed=True,
        quality_score=quality,
        reliability_score=80.0,
        freshness_score=100.0,
        provenance=json.dumps(provenance) if provenance else None,
    )
    db.add(signal)
    db.commit()
    db.refresh(signal)
    return signal


def test_rare_signal_is_explainable_and_pain_weighted(db):
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    rare = add_signal(
        db,
        "Small contractors lose hours manually reconciling permit invoices and lose money.",
        "reddit",
        now - timedelta(days=1),
    )
    boring = add_signal(db, "A new conference event schedule was published.", "rss", now - timedelta(days=1), importance=20)

    assessments = detect_rare_signals(db, now=now)
    rare_assessment = next(item for item in assessments if str(rare.id) in item.signal_ids.split(","))
    boring_assessment = next(item for item in assessments if str(boring.id) in item.signal_ids.split(","))

    assert rare_assessment.pain_intensity > boring_assessment.pain_intensity
    assert rare_assessment.economic_relevance > boring_assessment.economic_relevance
    assert "why_detected" in rare_assessment.explanation
    assert rare_assessment.explanation["evidence_signal_ids"]
    assert rare_assessment.score > boring_assessment.score


def test_velocity_source_diversity_and_cross_source_linking(db):
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    add_signal(db, "Businesses waste hours manually reconciling permit invoices.", "reddit", now - timedelta(days=20))
    add_signal(db, "Businesses waste hours manually reconciling permit invoices.", "github", now - timedelta(days=3))
    add_signal(db, "Businesses waste hours manually reconciling permit invoices.", "rss", now - timedelta(days=1))

    assessment = next(item for item in detect_rare_signals(db, now=now) if item.frequency == 3)

    assert assessment.prior_frequency == 1
    assert assessment.recent_frequency == 2
    assert assessment.velocity > 50
    assert assessment.source_diversity >= 75
    assert "discussion" in assessment.explanation["source_types"]
    assert "code" in assessment.explanation["source_types"]
    assert "media" in assessment.explanation["source_types"]


def test_related_signals_cluster_and_unrelated_problem_stays_separate(db):
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    first = add_signal(db, "Manual invoice reconciliation takes hours for accounts payable.", "reddit", now - timedelta(days=2))
    second = add_signal(db, "Spreadsheet invoice matching slows accounts payable teams.", "github", now - timedelta(days=1))
    third = add_signal(db, "Water pumps fail during winter maintenance inspections.", "rss", now - timedelta(days=1))

    assessments = detect_rare_signals(db, now=now)
    related = [item for item in assessments if str(first.id) in item.signal_ids.split(",")]
    assert related
    assert str(second.id) in related[0].signal_ids.split(",")
    assert str(third.id) not in related[0].signal_ids.split(",")


def test_repeat_detection_is_idempotent_and_new_evidence_updates_history(db):
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    add_signal(db, "Contractors lose hours manually scheduling repairs.", "reddit", now - timedelta(days=2))

    first = detect_rare_signals(db, now=now)
    second = detect_rare_signals(db, now=now)
    assert len(first) == len(second)
    assert db.query(models.RareSignalAssessment).count() == len(first)
    assert db.query(models.RareSignalEvent).filter_by(event_type="detected").count() == len(first)

    add_signal(db, "Contractors lose hours manually scheduling repairs and lose money.", "github", now - timedelta(days=1))
    updated = detect_rare_signals(db, now=now)
    assessment = next(item for item in updated if item.frequency >= 2)
    assert assessment.source_diversity >= 50
    assert db.query(models.RareSignalEvent).filter_by(assessment_id=assessment.id, event_type="strengthened").count() >= 1


def test_high_quality_economic_cluster_can_handoff_but_isolated_rare_signal_cannot(db):
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    for source, day in (("reddit", 1), ("github", 2), ("rss", 3)):
        add_signal(
            db,
            "Small contractors lose money and spend hours manually reconciling permit invoices; they would pay for a tool.",
            source,
            now - timedelta(days=day),
        )
    assessment = max(detect_rare_signals(db, now=now), key=lambda item: item.score)
    opportunity = handoff_rare_signal(db, assessment, threshold=70)

    assert assessment.score >= 70
    assert opportunity is not None
    assert opportunity.estimated_revenue is None
    assert opportunity.revenue_confidence == 0.0
    assert assessment.opportunity_id == opportunity.id


def test_geographic_language_spread_and_research_trigger_are_persistent(db):
    now = datetime(2026, 9, 11, tzinfo=timezone.utc)
    for source, country, language in (("reddit", "us", "en"), ("github", "de", "de"), ("rss", "jp", "ja")):
        add_signal(
            db,
            "Small contractors lose money and spend hours manually reconciling permit invoices; they would pay for a tool.",
            source,
            now - timedelta(days=1),
            provenance={"country": country, "language": language},
        )
    assessments = detect_rare_signals(db, now=now)
    assessment = max(assessments, key=lambda item: item.score)
    questions = trigger_research_for_rare_signals(db, assessments, threshold=60)
    again = trigger_research_for_rare_signals(db, assessments, threshold=60)

    assert assessment.geographic_spread == 75.0
    assert assessment.language_spread == 75.0
    assert questions
    assert again == []
    persisted = db.get(models.RareSignalAssessment, assessment.id)
    assert persisted.research_question_id is not None
    assert db.query(models.ResearchTask).filter_by(question_id=persisted.research_question_id).count() >= 1
