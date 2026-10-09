"""Independent evidence-grounded judgments and disagreement resolution."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Callable, Iterable

from sqlalchemy.orm import Session

from app import models
from app.models import utcnow
from app.services import evidence_graph
from app.services.tool_registry import ToolUnavailableError, default_registry


@dataclass(frozen=True)
class JudgeSpec:
    name: str
    provider: str
    model: str
    evaluate: Callable[[str, list[models.Evidence]], Any]
    available: Callable[[], bool] = lambda: True




def _evidence_key(evidence_ids: Iterable[int]) -> str:
    return ",".join(str(value) for value in sorted(set(evidence_ids)))


def _judgment_key(spec: JudgeSpec, question: str, evidence_ids: Iterable[int]) -> str:
    raw = json.dumps(
        {
            "judge": spec.name,
            "provider": spec.provider,
            "model": spec.model,
            "question": question.strip(),
            "evidence_ids": sorted(set(evidence_ids)),
        },
        sort_keys=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# Word-boundary regexes (not substrings): the substring version mislabeled
# "unlikely" as positive ("likely" matched inside it) and "eyes"/"nobody"
# via bare "yes"/"no". Negations are checked before affirmations.
_LABEL_UNCERTAIN = re.compile(
    r"\b(?:insufficient evidence|cannot determine|unknown|unclear|uncertain)\b"
)
_LABEL_NEGATIVE = re.compile(
    r"\b(?:will not pay|unlikely|rejected|no|not supported|does not establish)\b"
)
_LABEL_POSITIVE = re.compile(r"\b(?:will pay|likely|supported|yes)\b")


def _infer_label(text: str | None) -> str:
    if not text:
        return "unknown"
    lowered = text.casefold()
    if _LABEL_UNCERTAIN.search(lowered):
        return "uncertain"
    if _LABEL_NEGATIVE.search(lowered):
        return "negative"
    if _LABEL_POSITIVE.search(lowered):
        return "positive"
    return "unknown"


def _normalize_result(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        return {
            "conclusion": result.get("conclusion"),
            "reasoning_summary": result.get("reasoning_summary") or result.get("reasoning"),
            "conclusion_label": result.get("conclusion_label") or result.get("label"),
            "uncertainty": result.get("uncertainty"),
            "confidence": result.get("confidence") if isinstance(result.get("confidence"), (int, float)) else None,
        }
    text = str(result).strip()
    return {
        "conclusion": text or None,
        "reasoning_summary": text or None,
        "conclusion_label": _infer_label(text),
        "uncertainty": "not explicitly stated",
        "confidence": None,
    }


def _default_judges() -> list[JudgeSpec]:
    registry = default_registry()
    specs: list[JudgeSpec] = []
    for name, provider, model in (
        ("local-qwen3-coder", "ollama", "qwen3-coder:latest"),
        ("openai-completion", "openai", "configured"),
    ):
        try:
            tool = registry.get(name)
        except KeyError:
            continue
        if not tool.is_available():
            continue
        specs.append(
            JudgeSpec(
                name=name,
                provider=provider,
                model=model,
                evaluate=lambda question, evidence, selected=tool: selected.execute(
                    _build_prompt(question, evidence)
                ),
                available=tool.is_available,
            )
        )
    return specs


def _build_prompt(question: str, evidence: list[models.Evidence]) -> str:
    lines = [
        "Evaluate the question using only the supplied evidence.",
        f"Question: {question}",
        "Return a conclusion, reasoning summary, uncertainty, and an explicit label (positive, negative, or uncertain).",
        "Evidence:",
    ]
    lines.extend(f"[{item.id}] {item.content or ''}" for item in evidence)
    return "\n".join(lines)


def run_judgments(
    db: Session,
    *,
    question: str,
    evidence_ids: list[int],
    judges: list[JudgeSpec] | None = None,
    claim_id: int | None = None,
    opportunity_id: int | None = None,
    research_task_id: int | None = None,
) -> list[models.Judgment]:
    """Run available judges once for this exact question/evidence set."""
    evidence = db.query(models.Evidence).filter(models.Evidence.id.in_(evidence_ids)).all() if evidence_ids else []
    found_ids = {item.id for item in evidence}
    missing_ids = sorted(set(evidence_ids) - found_ids)
    selected_judges = judges if judges is not None else _default_judges()
    results: list[models.Judgment] = []
    for spec in selected_judges:
        key = _judgment_key(spec, question, evidence_ids)
        existing = db.query(models.Judgment).filter_by(judgment_key=key).first()
        if existing:
            results.append(existing)
            continue
        status = "completed"
        error = None
        normalized = {"conclusion": None, "reasoning_summary": None, "conclusion_label": "uncertain", "uncertainty": None, "confidence": None}
        try:
            if not spec.available():
                raise ToolUnavailableError(f"judge unavailable: {spec.name}")
            if missing_ids:
                raise ValueError(f"missing evidence ids: {missing_ids}")
            normalized = _normalize_result(spec.evaluate(question, evidence))
        except Exception as exc:
            status = "failed"
            error = str(exc)
        judgment = models.Judgment(
            judge_name=spec.name,
            provider=spec.provider,
            model=spec.model,
            question=question,
            conclusion=normalized["conclusion"],
            reasoning_summary=normalized["reasoning_summary"],
            conclusion_label=normalized["conclusion_label"] or _infer_label(normalized["conclusion"]),
            evidence_ids=_evidence_key(evidence_ids),
            uncertainty=normalized["uncertainty"],
            confidence=normalized["confidence"],
            status=status,
            error=error,
            judgment_key=key,
            claim_id=claim_id,
            opportunity_id=opportunity_id,
            research_task_id=research_task_id,
        )
        db.add(judgment)
        db.commit()
        db.refresh(judgment)
        for item in evidence:
            evidence_graph.link_evidence(db, item, relation_type="summarizes", judgment_id=judgment.id)
        results.append(judgment)
    return results


def _follow_up_question(db: Session, text: str, *, claim_id: int | None = None) -> models.ResearchQuestion:
    existing = db.query(models.ResearchQuestion).filter_by(question=text).first()
    if existing:
        return existing
    question = models.ResearchQuestion(
        question=text,
        priority_score=85.0,
        status="open",
        source_belief_id=None,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    from app.services import research_planner

    research_planner.plan_tasks_for_question(db, question)
    return question


def compare_judgments(
    db: Session,
    *,
    question: str,
    judgment_ids: list[int],
    evidence_ids: list[int],
    claim_id: int | None = None,
) -> models.JudgmentComparison:
    """Compare judgments without collapsing disagreement into a score."""
    normalized_ids = sorted(set(judgment_ids))
    comparison_key = hashlib.sha256(
        json.dumps({"question": question, "judgments": normalized_ids, "evidence": sorted(set(evidence_ids))}, sort_keys=True).encode("utf-8")
    ).hexdigest()
    existing = db.query(models.JudgmentComparison).filter_by(comparison_key=comparison_key).first()
    if existing:
        return existing
    judgments = db.query(models.Judgment).filter(models.Judgment.id.in_(normalized_ids)).all()
    missing_judgments = sorted(set(normalized_ids) - {item.id for item in judgments})
    failed = [item for item in judgments if item.status != "completed"]
    labels = {item.conclusion_label or _infer_label(item.conclusion) for item in judgments if item.status == "completed"}
    missing_evidence = sorted(set(evidence_ids) - {item.id for item in db.query(models.Evidence).filter(models.Evidence.id.in_(evidence_ids)).all()})
    unsupported = [item.id for item in judgments if item.status == "completed" and not item.evidence_ids]
    contradictions = []
    if claim_id is not None:
        contradictions = [
            edge.id
            for edge in db.query(models.EvidenceRelationship).filter_by(claim_id=claim_id, relation_type="contradicts").all()
        ]
    if not judgments or failed or missing_judgments or missing_evidence:
        outcome = "missing_evidence"
        summary = "Comparison is incomplete because one or more judgments or evidence records are unavailable."
    elif labels == {"positive"} or labels == {"negative"}:
        outcome = "agreement"
        summary = "All completed judges reached the same labeled conclusion."
    elif "uncertain" in labels or "unknown" in labels:
        outcome = "partial_agreement"
        summary = "Judges overlap partially, but at least one judge marked the conclusion uncertain."
    else:
        outcome = "disagreement"
        summary = "Judges reached materially different conclusions; Forge preserves both views."
    disagreement_points = [{"labels": sorted(labels), "question": question}] if outcome in {"disagreement", "partial_agreement"} else []
    follow_up = None
    if outcome in {"disagreement", "partial_agreement"} or (
        outcome == "missing_evidence" and normalized_ids
    ):
        detail = "Resolve disagreement about" if outcome != "missing_evidence" else "Find missing evidence for"
        follow_up = _follow_up_question(db, f"{detail}: {question}", claim_id=claim_id)
    comparison = models.JudgmentComparison(
        question=question,
        judgment_ids=normalized_ids,
        evidence_ids=_evidence_key(evidence_ids),
        outcome=outcome,
        summary=summary,
        disagreement_points=disagreement_points,
        missing_evidence=missing_evidence + missing_judgments,
        contradictory_claims=contradictions,
        unsupported_conclusions=unsupported,
        follow_up_question_id=follow_up.id if follow_up else None,
        comparison_key=comparison_key,
    )
    db.add(comparison)
    db.commit()
    db.refresh(comparison)
    return comparison
