"""Evidence-backed tool/source usefulness accounting and selection helpers."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
from typing import Any

from sqlalchemy.orm import Session

from app import models


def utcnow():
    return datetime.now(timezone.utc)


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
    useful = sum((getattr(event, useful_field, 0) or 0) for event in events)
    failures = attempts - successes
    cutoff = utcnow() - timedelta(days=30)
    recent_events = [event for event in events if _as_utc(event.created_at) >= cutoff]
    recent_results = sum((getattr(event, "result_count", 0) or 0) for event in recent_events)
    recent_useful = sum((getattr(event, useful_field, 0) or 0) for event in recent_events)
    return {
        "attempts": attempts,
        "successes": successes,
        "failures": failures,
        "result_count": results,
        "useful_count": useful,
        "success_rate": round(successes / attempts, 4) if attempts else None,
        "useful_rate": round(useful / results, 4) if results else None,
        "recent_attempts": len(recent_events),
        "recent_useful_rate": round(recent_useful / recent_results, 4) if recent_results else None,
        "last_used": max((event.created_at for event in events), default=None),
    }


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def tool_summary(db: Session, tool_name: str) -> dict[str, Any]:
    events = db.query(models.ToolUsageEvent).filter_by(tool_name=tool_name).order_by(models.ToolUsageEvent.created_at.asc()).all()
    return _summary(events, useful_field="useful_result_count")


def source_summary(db: Session, source: str) -> dict[str, Any]:
    events = db.query(models.SourceUsageEvent).filter_by(source=source).order_by(models.SourceUsageEvent.created_at.asc()).all()
    result = _summary(events, useful_field="useful_evidence_count")
    result["novel_count"] = sum((event.novel_evidence_count or 0) for event in events)
    result["corroborated_count"] = sum((event.corroborated_evidence_count or 0) for event in events)
    result["contradicted_count"] = sum((event.contradicted_claim_count or 0) for event in events)
    result["duplicate_count"] = sum((event.duplicate_result_count or 0) for event in events)
    return result


def learned_score(summary: dict[str, Any]) -> float | None:
    """Use only observed rates; return None when there is no history."""
    if summary["attempts"] == 0:
        return None
    success = summary["success_rate"] or 0.0
    useful = summary["useful_rate"] or 0.0
    recent_useful = summary["recent_useful_rate"]
    if recent_useful is not None:
        useful = useful * 0.35 + recent_useful * 0.65
    return round(success * 0.35 + useful * 0.65, 6)
