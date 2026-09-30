"""Evidence-aware labels and publication compliance for public claim surfaces.

Every public claim projection uses :func:`public_claim_label`. The label is a
small public vocabulary; internal inference state and confidence never cross
this boundary.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Literal, TypedDict
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app import models


PublicLabelName = Literal["observed", "supported", "contested"]


class PublicClaimLabel(TypedDict):
    epistemic_state: PublicLabelName
    stale: bool


_REGULATED_TERMS: dict[str, tuple[str, ...]] = {
    "equity": (r"\bequity\b", r"\bequities\b", r"\bsecurities\b", r"\bstock market\b", r"\blisted shares?\b"),
    "fixed_income": (r"\bfixed[- ]income\b", r"\bbonds?\b", r"\btreasur(?:y|ies) securities\b"),
    "derivative": (r"\bderivatives?\b", r"\bfutures contracts?\b", r"\bswaps?\b", r"\boptions contracts?\b"),
    "private_credit": (r"\bprivate credit\b", r"\bdirect lending funds?\b"),
    "hedge_fund": (r"\bhedge funds?\b", r"\bhedge[- ]fund situations?\b"),
    "insurance": (r"\binsurance\b", r"\breinsurance\b"),
}
_REGULATED_CLASS_NAMES = frozenset(_REGULATED_TERMS)
_REGULATED_CLASS_ALIASES = {
    "equities": "equity",
    "stocks": "equity",
    "fixedincome": "fixed_income",
    "derivatives": "derivative",
    "privatecredit": "private_credit",
    "hedgefund": "hedge_fund",
    "hedge_funds": "hedge_fund",
    "reinsurance": "insurance",
}
_FACT_VALUES = frozenset({"fact", "verified_fact"})
_OBSERVATION_VALUES = frozenset({"observation", "observed"})
_EXTERNAL_CLAIM_VALUES = frozenset({"external_claim", "claim"})
_HIDDEN_VALUES = frozenset({"inference", "inferred", "unknown", "hypothesis"})


def derive_public_label(
    db: Session,
    claim: models.Claim,
    *,
    now: datetime | None = None,
) -> PublicClaimLabel | None:
    """Map one claim and its stored evidence to a safe public label.

    ``None`` means the claim is an inference, unknown, superseded, rejected,
    or otherwise outside the public vocabulary. Evidence freshness is a
    separate flag and cannot promote or demote the epistemic label.
    """
    provenance = _provenance(claim)
    declared_kind = _claim_kind(provenance)
    internal_state = (claim.epistemic_state or "").strip().casefold().replace(" ", "_")

    if declared_kind in _HIDDEN_VALUES or internal_state in _HIDDEN_VALUES:
        return None
    if internal_state in {"superseded", "rejected", "weakened"}:
        return None

    links = (
        db.query(models.EvidenceRelationship, models.Evidence)
        .join(models.Evidence, models.Evidence.id == models.EvidenceRelationship.evidence_id)
        .filter(models.EvidenceRelationship.claim_id == claim.id)
        .all()
    )
    conflict = internal_state == "contested" or any(
        edge.relation_type == "contradicts" or evidence.direction == "contradicts"
        for edge, evidence in links
    )

    if conflict:
        label: PublicLabelName = "contested"
    elif declared_kind in _FACT_VALUES or internal_state == "fact":
        label = "supported"
    elif declared_kind in _EXTERNAL_CLAIM_VALUES:
        label = "supported" if _independent_external_sources(links) >= 2 else "observed"
    elif declared_kind in _OBSERVATION_VALUES or internal_state in {"observed", "observation"}:
        label = "observed"
    else:
        independent_sources = _independent_external_sources(links)
        if internal_state in {"supported", "verified"}:
            label = "supported" if independent_sources >= 2 else "observed"
        else:
            return None

    newest = _newest_evidence_time(links)
    cutoff_days = _freshness_days()
    current = _utc(now or datetime.now(timezone.utc))
    stale = newest is not None and current - newest > timedelta(days=cutoff_days)
    return {"epistemic_state": label, "stale": stale}


def public_claim_label(
    db: Session,
    claim: models.Claim,
    *,
    now: datetime | None = None,
) -> PublicClaimLabel | None:
    """Apply epistemic labeling and the regulated-asset publication gate."""
    label = derive_public_label(db, claim, now=now)
    if label is None or not publication_compliance_allowed(claim):
        return None
    return label


def publication_compliance_required(claim: models.Claim) -> bool:
    """Return whether the claim concerns a regulated asset class."""
    provenance = _provenance(claim)
    structured_class = _regulated_class(provenance)
    if structured_class:
        return True
    text = " ".join((claim.statement or "", _subject_text(provenance))).casefold()
    return any(re.search(pattern, text) for patterns in _REGULATED_TERMS.values() for pattern in patterns)


def publication_compliance_allowed(claim: models.Claim) -> bool:
    """Fail closed unless regulated-asset publication has an explicit review.

    The approval record is stored in the claim's provenance as
    ``compliance_review: {status: approved, reviewer: ..., reference: ...}``.
    A status alone is insufficient: the reviewer and review reference are
    required audit fields.
    """
    if not publication_compliance_required(claim):
        return True
    review = _provenance(claim).get("compliance_review")
    if not isinstance(review, dict):
        return False
    return (
        str(review.get("status", "")).strip().casefold() == "approved"
        and bool(str(review.get("reviewer", "")).strip())
        and bool(str(review.get("reference", "")).strip())
    )


def _independent_external_sources(links: list[tuple[models.EvidenceRelationship, models.Evidence]]) -> int:
    sources: set[str] = set()
    for _edge, evidence in links:
        signal = evidence.signal
        external_signal = bool(signal and signal.source_type == "external")
        source_name = (evidence.source or (signal.source if signal else "") or "").strip().casefold()
        url = (evidence.canonical_url or (signal.canonical_url if signal else "") or "").strip()
        if not external_signal and not url.startswith(("https://", "http://")):
            continue
        identity = source_name or _url_host(url)
        if identity:
            sources.add(identity)
    return len(sources)


def _newest_evidence_time(
    links: list[tuple[models.EvidenceRelationship, models.Evidence]],
) -> datetime | None:
    dates: list[datetime] = []
    for _edge, evidence in links:
        signal = evidence.signal
        value = evidence.retrieved_at or (signal.retrieved_at if signal else None) or evidence.created_at
        if value is not None:
            dates.append(_utc(value))
    return max(dates) if dates else None


def _claim_kind(provenance: dict) -> str:
    for key in ("epistemic_type", "claim_type", "epistemic_class", "classification"):
        value = provenance.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().casefold().replace(" ", "_")
    return ""


def _regulated_class(provenance: dict) -> str:
    for key in ("regulated_asset_class", "subject_asset_class", "asset_class"):
        value = provenance.get(key)
        if isinstance(value, str):
            normalized = value.strip().casefold().replace(" ", "_").replace("-", "_")
            normalized = _REGULATED_CLASS_ALIASES.get(normalized, normalized)
            if normalized in _REGULATED_CLASS_NAMES:
                return normalized
    return ""


def _subject_text(provenance: dict) -> str:
    values = []
    for key in ("subject", "subject_name", "topic", "asset_class", "regulated_asset_class", "subject_asset_class"):
        value = provenance.get(key)
        if isinstance(value, str):
            values.append(value)
    return " ".join(values)


def _provenance(claim: models.Claim) -> dict:
    if not claim.provenance:
        return {}
    try:
        parsed = json.loads(claim.provenance)
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _freshness_days() -> int:
    try:
        return max(0, int(os.environ.get("FORGEOS_EVIDENCE_FRESH_DAYS", "90")))
    except (TypeError, ValueError):
        return 90


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _url_host(value: str) -> str:
    try:
        return urlsplit(value).hostname or ""
    except ValueError:
        return ""
