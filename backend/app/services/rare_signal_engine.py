"""Deterministic weak-signal detection over existing Forge Signals."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Iterable

from sqlalchemy.orm import Session

from app import models
from app.services import economic_intelligence, opportunity_engine
from app.services.pattern_engine import tokenize

WINDOW_DAYS = 30
RECENT_DAYS = 7
MAX_SIGNALS = 500
SIGNAL_STOPWORDS = {"business", "businesses", "people", "problem", "service", "services"}
SCORE_WEIGHTS = {
    "velocity": 0.20,
    "source_diversity": 0.15,
    "novelty": 0.15,
    "pain_intensity": 0.15,
    "specificity": 0.10,
    "solution_scarcity": 0.10,
    "economic_relevance": 0.10,
    "freshness": 0.05,
}


def utcnow():
    return datetime.now(timezone.utc)


def _tokens(signal: models.Signal) -> set[str]:
    values = tokenize(signal.content) - SIGNAL_STOPWORDS
    if signal.tags:
        values |= {part.strip().casefold() for part in signal.tags.split(",") if part.strip()}
    return values


def _cluster_key(tokens: Iterable[str]) -> str:
    normalized = " ".join(sorted(set(tokens)))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _union_clusters(signals: list[models.Signal]) -> list[set[int]]:
    token_to_ids: dict[str, set[int]] = defaultdict(set)
    token_sets: dict[int, set[str]] = {}
    for signal in signals:
        token_sets[signal.id] = _tokens(signal)
        for token in token_sets[signal.id]:
            token_to_ids[token].add(signal.id)
    parent = {signal.id: signal.id for signal in signals}

    def find(value: int) -> int:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for ids in token_to_ids.values():
        ids = list(ids)
        for other in ids[1:]:
            union(ids[0], other)
    clusters: dict[int, set[int]] = defaultdict(set)
    for signal_id in parent:
        clusters[find(signal_id)].add(signal_id)
    return list(clusters.values())


def _source_type(source: str) -> str:
    return {
        "reddit": "discussion",
        "github": "code",
        "rss": "media",
        "news": "media",
        "arxiv": "research",
        "web": "web",
        "manual": "human",
        "youtube": "media",
    }.get(source, "other")


def _provenance_values(signals: list[models.Signal], key: str) -> set[str]:
    values = set()
    for signal in signals:
        if not signal.provenance:
            continue
        try:
            value = json.loads(signal.provenance).get(key)
        except (TypeError, ValueError):
            value = None
        if value:
            values.add(str(value).casefold())
    return values


def _pain_score(signals: list[models.Signal]) -> float:
    phrases = economic_intelligence.PAIN_PHRASES + economic_intelligence.CONSEQUENCE_PHRASES
    hits = sum(1 for signal in signals if any(phrase in signal.content.casefold() for phrase in phrases))
    return round(min(100.0, (hits / max(1, len(signals))) * 100), 1)


def _freshness(signals: list[models.Signal], now: datetime) -> float:
    ages = []
    for signal in signals:
        timestamp = _as_utc(signal.timestamp or now)
        ages.append(max(0.0, (now - timestamp).total_seconds() / 86400))
    return round(max(0.0, 100.0 - (sum(ages) / max(1, len(ages))) * 3), 1)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _score_cluster(signals: list[models.Signal], now: datetime) -> dict:
    cutoff = now - timedelta(days=WINDOW_DAYS)
    recent_cutoff = now - timedelta(days=RECENT_DAYS)
    current = [signal for signal in signals if _as_utc(signal.timestamp or now) >= cutoff]
    recent = [signal for signal in current if _as_utc(signal.timestamp or now) >= recent_cutoff]
    prior = [signal for signal in current if _as_utc(signal.timestamp or now) < recent_cutoff]
    frequency = len(current)
    prior_frequency = len(prior)
    recent_frequency = len(recent)
    velocity = round(min(100.0, (recent_frequency / max(1, prior_frequency)) * 50.0), 1)
    acceleration = round(max(0.0, velocity - min(100.0, prior_frequency * 10.0)), 1)
    sources = {signal.source for signal in current}
    source_types = {_source_type(signal.source) for signal in current}
    source_diversity = round(min(100.0, len(sources) * 25.0 + max(0, len(source_types) - 1) * 15.0), 1)
    first_seen = min((_as_utc(signal.timestamp or now) for signal in current), default=now)
    novelty = 100.0 if first_seen >= recent_cutoff else 35.0
    specificity = round(sum(min(100.0, len(_tokens(signal)) * 10.0) for signal in current) / max(1, len(current)), 1)
    pain = _pain_score(current)
    has_solution = any(any(phrase in signal.content.casefold() for phrase in economic_intelligence.EXISTING_SOLUTION_PHRASES) for signal in current)
    scarcity = 35.0 if has_solution else 75.0
    economic = []
    for signal in current:
        extraction = economic_intelligence.extract_economic_signal(signal.content)
        scores = economic_intelligence.score_economic_signal(extraction, signal.reliability_score)
        economic.append(max(scores["monetary_impact_score"], scores["demand_score"], scores["pain_score"]))
    economic_relevance = round(sum(economic) / max(1, len(economic)), 1)
    freshness = _freshness(current, now)
    recurrence = round(min(100.0, frequency * 20.0), 1)
    geographic_values = _provenance_values(current, "country") | _provenance_values(current, "region")
    language_values = _provenance_values(current, "language")
    geographic_spread = round(min(100.0, len(geographic_values) * 25.0), 1)
    language_spread = round(min(100.0, len(language_values) * 25.0), 1)
    score = round(sum({
        "velocity": velocity,
        "source_diversity": source_diversity,
        "novelty": novelty,
        "pain_intensity": pain,
        "specificity": specificity,
        "solution_scarcity": scarcity,
        "economic_relevance": economic_relevance,
        "freshness": freshness,
    }[factor] * weight for factor, weight in SCORE_WEIGHTS.items()), 1)
    label = ", ".join(sorted(_tokens(current[0]))[:5]) if current else "unknown signal"
    return {
        "frequency": frequency,
        "prior_frequency": prior_frequency,
        "recent_frequency": recent_frequency,
        "velocity": velocity,
        "acceleration": acceleration,
        "source_diversity": source_diversity,
        "source_types": sorted(source_types),
        "novelty": novelty,
        "specificity": specificity,
        "pain_intensity": pain,
        "solution_scarcity": scarcity,
        "economic_relevance": economic_relevance,
        "freshness": freshness,
        "recurrence": recurrence,
        "geographic_spread": geographic_spread,
        "language_spread": language_spread,
        "score": score,
        "label": label,
        "first_seen": first_seen,
        "last_seen": max((_as_utc(signal.timestamp or now) for signal in current), default=now),
        "explanation": {
            "why_detected": " + ".join(f"{factor}={value}" for factor, value in {
                "frequency": frequency, "velocity": velocity, "acceleration": acceleration,
                "source_diversity": source_diversity, "novelty": novelty,
                "pain_intensity": pain, "solution_scarcity": scarcity,
                "economic_relevance": economic_relevance, "freshness": freshness,
                "recurrence": recurrence, "geographic_spread": geographic_spread,
                "language_spread": language_spread,
            }.items()),
            "evidence_signal_ids": [signal.id for signal in current],
            "source_types": sorted(source_types),
            "note": "Indicators are deterministic heuristics, not objective truth or verified demand.",
        },
    }


def _assessment_for_key(db: Session, key: str) -> models.RareSignalAssessment | None:
    return db.query(models.RareSignalAssessment).filter_by(cluster_key=key).first()


def detect_rare_signals(
    db: Session,
    *,
    now: datetime | None = None,
    min_score: float = 35.0,
    handoff_score: float = 75.0,
) -> list[models.RareSignalAssessment]:
    now = now or utcnow()
    signals = (
        db.query(models.Signal)
        .filter(models.Signal.is_duplicate_of.is_(None))
        .order_by(models.Signal.timestamp.desc())
        .limit(MAX_SIGNALS)
        .all()
    )
    by_id = {signal.id: signal for signal in signals}
    assessments: list[models.RareSignalAssessment] = []
    for cluster_ids in _union_clusters(signals):
        cluster = [by_id[signal_id] for signal_id in cluster_ids]
        metrics = _score_cluster(cluster, now)
        if metrics["score"] < min_score:
            continue
        key = _cluster_key(_tokens(cluster[0]))
        assessment = _assessment_for_key(db, key)
        previous_score = assessment.score if assessment else None
        if not assessment:
            assessment = models.RareSignalAssessment(cluster_key=key, label=metrics["label"], signal_ids="")
            db.add(assessment)
            db.flush()
        assessment.label = metrics["label"]
        assessment.signal_ids = ",".join(str(signal.id) for signal in sorted(cluster, key=lambda item: item.id))
        for field in ("frequency", "prior_frequency", "recent_frequency", "velocity", "acceleration", "source_diversity", "novelty", "specificity", "pain_intensity", "solution_scarcity", "economic_relevance", "freshness", "recurrence", "geographic_spread", "language_spread", "score", "first_seen", "last_seen"):
            setattr(assessment, field, metrics[field])
        assessment.explanation = metrics["explanation"]
        assessment.status = "INTERESTING" if assessment.score >= handoff_score else "DETECTED"
        assessment.updated_at = now
        if previous_score is None:
            db.add(models.RareSignalEvent(assessment=assessment, event_type="detected", details=metrics["explanation"]))
        elif previous_score != assessment.score:
            event_type = "strengthened" if assessment.score > previous_score else "weakened"
            db.add(models.RareSignalEvent(assessment=assessment, event_type=event_type, details={"previous_score": previous_score, "score": assessment.score}))
        assessments.append(assessment)
    db.commit()
    for assessment in assessments:
        db.refresh(assessment)
    return sorted(assessments, key=lambda item: (-item.score, item.id))


def trigger_research_for_rare_signals(
    db: Session,
    assessments: list[models.RareSignalAssessment],
    *,
    threshold: float = 70.0,
) -> list[models.ResearchQuestion]:
    """Create one idempotent P1 question for each important assessment."""
    from app.services import research_planner

    created = []
    for assessment in assessments:
        if assessment.score < threshold or assessment.research_question_id:
            continue
        question_text = f"Investigate emerging signal: {assessment.label}"
        question = db.query(models.ResearchQuestion).filter_by(question=question_text).first()
        if not question:
            question = models.ResearchQuestion(
                question=question_text,
                priority_score=min(100.0, assessment.score),
                status="open",
                source_rare_signal_id=assessment.id,
            )
            db.add(question)
            db.flush()
            created.append(question)
        assessment.research_question_id = question.id
        assessment.status = "VERIFYING"
        assessment.updated_at = utcnow()
        research_planner.plan_tasks_for_question(db, question)
    db.commit()
    return created


def handoff_rare_signal(db: Session, assessment: models.RareSignalAssessment, *, threshold: float = 75.0) -> models.Opportunity | None:
    if assessment.score < threshold or assessment.opportunity_id:
        return None
    ids = [int(value) for value in assessment.signal_ids.split(",") if value.strip().isdigit()]
    pattern = db.query(models.Pattern).filter_by(title=f"Rare signal cluster: {assessment.cluster_key}").first()
    if not pattern:
        pattern = models.Pattern(
            title=f"Rare signal cluster: {assessment.cluster_key}",
            description=assessment.label,
            frequency=len(ids),
            confidence_score=min(95.0, assessment.score),
            origin_signal_ids=assessment.signal_ids,
        )
        db.add(pattern)
        db.commit()
        db.refresh(pattern)
    opportunity = opportunity_engine.generate_opportunity_from_pattern_if_economic(db, pattern)
    if opportunity:
        assessment.pattern_id = pattern.id
        assessment.opportunity_id = opportunity.id
        assessment.status = "VERIFYING"
        assessment.updated_at = utcnow()
        db.commit()
        db.refresh(assessment)
    return opportunity
