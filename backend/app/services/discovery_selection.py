"""Unknown-unknown discovery loop on the existing Selection v0 seams.

Discovery is a *lane* on the existing candidate/Bet projection
(``operating_v4.CANDIDATE_LANES``), not a new table, primitive, queue, or
experiment model. This module adds the two pieces Selection v0 did not have:

* ``generate_discovery_candidates`` — a read-only projection that scans
  existing repository data for grounded reasons Hami might be missing
  something, and proposes discovery probes. It proposes only; the owner
  decides which probes become candidates via the existing
  ``POST /opv4/bets/candidates`` endpoint. Every proposal is
  MODEL-PROPOSED / UNCONFIRMED until the owner confirms it.
* ``record_discovery_finding`` — records a discovery experiment's structured
  finding as EVIDENCE + EVENT on the existing substrate seams, and, when the
  finding reveals a meaningful unknown with valid provenance, converts it
  into a known-unknown candidate that enters the normal selection pool.

A source that cannot be grounded in existing data is reported UNAVAILABLE;
candidates are never fabricated.
"""

import json
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app import models
from app.services import operating_v4
from app.services import world_graph

log = logging.getLogger(__name__)

DISCOVERY_SOURCES = operating_v4.DISCOVERY_SOURCES

DISCOVERY_FINDING_TYPES = (
    "new_unknown",
    "updated_unknown",
    "anomaly",
    "contradiction",
    "blind_spot",
    "new_relationship",
    "capability_gap",
    "no_material_discovery",
)

_SOURCE_DESCRIPTIONS = {
    "map_gap": "Important areas with little or no unknown-map coverage.",
    "evidence_contradiction": "Existing evidence that disagrees materially.",
    "outcome_anomaly": "Observed outcomes the current model does not explain.",
    "capability_gap": "Investigations blocked by a missing capability.",
    "horizon_escape": "Deliberate exploration outside the current watch horizon.",
}

_DISCOVERY_CONSENT = "owner consent; no contact by Hami"


def _horizon_attrs(h: models.SubstrateEntity) -> dict:
    try:
        return json.loads(h.attributes or "{}")
    except (ValueError, TypeError):
        return {}


def _bet_text(db: Session) -> list[tuple[int, str]]:
    """(id, searchable text) for live candidate Bet projections."""
    rows = (
        db.query(models.SubstrateEntity)
        .filter(models.SubstrateEntity.entity_type == operating_v4.BET_ENTITY_TYPE)
        .all()
    )
    out = []
    for row in rows:
        try:
            attrs = json.loads(row.attributes or "{}")
        except (ValueError, TypeError):
            attrs = {}
        text = " ".join(
            str(attrs.get(key) or "") for key in ("claim", "constraint", "test")
        ).lower()
        out.append((row.id, text))
    return out


def _spec(
    *,
    source: str,
    title: str,
    discovery_basis: str,
    suggested_claim: str,
    suggested_test: str,
    suggested_kill_rule: str,
    horizon_relation: str,
    grounding_refs: list[int],
) -> dict:
    return {
        "source": source,
        "source_description": _SOURCE_DESCRIPTIONS[source],
        "title": title,
        "discovery_basis": discovery_basis,
        "suggested_claim": suggested_claim,
        "suggested_test": suggested_test,
        "suggested_kill_rule": suggested_kill_rule,
        "suggested_consent": _DISCOVERY_CONSENT,
        "horizon_relation": horizon_relation,
        # Generated proposals are never evidence and never confirmed.
        "provenance": "model-proposed",
        "confirmed": False,
        "grounding_refs": grounding_refs,
    }


def _source_map_gap(db: Session, bet_text: list[tuple[int, str]]) -> list[dict]:
    """Owner-curated horizon domains with zero candidate coverage."""
    specs = []
    for h in operating_v4.list_horizon_domains(db):
        attrs = _horizon_attrs(h)
        if attrs.get("name") == operating_v4.WATCH_HORIZON_NAME:
            continue
        if attrs.get("status") == "parked":
            continue
        name = (attrs.get("name") or "").strip()
        if not name:
            continue
        covered = any(name.lower() in text for _, text in bet_text)
        if not covered:
            specs.append(
                _spec(
                    source="map_gap",
                    title=f"Probe uncovered horizon domain: {name}",
                    discovery_basis=(
                        f"Horizon domain '{name}' is owner-curated as important, "
                        "yet no candidate Bet references it. Hami may be "
                        "missing the questions that live in this territory."
                    ),
                    suggested_claim=(
                        f"There are material unknowns in '{name}' that no "
                        "current candidate investigates."
                    ),
                    suggested_test=(
                        f"Bounded review of existing evidence touching '{name}'; "
                        "list candidate unknowns it suggests."
                    ),
                    suggested_kill_rule=(
                        f"No candidate unknown emerges from '{name}' within the bounded review."
                    ),
                    horizon_relation="inside",
                    grounding_refs=[h.id],
                )
            )
    return specs


def _source_evidence_contradiction(db: Session) -> list[dict]:
    """Beliefs superseded by other beliefs: the record disagrees with itself."""
    specs = []
    superseded = (
        db.query(models.Belief)
        .filter(models.Belief.merged_into_id.isnot(None))
        .order_by(models.Belief.id.asc())
        .all()
    )
    for belief in superseded:
        statement = (belief.statement or "")[:160]
        specs.append(
            _spec(
                source="evidence_contradiction",
                title="Probe the flawed basis behind a superseded belief",
                discovery_basis=(
                    f"Belief #{belief.id} ('{statement}…') was superseded by "
                    f"belief #{belief.merged_into_id}. The assumption that "
                    "produced the wrong belief may have infected sibling "
                    "conclusions Hami still holds."
                ),
                suggested_claim=(
                    "The flawed assumption behind the superseded belief also "
                    "supports other current beliefs."
                ),
                suggested_test=(
                    "Trace the superseded belief's basis; check sibling beliefs "
                    "built on the same assumption."
                ),
                suggested_kill_rule=(
                    "No sibling belief shares the flawed assumption."
                ),
                horizon_relation="inside",
                grounding_refs=[belief.id],
            )
        )
    return specs


def _source_outcome_anomaly(db: Session) -> list[dict]:
    """Real outcomes that failed their objective or are disputed."""
    specs = []
    anomalies = (
        db.query(models.Outcome)
        .filter(
            ((models.Outcome.success.is_(False)) | (models.Outcome.verification_state == "DISPUTED")),
        )
        .order_by(models.Outcome.id.asc())
        .all()
    )
    for outcome in anomalies:
        label = (
            "disputed" if outcome.verification_state == "DISPUTED"
            else "failed its objective"
        )
        detail = (outcome.qualitative_result or outcome.outcome_type or "")[:160]
        specs.append(
            _spec(
                source="outcome_anomaly",
                title=f"Probe unexplained outcome #{outcome.id}",
                discovery_basis=(
                    f"Outcome #{outcome.id} ({outcome.outcome_type}) {label}: "
                    f"'{detail}…'. The current model did not predict or explain this."
                ),
                suggested_claim=(
                    "The anomalous outcome reveals a missing variable in Hami's model."
                ),
                suggested_test=(
                    "Reconstruct the causal chain behind the outcome; name the "
                    "variable the model lacks."
                ),
                suggested_kill_rule="The outcome is fully explained by known variables.",
                horizon_relation="inside",
                grounding_refs=[outcome.id],
            )
        )
    return specs


def _source_capability_gap(db: Session) -> list[dict]:
    """Capabilities the ledger says are needed but not yet active."""
    specs = []
    pending = (
        db.query(models.ForgeCapability)
        .filter(models.ForgeCapability.status.in_(("proposed", "building")))
        .order_by(models.ForgeCapability.id.asc())
        .all()
    )
    for cap in pending:
        specs.append(
            _spec(
                source="capability_gap",
                title=f"Probe what '{cap.name}' would unlock",
                discovery_basis=(
                    f"Capability '{cap.name}' is '{cap.status}', not active. "
                    "Investigations it would enable are currently impossible, "
                    "so unknowns in its territory cannot even be asked."
                ),
                suggested_claim=(
                    f"Activating '{cap.name}' would expose material unknowns "
                    "Hami cannot currently see."
                ),
                suggested_test=(
                    "Enumerate the investigations the missing capability blocks; "
                    "assess which territories stay dark without it."
                ),
                suggested_kill_rule="No blocked investigation maps to a material unknown.",
                horizon_relation="inside",
                grounding_refs=[cap.id],
            )
        )
    return specs


def _source_horizon_escape(db: Session) -> list[dict]:
    """Parked domains: owner-acknowledged territory outside the watch horizon."""
    specs = []
    for h in operating_v4.list_horizon_domains(db):
        attrs = _horizon_attrs(h)
        if attrs.get("name") == operating_v4.WATCH_HORIZON_NAME:
            continue
        if attrs.get("status") != "parked":
            continue
        name = (attrs.get("name") or "").strip()
        if not name:
            continue
        reason = (attrs.get("reason_parked") or "no reason recorded")[:160]
        specs.append(
            _spec(
                source="horizon_escape",
                title=f"Discovery probe outside the horizon: {name}",
                discovery_basis=(
                    f"Domain '{name}' is parked ({reason}). The watch horizon "
                    "is a focus, not a universe boundary; unknown unknowns "
                    "are most likely where Hami is not looking."
                ),
                suggested_claim=(
                    f"There are material unknowns in parked domain '{name}'."
                ),
                suggested_test=(
                    f"Bounded probe of '{name}' for anomalies, contradictions, "
                    "or unasked questions."
                ),
                suggested_kill_rule=f"No material unknown surfaces in '{name}'.",
                horizon_relation="outside",
                grounding_refs=[h.id],
            )
        )
    return specs


_SOURCE_RUNNERS = {
    "map_gap": _source_map_gap,
    "evidence_contradiction": _source_evidence_contradiction,
    "outcome_anomaly": _source_outcome_anomaly,
    "capability_gap": _source_capability_gap,
    "horizon_escape": _source_horizon_escape,
}


def generate_discovery_candidates(db: Session) -> dict:
    """Read-only projection of grounded discovery probes.

    Returns ``{"candidates": [...], "sources": {...}}``. A source with no
    grounding data is reported ``unavailable`` with a reason; no candidate is
    ever fabricated. Proposals are MODEL-PROPOSED / UNCONFIRMED by
    construction — persisting one as a candidate is an owner action through
    the existing candidate endpoint.
    """
    bet_text = _bet_text(db)
    candidates: list[dict] = []
    sources: dict[str, dict] = {}
    for source in DISCOVERY_SOURCES:
        runner = _SOURCE_RUNNERS[source]
        try:
            specs = runner(db, bet_text) if source == "map_gap" else runner(db)
        except Exception as exc:  # a broken source must not kill the pool
            log.warning("discovery source %s failed: %s", source, exc)
            specs = []
            sources[source] = {
                "status": "unavailable",
                "reason": f"source inspection failed: {exc}",
                "candidate_count": 0,
            }
            continue
        candidates.extend(specs)
        sources[source] = {
            "status": "available" if specs else "unavailable",
            "reason": (
                _SOURCE_DESCRIPTIONS[source]
                if specs
                else f"No grounding data for {source}; nothing proposed."
            ),
            "candidate_count": len(specs),
        }
    return {"candidates": candidates, "sources": sources}


def record_discovery_finding(
    db: Session,
    *,
    discovery_bet_id: int,
    finding_type: str,
    statement: str,
    evidence_ids: Optional[list[int]] = None,
    owner_confirmed: bool = False,
    proposed_unknown_question: Optional[str] = None,
    cheapest_next_test: Optional[str] = None,
    kill_rule: Optional[str] = None,
    horizon_relation: str = "unassessed",
) -> dict:
    """Record a discovery experiment's finding; convert new unknowns.

    The finding is persisted as EVIDENCE + EVENT on the existing substrate
    seams, with provenance back to the discovery Bet. When ``finding_type``
    is ``new_unknown`` and the originating provenance is valid (linked
    evidence or owner confirmation), the discovered question is converted
    into a known-unknown candidate that enters the normal selection pool —
    marked provisional, unassessed, and gated like any other candidate.

    This function never contacts anyone, spends money, executes actions, or
    promotes findings into consequential use. It only records and proposes.
    """
    if finding_type not in DISCOVERY_FINDING_TYPES:
        raise ValueError(f"finding_type must be one of {DISCOVERY_FINDING_TYPES}.")
    clean_statement = (statement or "").strip()
    if not clean_statement:
        raise ValueError("A discovery finding requires a statement.")
    bet = db.get(models.SubstrateEntity, discovery_bet_id)
    if bet is None or bet.entity_type != operating_v4.BET_ENTITY_TYPE:
        raise ValueError(f"Discovery bet {discovery_bet_id} does not exist.")
    try:
        bet_attrs = json.loads(bet.attributes or "{}")
    except (ValueError, TypeError):
        bet_attrs = {}
    if bet_attrs.get("candidate_lane") != "unknown_unknown_discovery":
        raise ValueError(
            "Findings can only be recorded against unknown_unknown_discovery bets."
        )

    linked_evidence: list[int] = []
    if finding_type != "no_material_discovery":
        for evidence_id in evidence_ids or []:
            if db.get(models.Evidence, evidence_id) is None:
                raise ValueError(f"Evidence {evidence_id} does not exist.")
            linked_evidence.append(evidence_id)
        if not linked_evidence and not owner_confirmed:
            raise ValueError(
                "A discovery finding becomes a known unknown only with valid "
                "provenance: linked evidence or owner confirmation."
            )

    new_candidate_id: Optional[int] = None
    if finding_type == "new_unknown":
        for field_name, field_value, label in (
            ("proposed_unknown_question", proposed_unknown_question, "discovered question"),
            ("cheapest_next_test", cheapest_next_test, "cheapest next test"),
            ("kill_rule", kill_rule, "kill rule"),
        ):
            if not (field_value or "").strip():
                raise ValueError(
                    f"Converting a discovery to a known unknown requires a {label}."
                )

    provenance: dict[str, Any] = {
        "finding_type": finding_type,
        "discovery_bet_id": discovery_bet_id,
        "discovery_source": bet_attrs.get("discovery_source"),
        "evidence_ids": linked_evidence,
        "owner_confirmed": bool(owner_confirmed),
    }
    evidence = world_graph.create_evidence(
        db,
        subject_kind="entity",
        subject_id=discovery_bet_id,
        claim=clean_statement,
        support_level="hypothesized",
        source="discovery-finding",
        provenance=provenance,
        idempotency_key=f"discovery-finding:{discovery_bet_id}:{finding_type}:{hash(clean_statement) & 0xFFFFFFFF:08x}",
    )
    event_type = (
        "capability_gap_recorded" if finding_type == "capability_gap" else "learning_recorded"
    )
    event = world_graph.create_event(
        db,
        event_type=event_type,
        source="discovery-finding",
        entity_id=discovery_bet_id,
        payload={
            "finding_type": finding_type,
            "statement": clean_statement,
            "evidence_id": evidence.id,
            **provenance,
        },
    )

    if finding_type == "new_unknown":
        candidate = operating_v4.create_candidate(
            db,
            source_unknown_id=None,
            candidate_lane="known_unknown",
            provisional_unknown=True,
            origin_bet_id=discovery_bet_id,
            origin_evidence_id=evidence.id,
            claim=(proposed_unknown_question or "").strip(),
            why_it_matters=(
                f"Discovered by unknown-unknown probe (bet:{discovery_bet_id}): "
                f"{clean_statement[:200]}"
            ),
            disconfirming_test=(cheapest_next_test or "").strip(),
            kill_rule=(kill_rule or "").strip(),
            consent_requirement="Owner to specify before any test.",
            bounded_cost="Unassessed — owner to bound.",
            bounded_harm="Unassessed — owner to bound.",
            time_to_first_evidence_days=None,
            horizon_relation=horizon_relation,
            assessments={
                dimension: {"level": "unassessed", "provenance": "unassessed"}
                for dimension in operating_v4.SELECTION_DIMENSIONS
            },
        )
        new_candidate_id = candidate.id

    db.commit()
    return {
        "finding_type": finding_type,
        "evidence_id": evidence.id,
        "event_id": event.id,
        "new_candidate_id": new_candidate_id,
        "discovery_bet_id": discovery_bet_id,
    }
