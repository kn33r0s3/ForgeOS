"""Evidence-backed tool/source usefulness accounting and selection helpers."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
from typing import Any

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow




def _event_key(prefix: str, task_id: int | None, name: str, result_ids: list[int]) -> str:
    raw = f"{prefix}:{task_id}:{name}:{','.join(map(str, sorted(set(result_ids))))}"
    return hashlib.sha256(raw.encode()).hexdigest()


def record_usage(
    db: Session,
    *,
    tool_name: str,
    source: str,
    source_type: str | None,
    query: str | None,
    research_task_id: int | None,
    claim_id: int | None,
    result_count: int | None,
    useful_result_count: int | None,
    novel_result_count: int | None,
    verified_result_count: int | None,
    duplicate_result_count: int | None,
    corroborated_evidence_count: int | None,
    contradicted_claim_count: int | None,
    freshness: float | None,
    latency_ms: float | None,
    success: bool,
    failure_kind: str | None = None,
    cost: float | None = None,
    result_ids: list[int] | None = None,
) -> tuple[models.ToolUsageEvent, models.SourceUsageEvent] | None:
    """Record one measured invocation; repeated processing of the same result is ignored."""
    result_ids = result_ids or []
    tool_key = _event_key("tool", research_task_id, tool_name, result_ids)
    source_key = _event_key("source", research_task_id, source, result_ids)
    if db.query(models.ToolUsageEvent).filter_by(event_key=tool_key).first():
        return None
    tool_event = models.ToolUsageEvent(
        tool_name=tool_name,
        query=query,
        research_task_id=research_task_id,
        claim_id=claim_id,
        result_count=result_count,
        useful_result_count=useful_result_count,
        novel_result_count=novel_result_count,
        verified_result_count=verified_result_count,
        duplicate_result_count=duplicate_result_count,
        latency_ms=latency_ms,
        success=success,
        failure_kind=failure_kind,
        cost=cost,
        event_key=tool_key,
    )
    source_event = models.SourceUsageEvent(
        source=source,
        source_type=source_type,
        query=query,
        research_task_id=research_task_id,
        claim_id=claim_id,
        result_count=result_count,
        useful_evidence_count=useful_result_count,
        novel_evidence_count=novel_result_count,
        corroborated_evidence_count=corroborated_evidence_count,
        contradicted_claim_count=contradicted_claim_count,
        duplicate_result_count=duplicate_result_count,
        freshness=freshness,
        success=success,
        failure_kind=failure_kind,
        event_key=source_key,
    )
    db.add(tool_event)
    db.add(source_event)
    db.commit()
    db.refresh(tool_event)
    db.refresh(source_event)
    return tool_event, source_event


def _summary(events: list[Any], *, useful_field: str) -> dict[str, Any]:
    attempts = len(events)
    successes = sum(1 for event in events if event.success)
    results = sum((getattr(event, "result_count", 0) or 0) for event in events)

    # Nullable usefulness is an epistemic boundary: no target claim, missing
    # relevance assessment, or failed collection is not a measured zero.
    assessed_events = [
        event for event in events if getattr(event, useful_field, None) is not None
    ]
    assessed_results = sum(
        (getattr(event, "result_count", 0) or 0) for event in assessed_events
    )
    useful = sum((getattr(event, useful_field) or 0) for event in assessed_events)

    failures = attempts - successes
    cutoff = utcnow() - timedelta(days=30)
    recent_events = [event for event in events if _as_utc(event.created_at) >= cutoff]
    recent_assessed_events = [
        event for event in recent_events
        if getattr(event, useful_field, None) is not None
    ]
    recent_assessed_results = sum(
        (getattr(event, "result_count", 0) or 0) for event in recent_assessed_events
    )
    recent_useful = sum(
        (getattr(event, useful_field) or 0) for event in recent_assessed_events
    )
    return {
        "attempts": attempts,
        "successes": successes,
        "failures": failures,
        "result_count": results,
        "useful_count": useful if assessed_events else None,
        "usefulness_assessed_result_count": assessed_results,
        "success_rate": round(successes / attempts, 4) if attempts else None,
        "useful_rate": round(useful / assessed_results, 4) if assessed_results else None,
        "recent_attempts": len(recent_events),
        "recent_useful_rate": (
            round(recent_useful / recent_assessed_results, 4)
            if recent_assessed_results else None
        ),
        "recent_usefulness_assessed_result_count": recent_assessed_results,
        "last_used": max((event.created_at for event in events), default=None),
    }


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def tool_summary(db: Session, tool_name: str) -> dict[str, Any]:
    events = db.query(models.ToolUsageEvent).filter_by(tool_name=tool_name).order_by(models.ToolUsageEvent.created_at.asc()).all()
    return _summary(events, useful_field="useful_result_count")


def _sum_known(events: list[Any], field: str) -> int | None:
    values = [
        getattr(event, field, None)
        for event in events
        if getattr(event, field, None) is not None
    ]
    return sum(values) if values else None


def source_summary(
    db: Session,
    source: str,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    query = db.query(models.SourceUsageEvent).filter_by(source=source).order_by(
        models.SourceUsageEvent.created_at.desc(),
        models.SourceUsageEvent.id.desc(),
    )
    if limit is not None:
        query = query.limit(max(1, int(limit)))
    events = list(reversed(query.all()))
    result = _summary(events, useful_field="useful_evidence_count")
    result["novel_count"] = _sum_known(events, "novel_evidence_count")
    result["corroborated_count"] = _sum_known(events, "corroborated_evidence_count")
    result["contradicted_count"] = _sum_known(events, "contradicted_claim_count")
    result["duplicate_count"] = _sum_known(events, "duplicate_result_count")
    return result


def learned_score(summary: dict[str, Any]) -> float | None:
    """Rank only when there is measured relevance; unknown is not a zero score."""
    if summary["attempts"] == 0:
        return None
    useful_rate = summary.get("useful_rate")
    recent_useful = summary.get("recent_useful_rate")
    if useful_rate is None and recent_useful is None:
        return None
    if useful_rate is None:
        useful = recent_useful
    elif recent_useful is not None:
        useful = useful_rate * 0.35 + recent_useful * 0.65
    else:
        useful = useful_rate
    success = summary["success_rate"] or 0.0
    return round(success * 0.35 + (useful or 0.0) * 0.65, 6)
