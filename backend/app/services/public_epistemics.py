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

from sqlalchemy.orm import Session, joinedload

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
    evidence_links: list[tuple[models.EvidenceRelationship, models.Evidence]] | None = None,
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

    links = evidence_links
    if links is None:
        links = (
            db.query(models.EvidenceRelationship, models.Evidence)
            .join(models.Evidence, models.Evidence.id == models.EvidenceRelationship.evidence_id)
            .filter(models.EvidenceRelationship.claim_id == claim.id)
            .options(joinedload(models.Evidence.signal))
            .all()
        )
    # Contradiction is Claim-specific. Evidence.direction belongs to a
    # legacy evidence row and may describe a different belief/opportunity; do
    # not let it override this Claim's explicit EvidenceRelationship.
    conflict = internal_state == "contested" or any(
        edge.relation_type == "contradicts"
        for edge, _evidence in links
    )
    # Count independent sources only when the relationship itself asserts
    # support/update. Mere lineage or summary links show where information came
    # from; they do not corroborate the truth of the Claim.
    supporting_links = [
        (edge, evidence)
        for edge, evidence in links
        if edge.relation_type in {"supports", "updates"}
        and evidence.direction != "contradicts"
    ]
    independent_supporting_sources = _independent_external_sources(supporting_links)

    if conflict:
        label: PublicLabelName = "contested"
    elif declared_kind in _FACT_VALUES or internal_state == "fact":
        # A classification supplied in Claim provenance is not proof by
        # itself. A fact-labelled Claim needs an explicit support/update edge
        # backed by at least one independent external source before the public
        # projection can label it supported.
        if not links:
            return None
        label = "supported" if independent_supporting_sources >= 1 else "observed"
    elif declared_kind in _EXTERNAL_CLAIM_VALUES:
        label = "supported" if independent_supporting_sources >= 2 else "observed"
    elif declared_kind in _OBSERVATION_VALUES or internal_state in {"observed", "observation"}:
        label = "observed"
    else:
        if internal_state in {"supported", "verified"}:
            label = "supported" if independent_supporting_sources >= 2 else "observed"
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
    evidence_links: list[tuple[models.EvidenceRelationship, models.Evidence]] | None = None,
) -> PublicClaimLabel | None:
    """Apply epistemic labeling and the regulated-asset publication gate."""
    label = derive_public_label(db, claim, now=now, evidence_links=evidence_links)
    if label is None or not publication_compliance_allowed(claim):
        return None
    return label


def public_claim_labels(
    db: Session,
    claims: list[models.Claim],
    *,
    now: datetime | None = None,
) -> dict[int, PublicClaimLabel]:
    """Evaluate many public Claim labels using bounded, batched Evidence reads.

    This is the set-based equivalent of calling the scalar public label
    function for every claim. It preserves the same contradiction, independent
    source, freshness and regulated-asset publication rules.
    """
    claims_by_id = {claim.id: claim for claim in claims if claim.id is not None}
    if not claims_by_id:
        return {}

    links_by_claim: dict[int, list[tuple[models.EvidenceRelationship, models.Evidence]]] = {
        claim_id: [] for claim_id in claims_by_id
    }
    claim_ids = list(claims_by_id)
    # 400 ids remain below SQLite's traditional bind-parameter limits while
    # normal public-match batches use a single round trip.
    batch_size = 400
    for offset in range(0, len(claim_ids), batch_size):
        batch_ids = claim_ids[offset : offset + batch_size]
        linked_rows = (
            db.query(models.EvidenceRelationship, models.Evidence)
            .join(models.Evidence, models.Evidence.id == models.EvidenceRelationship.evidence_id)
            .filter(models.EvidenceRelationship.claim_id.in_(batch_ids))
            .options(joinedload(models.Evidence.signal))
            .all()
        )
        for edge, evidence in linked_rows:
            links_by_claim[edge.claim_id].append((edge, evidence))

    labels: dict[int, PublicClaimLabel] = {}
    for claim_id, claim in claims_by_id.items():
        label = public_claim_label(
            db,
            claim,
            now=now,
            evidence_links=links_by_claim[claim_id],
        )
        if label is not None:
            labels[claim_id] = label
    return labels


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
        url = (evidence.canonical_url or (signal.canonical_url if signal else "") or "").strip()
        # A collector label is not proof of an independent publisher. Only
        # an explicit HTTP(S) source location can contribute to corroboration.
        if not url.casefold().startswith(("https://", "http://")):
            continue
        host = _url_host(url).casefold()
        if not host:
            continue
        # These host variants generally identify the same web origin.
        if host.startswith("www."):
            host = host[4:]
        sources.add(host)
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
