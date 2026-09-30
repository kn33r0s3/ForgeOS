from datetime import datetime, timezone

from app.services.research_evidence_assessment import assess_source_record


def test_metadata_assessment_reports_exact_overlap_and_does_not_infer_support():
    assessment = assess_source_record(
        "What evidence evaluates appointment reminders at independent bicycle repair shops?",
        title="Appointment reminders reduce missed hospital appointments",
        content="A bibliographic metadata record.",
        published_at=datetime(2015, 10, 20, tzinfo=timezone.utc),
        retrieved_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
    )

    overlap = assessment["keyword_overlap"]
    assert overlap["method"] == "case-insensitive exact-token overlap; not semantic relevance"
    assert "appointment" in overlap["matched_terms"]
    assert "bicycle" in overlap["unmatched_terms"]
    assert assessment["publication_age_days"] == 3995
    assert assessment["semantic_relevance"] == "unassessed"
    assert assessment["contradictions"] == "unassessed"
    assert assessment["claim_support"] == "not_inferred"


def test_metadata_assessment_keeps_missing_dates_unknown():
    assessment = assess_source_record(
        "Can this source disprove the hypothesis?",
        title="An unrelated source",
        content=None,
        published_at=None,
        retrieved_at=datetime(2026, 9, 27, tzinfo=timezone.utc),
    )

    assert assessment["publication_age_days"] is None
    assert "unavailable" in assessment["freshness_basis"]
