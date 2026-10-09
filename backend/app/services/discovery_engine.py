"""OPEN-WORLD DISCOVERY ENGINE
============================

Lets Hami notice what it did not already know to look for, without a fixed
research workflow or a domain taxonomy.

How it works
------------
* A **discovery method** is a small, replaceable plugin: a name, a version,
  the input tags it ``requires``, the discovery kinds it usually ``emits``,
  and a read-only ``run(ctx)`` that inspects the recorded substrate and yields
  :class:`Finding` objects. Methods live in a :class:`DiscoveryMethodRegistry`;
  the default registry can be copied, extended, or have any method replaced.
  Search engines, APIs, LLMs, and databases are only possible *inputs* to a
  method (declared as requirement tags); they are not what discovery is.
* A **finding** is not assumed to be an opportunity. Its ``kind`` names what
  was found: an observation, contradiction, capability gap, information gap,
  hypothesis, question, action candidate, investigation method, resource
  candidate, or reason to stop. A method may name a kind nobody has seen
  before: the engine registers it as a *proposed* ``entity_type`` in
  ``type_registry`` and defers the finding (a ``discovery_deferred`` EVENT)
  until the type is activated through ``world_graph.set_type_status``. No new
  tables are created, ever.
* Every persisted finding is stored in the six primitives only: an ENTITY of
  its kind (validated by ``type_registry.schema_json``), ``possible`` or
  ``hypothesized`` EVIDENCE whose provenance lists the exact substrate rows it
  was computed from, ``hypothesized`` ``derived_from`` RELATIONs to the
  subjects it is about, ``possible`` RELATIONs for any relationship it
  proposes (for example ``may_relate``), follow-up research questions as
  further ENTITYs, and a ``discovery_run_completed`` EVENT per run.
* **Nothing is fabricated.** A finding must cite at least one existing basis
  row, and the engine rejects findings whose basis does not resolve or whose
  epistemic state is anything but ``possible``/``hypothesized``. Anything
  stronger must be earned later through the ordinary evidence rules
  (``transition_relation_truth_state`` and non-simulated provenance).
* **Capability gaps are explicit.** When a method requires an input that
  neither the substrate nor any *verified* active capability provides, the
  engine records a ``proposed`` CAPABILITY row (``discovery_input``) naming
  the missing input plus a ``capability_gap`` discovery. The gap closes only
  when a capability that ``provides`` that input has passed the hardened
  lifecycle (proposed -> building -> tested with attributable provenance ->
  active); a row that merely *claims* ``active`` without an activation record
  is itself surfaced as a capability gap.

The engine makes no network calls. It runs when explicitly invoked
(service call, the ``/forge/substrate/discovery`` endpoints, or Stage 5
of the ``/scheduled/intelligence`` cycle).
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping

from sqlalchemy.orm import Session

from app import models
from app.services import world_graph
from app.services.type_validation import SubstrateError

ENGINE_ACTOR = "discovery_engine"
ENGINE_VERSION = "1"
EVIDENCE_REF = "backend/app/services/discovery_engine.py"
EPISTEMIC_STATES = ("possible", "hypothesized")
BASIS_KINDS = (
    "entity", "relation", "evidence", "event", "capability",
    "research_question", "research_task", "type",
)
INTERNAL_INPUTS = frozenset({
    "substrate.entities", "substrate.relations", "substrate.evidence",
    "substrate.events", "substrate.capabilities", "substrate.research",
})
_KIND = re.compile(r"[a-z][a-z0-9_]{1,79}")
_BASIS_TABLES = {
    "entity": models.SubstrateEntity,
    "relation": models.WorldRelation,
    "evidence": models.Evidence,
    "event": models.WorldEvent,
    "capability": models.ForgeCapability,
    "research_question": models.ResearchQuestion,
    "research_task": models.ResearchTask,
    "type": models.TypeRegistry,
}

# Built-in vocabulary. These are *starting* kinds, not a closed taxonomy:
# methods may emit any other kind, which enters the registry as proposed.
BUILTIN_KINDS: dict[str, str] = {
    "observation": "Something noticed in recorded state (anomaly, difference, change, recurrence, neglect).",
    "contradiction": "Recorded evidence or assumptions that disagree with each other.",
    "capability_gap": "Something Hami would need to be able to do, observe, or verify but cannot yet.",
    "information_gap": "Something Hami would need to know that no recorded evidence answers.",
    "hypothesis": "A testable, unconfirmed proposition derived from recorded state.",
    "question": "A question worth investigating, including a reframing of a question that looks wrong.",
    "action_candidate": "Something that could be done, pending evidence and approval.",
    "investigation_method": "A way of investigating that the current methods do not cover.",
    "resource_candidate": "Something recorded that may be an unused or overlooked resource.",
    "reason_to_stop": "Recorded evidence that a line of inquiry should stop.",
    # Recovered from PR #15 (Step 3B-1): unknown-unknown discovery finding types.
    "new_unknown": "A previously unrecognized unknown that Hami should now track.",
    "updated_unknown": "A known unknown whose understanding has materially changed.",
    "anomaly": "An observed outcome or state the current model does not explain.",
    "blind_spot": "A territory Hami is not looking at where unknowns likely live.",
    "new_relationship": "A previously unrecognized relationship between recorded entities.",
    "no_material_discovery": "A bounded probe that found nothing material (explicit negative result).",
}
BUILTIN_RELATION_TYPES: dict[str, str] = {
    "may_relate": "A possible, untested connection proposed by a discovery method.",
    "reframes": "A discovered question that reframes an earlier question.",
    "stops": "A reason to stop that applies to an earlier discovery.",
}
BUILTIN_EVENT_TYPES: dict[str, str] = {
    "discovery_run_completed": "One explicit discovery engine run and its outcome summary.",
    "discovery_deferred": "A finding that could not be materialized yet, with the reason.",
}
GAP_CAPABILITY_TYPE = "discovery_input"
GAP_RECORD_KIND = "discovery_capability_gap"


def discovery_schema(kind: str) -> dict[str, Any]:
    """Authoritative JSON Schema for any discovery ENTITY of ``kind``."""
    return {
        "type": "object",
        "required": [
            "discovery_kind", "method", "method_version", "statement",
            "basis", "epistemic_state", "fingerprint",
        ],
        "properties": {
            "discovery_kind": {"const": kind},
            "method": {"type": "string", "minLength": 1},
            "method_version": {"type": "string", "minLength": 1},
            "statement": {"type": "string", "minLength": 1},
            "basis": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["kind", "id"],
                    "properties": {
                        "kind": {"enum": list(BASIS_KINDS)},
                        "id": {"type": "integer", "minimum": 1},
                    },
                    "additionalProperties": False,
                },
            },
            "epistemic_state": {"enum": list(EPISTEMIC_STATES)},
            "fingerprint": {"type": "string", "minLength": 16},
            "next_step": {"type": "string"},
            "facets": {"type": "object"},
        },
        "additionalProperties": False,
    }


_PROPOSED_RELATION_SCHEMA = {
    "type": "object",
    "required": ["discovery_fingerprint", "discovery_entity_id", "rationale"],
    "properties": {
        "discovery_fingerprint": {"type": "string"},
        "discovery_entity_id": {"type": "integer", "minimum": 1},
        "rationale": {"type": "string", "minLength": 1},
    },
}
_GAP_CAPABILITY_SCHEMA = {
    "type": "object",
    "required": ["record_kind", "provides", "required_by"],
    "properties": {
        "record_kind": {"const": GAP_RECORD_KIND},
        "provides": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "required_by": {"type": "array", "items": {"type": "string"}},
    },
}


# ---------------------------------------------------------------------------
# Plugin contract
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BasisRef:
    kind: str
    id: int

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "id": int(self.id)}


@dataclass(frozen=True)
class ProposedRelation:
    """A relationship a finding proposes. ``None`` endpoints mean "this finding"."""

    relation_type: str
    rationale: str
    from_entity_id: int | None = None
    to_entity_id: int | None = None
    direction: str = "directed"


@dataclass(frozen=True)
class CapabilityNeed:
    provides: str
    description: str


@dataclass
class Finding:
    kind: str
    key: str
    statement: str
    basis: tuple[BasisRef, ...]
    epistemic_state: str = "possible"
    subject_entity_ids: tuple[int, ...] = ()
    facets: Mapping[str, Any] = field(default_factory=dict)
    next_step: str | None = None
    proposed_relations: tuple[ProposedRelation, ...] = ()
    follow_up_questions: tuple[str, ...] = ()


@dataclass
class DiscoveryContext:
    db: Session
    inputs: dict[str, Any]
    actor: str = ENGINE_ACTOR

    def entities(self) -> list[models.SubstrateEntity]:
        """Active, non-discovery entities: the world as recorded, not our own output."""
        rows = (
            self.db.query(models.SubstrateEntity)
            .filter(models.SubstrateEntity.status == "active")
            .order_by(models.SubstrateEntity.id)
            .all()
        )
        return [row for row in rows if not is_discovery_entity(row)]

    @staticmethod
    def attributes(row: Any) -> dict[str, Any]:
        return _load(getattr(row, "attributes", None))


@dataclass(frozen=True)
class DiscoveryMethod:
    name: str
    version: str
    description: str
    run: Callable[[DiscoveryContext], Iterable[Finding]]
    emits: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name, "version": self.version, "description": self.description,
            "emits": list(self.emits), "requires": list(self.requires),
        }


class DiscoveryMethodRegistry:
    """Replaceable, extensible set of discovery methods."""

    def __init__(self, methods: Iterable[DiscoveryMethod] = ()):
        self._methods: dict[str, DiscoveryMethod] = {}
        for method in methods:
            self.register(method)

    def register(self, method: DiscoveryMethod, *, replace: bool = False) -> DiscoveryMethod:
        if not _KIND.fullmatch(method.name or ""):
            raise SubstrateError("discovery method name must be lowercase snake case")
        if not (method.version or "").strip():
            raise SubstrateError("discovery method version is required")
        if method.name in self._methods and not replace:
            raise SubstrateError(f"discovery method {method.name!r} already registered; pass replace=True")
        self._methods[method.name] = method
        return method

    def unregister(self, name: str) -> None:
        self._methods.pop(name, None)

    def get(self, name: str) -> DiscoveryMethod:
        try:
            return self._methods[name]
        except KeyError as exc:
            raise SubstrateError(f"unknown discovery method {name!r}") from exc

    def methods(self) -> list[DiscoveryMethod]:
        return [self._methods[name] for name in sorted(self._methods)]

    def copy(self) -> "DiscoveryMethodRegistry":
        return DiscoveryMethodRegistry(self._methods.values())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _hash(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def is_discovery_entity(row: models.SubstrateEntity) -> bool:
    return row.source_system == ENGINE_ACTOR or row.created_by == ENGINE_ACTOR


def _label(row: models.SubstrateEntity | None) -> str:
    if row is None:
        return "an unknown entity"
    return f"{row.display_name} ({row.entity_type} #{row.id})"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def verified_providers(db: Session, tag: str) -> list[models.ForgeCapability]:
    """Active capabilities that provide ``tag`` AND carry a verified activation record."""
    rows = db.query(models.ForgeCapability).filter_by(status="active").order_by(models.ForgeCapability.id).all()
    found = []
    for row in rows:
        provides = _load(row.attributes).get("provides")
        if isinstance(provides, list) and tag in provides and world_graph.capability_activation_record(db, row):
            found.append(row)
    return found


def ensure_discovery_types(db: Session) -> None:
    """Register the built-in discovery vocabulary through the recorded type lifecycle.

    Kept out of ``seed_core_types`` on purpose: nothing is written until the
    engine is explicitly run. Types go proposed -> active via ``set_type_status``
    with this module as the in-repository evidence reference.
    """
    specs: list[tuple[str, str, dict[str, Any], str]] = [
        ("entity_type", kind, discovery_schema(kind), text) for kind, text in BUILTIN_KINDS.items()
    ]
    specs += [("relation_type", name, _PROPOSED_RELATION_SCHEMA, text) for name, text in BUILTIN_RELATION_TYPES.items()]
    specs += [("event_type", name, {"type": "object"}, text) for name, text in BUILTIN_EVENT_TYPES.items()]
    specs.append((
        "capability_type", GAP_CAPABILITY_TYPE, _GAP_CAPABILITY_SCHEMA,
        "An input a discovery method needs that no verified capability provides yet.",
    ))
    for category, name, schema, text in specs:
        row = world_graph.register_type(
            db, category=category, type_name=name, schema=schema,
            owner_agent=ENGINE_ACTOR, description=text,
        )
        if row.status == "proposed":
            world_graph.set_type_status(
                db, row, "active", actor=ENGINE_ACTOR,
                rationale="Built-in open-world discovery vocabulary.",
                evidence_ref=EVIDENCE_REF,
            )


def _active_entity_kind(db: Session, kind: str) -> models.TypeRegistry | None:
    return db.query(models.TypeRegistry).filter_by(
        category="entity_type", type_name=kind, status="active"
    ).one_or_none()


def ensure_capability_gap(db: Session, *, provides: str, description: str, required_by: str) -> models.ForgeCapability:
    """One idempotent proposed CAPABILITY that would satisfy ``provides``."""
    name = f"discovery-gap-{_hash('discovery-gap-v1', provides)[:24]}"
    existing = db.query(models.ForgeCapability).filter_by(name=name).one_or_none()
    if existing is not None:
        return existing
    return world_graph.create_capability(
        db,
        capability_type=GAP_CAPABILITY_TYPE,
        name=name,
        description=description,
        owner_agent=ENGINE_ACTOR,
        spec_ref=EVIDENCE_REF,
        attributes={"record_kind": GAP_RECORD_KIND, "provides": [provides], "required_by": [required_by]},
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


def _validate_finding(db: Session, finding: Finding) -> str | None:
    if not _KIND.fullmatch(finding.kind or ""):
        return "kind must be lowercase snake case"
    if finding.epistemic_state not in EPISTEMIC_STATES:
        return "findings must begin possible or hypothesized"
    if not (finding.statement or "").strip() or not (finding.key or "").strip():
        return "statement and key are required"
    if not finding.basis:
        return "a finding must cite at least one recorded basis row"
    for ref in finding.basis:
        table = _BASIS_TABLES.get(ref.kind)
        if table is None or isinstance(ref.id, bool) or not isinstance(ref.id, int) or db.get(table, ref.id) is None:
            return f"basis {ref.kind}:{ref.id} does not resolve to a recorded row"
    for subject in finding.subject_entity_ids:
        if db.get(models.SubstrateEntity, subject) is None:
            return f"subject entity {subject} does not exist"
    return None


def fingerprint(method: DiscoveryMethod, finding: Finding) -> str:
    basis = sorted((ref.kind, ref.id) for ref in finding.basis)
    return _hash("discovery-v1", method.name, finding.kind, finding.key, basis)[:32]


def _persist(db: Session, method: DiscoveryMethod, finding: Finding, actor: str, report: dict[str, Any]) -> models.SubstrateEntity | None:
    fp = fingerprint(method, finding)
    kind = finding.kind
    if _active_entity_kind(db, kind) is None:
        reason = "category_not_active"
        if db.query(models.TypeRegistry).filter_by(category="entity_type", type_name=kind).one_or_none() is None:
            try:
                with db.begin_nested():
                    world_graph.register_type(
                        db, category="entity_type", type_name=kind, schema=discovery_schema(kind),
                        owner_agent=f"{ENGINE_ACTOR}:{method.name}",
                        description=f"Discovery category first proposed by method {method.name}.",
                    )
                reason = "category_proposed"
            except SubstrateError as exc:
                reason = f"category_unregistrable: {exc}"
        world_graph.create_event(
            db, event_type="discovery_deferred", source=actor,
            payload={
                "reason": reason, "kind": kind, "method": method.name,
                "method_version": method.version, "statement": finding.statement,
                "basis": [ref.as_dict() for ref in finding.basis], "fingerprint": fp,
            },
            idempotency_key=f"discovery-deferred:{fp}:{reason[:40]}",
        )
        report["deferred"].append({"kind": kind, "method": method.name, "reason": reason, "fingerprint": fp})
        return None

    basis = [ref.as_dict() for ref in finding.basis]
    identity_key = f"source:{kind}:{ENGINE_ACTOR}:{fp}"
    entity = db.query(models.SubstrateEntity).filter_by(identity_key=identity_key).one_or_none()
    created = entity is None
    if created:
        attributes: dict[str, Any] = {
            "discovery_kind": kind, "method": method.name, "method_version": method.version,
            "statement": finding.statement.strip(), "basis": basis,
            "epistemic_state": finding.epistemic_state, "fingerprint": fp,
        }
        if finding.next_step:
            attributes["next_step"] = finding.next_step
        if finding.facets:
            attributes["facets"] = dict(finding.facets)
        entity = world_graph.create_entity(
            db, entity_type=kind, display_name=finding.statement.strip()[:240],
            attributes=attributes, created_by=actor,
            identity={
                "source_system": ENGINE_ACTOR, "source_id": fp,
                "provenance": {"method": method.name, "method_version": method.version,
                               "engine_version": ENGINE_VERSION, "basis": basis},
                "identity_uncertainty": "Engine-proposed discovery; not an independently observed real-world entity.",
            },
        )
    world_graph.create_evidence(
        db, subject_kind="entity", subject_id=entity.id, claim=finding.statement.strip(),
        support_level=finding.epistemic_state, source=f"{ENGINE_ACTOR}:{method.name}",
        provenance={
            "method": method.name, "method_version": method.version, "engine_version": ENGINE_VERSION,
            "basis": basis,
            "derivation": "computed from the cited recorded substrate rows; no external observation was made",
        },
        idempotency_key=f"discovery-evidence:{fp}",
    )
    for subject in dict.fromkeys(finding.subject_entity_ids):
        if subject == entity.id:
            continue
        world_graph.create_relation(
            db, from_entity_id=entity.id, to_entity_id=subject, relation_type="derived_from",
            attributes={"discovery_fingerprint": fp}, truth_state="hypothesized",
            created_by=actor, idempotency_key=f"discovery-derived:{fp}:{subject}",
        )
    for index, proposal in enumerate(finding.proposed_relations):
        start = proposal.from_entity_id or entity.id
        end = proposal.to_entity_id or entity.id
        try:
            with db.begin_nested():
                world_graph.create_relation(
                    db, from_entity_id=start, to_entity_id=end, relation_type=proposal.relation_type,
                    attributes={"discovery_fingerprint": fp, "discovery_entity_id": entity.id,
                                "rationale": proposal.rationale},
                    direction=proposal.direction, truth_state="possible", created_by=actor,
                    idempotency_key=f"discovery-relation:{fp}:{index}",
                )
        except SubstrateError as exc:
            report["deferred"].append({"kind": f"relation:{proposal.relation_type}", "method": method.name,
                                       "reason": str(exc), "fingerprint": fp})
    for index, question in enumerate(finding.follow_up_questions):
        follow_up = Finding(
            kind="question", key=f"{finding.key}:follow-up:{index}", statement=question,
            basis=(BasisRef("entity", entity.id),) + tuple(finding.basis), epistemic_state="possible",
            subject_entity_ids=(entity.id,),
            facets={"follow_up_of": entity.id, "purpose": "testable research question"},
            next_step="Investigate only with cleared sources; answers advance through the evidence rules.",
        )
        _persist(db, method, follow_up, actor, report)
    report["surfaced" if created else "existing"].append(
        {"entity_id": entity.id, "kind": kind, "method": method.name, "fingerprint": fp,
         "epistemic_state": finding.epistemic_state, "statement": finding.statement}
    )
    return entity


def run_discovery(
    db: Session,
    *,
    registry: DiscoveryMethodRegistry | None = None,
    methods: Iterable[str] | None = None,
    persist: bool = True,
    actor: str = ENGINE_ACTOR,
    max_findings_per_method: int = 50,
) -> dict[str, Any]:
    """Run discovery methods over the recorded substrate.

    ``persist=False`` is a pure read: findings are returned, nothing is written.
    The caller owns the transaction (commit/rollback) when ``persist=True``.
    """
    registry = registry or DEFAULT_REGISTRY
    selected = [registry.get(name) for name in methods] if methods is not None else registry.methods()
    if persist:
        ensure_discovery_types(db)
    report: dict[str, Any] = {
        "engine_version": ENGINE_VERSION, "persisted": persist,
        "methods": [], "surfaced": [], "existing": [], "deferred": [],
        "rejected": [], "capability_gaps": [], "errors": [], "preview": [],
    }
    for method in selected:
        entry = {"name": method.name, "version": method.version, "findings": 0, "status": "ran"}
        report["methods"].append(entry)
        inputs: dict[str, Any] = {}
        missing = []
        for tag in method.requires:
            if tag in INTERNAL_INPUTS:
                inputs[tag] = "substrate"
                continue
            providers = verified_providers(db, tag)
            if providers:
                inputs[tag] = providers
            else:
                missing.append(tag)
        if missing:
            entry["status"] = "blocked_by_capability"
            entry["missing_inputs"] = missing
            for tag in missing:
                gap_report = {"method": method.name, "requires": tag}
                if persist:
                    gap = ensure_capability_gap(
                        db, provides=tag, required_by=method.name,
                        description=(f"Discovery method {method.name} needs input {tag!r}; no active, "
                                     "test-verified capability provides it."),
                    )
                    gap_report["capability_id"] = gap.id
                    _persist(db, _REQUIREMENTS_METHOD, Finding(
                        kind="capability_gap", key=f"requires:{tag}",
                        statement=(f"Hami cannot run discovery method {method.name!r}: it needs {tag!r}, "
                                   "and no active capability with a verified activation record provides it."),
                        basis=(BasisRef("capability", gap.id),), epistemic_state="hypothesized",
                        facets={"missing_input": tag, "required_by": method.name, "capability_id": gap.id,
                                "verified_providers": 0},
                        next_step=(f"Build capability #{gap.id} (or another that provides {tag!r}) through "
                                   "begin_capability_build -> mark_capability_tested -> activate_capability."),
                    ), actor, report)
                report["capability_gaps"].append(gap_report)
            continue
        ctx = DiscoveryContext(db=db, inputs=inputs, actor=actor)
        try:
            # Genuine early-stop: islice consumes the lazy iterator without
            # materializing the entire result set first. This bounds the number
            # of findings CONSUMED from the method, not the DB rows scanned or
            # time spent — methods that eagerly build large lists before their
            # first yield are not bounded by this. See method docstrings for
            # per-method work characteristics.
            findings = list(itertools.islice(method.run(ctx), max_findings_per_method))
        except Exception as exc:  # a broken plugin must not stop the others
            entry["status"] = "error"
            report["errors"].append({"method": method.name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        for finding in findings:
            problem = _validate_finding(db, finding)
            if problem:
                report["rejected"].append({"method": method.name, "kind": finding.kind, "reason": problem})
                continue
            entry["findings"] += 1
            if not persist:
                report["preview"].append({
                    "method": method.name, "kind": finding.kind, "statement": finding.statement,
                    "epistemic_state": finding.epistemic_state,
                    "basis": [ref.as_dict() for ref in finding.basis],
                    "category_active": _active_entity_kind(db, finding.kind) is not None,
                    "follow_up_questions": list(finding.follow_up_questions),
                })
                continue
            _persist(db, method, finding, actor, report)
    if persist:
        world_graph.create_event(
            db, event_type="discovery_run_completed", source=actor,
            payload={key: (value if key == "methods" else len(value))
                     for key, value in report.items() if isinstance(value, list) and key != "preview"},
        )
    return report


def list_discoveries(db: Session, *, kind: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    query = db.query(models.SubstrateEntity).filter_by(source_system=ENGINE_ACTOR)
    if kind:
        query = query.filter_by(entity_type=kind)
    rows = query.order_by(models.SubstrateEntity.id.desc()).limit(limit).all()
    return [
        {"entity_id": row.id, "kind": row.entity_type, "status": row.status,
         "identity_state": row.identity_state, **_load(row.attributes)}
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Built-in methods (each is replaceable; none assumes a domain)
# ---------------------------------------------------------------------------


def _no_op(ctx: DiscoveryContext) -> Iterable[Finding]:
    return ()


_REQUIREMENTS_METHOD = DiscoveryMethod(
    name="method_requirements", version="1", run=_no_op, emits=("capability_gap",),
    description="Engine-internal: records inputs that registered methods need but no verified capability provides.",
)


def _evidence_by_subject(db: Session) -> dict[tuple[str, int], list[models.Evidence]]:
    grouped: dict[tuple[str, int], list[models.Evidence]] = defaultdict(list)
    rows = (
        db.query(models.Evidence)
        .filter(models.Evidence.subject_kind.isnot(None), models.Evidence.subject_id.isnot(None))
        .order_by(models.Evidence.id)
        .all()
    )
    for row in rows:
        grouped[(row.subject_kind, row.subject_id)].append(row)
    return grouped


def _evidence_contradiction(ctx: DiscoveryContext) -> Iterable[Finding]:
    db = ctx.db
    for (subject_kind, subject_id), rows in _evidence_by_subject(db).items():
        positive = [row for row in rows if row.support_level in {"tested", "supported"}]
        refuting = [row for row in rows if row.support_level == "refuted"]
        if not positive or not refuting:
            continue
        if subject_kind == "entity":
            subject = db.get(models.SubstrateEntity, subject_id)
            if subject is None:
                continue
            label, subjects, assumed = _label(subject), (subject.id,), None
        else:
            relation = db.get(models.WorldRelation, subject_id)
            if relation is None:
                continue
            start = db.get(models.SubstrateEntity, relation.from_entity_id)
            end = db.get(models.SubstrateEntity, relation.to_entity_id)
            label = f"{_label(start)} {relation.relation_type} {_label(end)} (relation #{relation.id})"
            subjects = (relation.from_entity_id, relation.to_entity_id)
            assumed = relation.truth_state
        challenged = assumed in {"tested", "supported"}
        yield Finding(
            kind="contradiction",
            key=f"{subject_kind}:{subject_id}",
            statement=(f"Recorded evidence disagrees about {label}: {len(positive)} tested/supported "
                       f"record(s) versus {len(refuting)} refuting record(s)."
                       + (f" The relation is currently held as {assumed}." if challenged else "")),
            basis=(BasisRef(subject_kind, subject_id),) + tuple(BasisRef("evidence", row.id) for row in positive + refuting),
            epistemic_state="hypothesized",
            subject_entity_ids=subjects,
            facets={"subject_kind": subject_kind, "subject_id": subject_id,
                    "supporting_evidence_ids": [row.id for row in positive],
                    "refuting_evidence_ids": [row.id for row in refuting],
                    "current_assumption_challenged": challenged},
            next_step="Obtain independent, non-simulated evidence that resolves the disagreement; treat the subject as contested until then.",
        )


def _question_text(db: Session, entity: models.SubstrateEntity) -> tuple[str, models.ResearchQuestion | None]:
    ref = _load(entity.attributes).get("canonical_ref")
    if isinstance(ref, dict) and ref.get("entity_type") == "research_question":
        row = db.get(models.ResearchQuestion, ref.get("entity_id"))
        if row is not None:
            return row.question, row
    return entity.display_name, None


def _refuted_without_later_support(rows: list[models.Evidence]) -> list[models.Evidence]:
    refuted = [row for row in rows if row.support_level == "refuted"]
    if not refuted:
        return []
    latest_refuted = max(row.id for row in refuted)
    if any(row.support_level in {"tested", "supported"} and row.id > latest_refuted for row in rows):
        return []
    return refuted


def _question_reframe(ctx: DiscoveryContext) -> Iterable[Finding]:
    db = ctx.db
    evidence = _evidence_by_subject(db)
    questions = [row for row in ctx.entities() if row.entity_type == "research_question"]
    for question in questions:
        text, record = _question_text(db, question)
        relations = db.query(models.WorldRelation).filter(
            (models.WorldRelation.from_entity_id == question.id) | (models.WorldRelation.to_entity_id == question.id)
        ).order_by(models.WorldRelation.id).all()
        for relation in relations:
            if relation.created_by == ENGINE_ACTOR:
                continue
            other_id = relation.to_entity_id if relation.from_entity_id == question.id else relation.from_entity_id
            premise = db.get(models.SubstrateEntity, other_id)
            if premise is None:
                continue
            refuting = [row for row in evidence.get(("relation", relation.id), []) if row.support_level == "refuted"] \
                if relation.truth_state == "refuted" else []
            reason = "its link to the premise is refuted"
            if not refuting:
                refuting = _refuted_without_later_support(evidence.get(("entity", premise.id), []))
                reason = "the premise itself is refuted"
            if not refuting:
                continue
            reframed = (f"What is actually true about {premise.display_name}, and does "
                        f"\"{text}\" still matter once that is known?")
            yield Finding(
                kind="question",
                key=f"reframe:{question.id}:{relation.id}",
                statement=(f"The question \"{text}\" rests on {_label(premise)}, but {reason} "
                           f"(evidence {', '.join('#' + str(row.id) for row in refuting)}). The question may be "
                           f"wrong as framed. Reframed: {reframed}"),
                basis=(BasisRef("entity", question.id), BasisRef("relation", relation.id))
                + tuple(BasisRef("evidence", row.id) for row in refuting),
                epistemic_state="hypothesized",
                subject_entity_ids=(question.id, premise.id),
                facets={"reframe_reason": "refuted_premise", "original_question": text,
                        "original_question_entity_id": question.id, "premise_entity_id": premise.id,
                        "premise_relation_id": relation.id, "reframed_question": reframed},
                next_step="Investigate the reframed question; keep the original open only if the premise is re-established by evidence.",
                proposed_relations=(ProposedRelation("reframes", "Reframing prompted by a refuted premise.",
                                                     to_entity_id=question.id),),
            )
        if record is None:
            continue
        tasks = db.query(models.ResearchTask).filter_by(question_id=record.id).order_by(models.ResearchTask.id).all()
        finished = [task for task in tasks if task.status in {"completed", "failed", "needs_research"}]
        answered = [task for task in tasks if (task.evidence_ids or "").strip() not in {"", "[]", "null"}]
        if len(finished) >= 2 and len(finished) == len(tasks) and not answered and not evidence.get(("entity", question.id)):
            sources = sorted({task.source for task in tasks})
            reframed = f"What observable, recordable fact would change what we believe about: \"{text}\"?"
            yield Finding(
                kind="question",
                key=f"unanswered:{question.id}",
                statement=(f"{len(tasks)} research tasks ({', '.join(sources)}) ended without any evidence for "
                           f"\"{text}\". It may be unanswerable as framed. Reframed: {reframed}"),
                basis=(BasisRef("entity", question.id), BasisRef("research_question", record.id))
                + tuple(BasisRef("research_task", task.id) for task in tasks),
                epistemic_state="hypothesized",
                subject_entity_ids=(question.id,),
                facets={"reframe_reason": "unanswered_as_framed", "original_question": text,
                        "original_question_entity_id": question.id, "task_sources": sources,
                        "reframed_question": reframed},
                next_step="Either narrow the question to something an existing cleared source can observe, or record the missing source as a capability gap.",
                proposed_relations=(ProposedRelation("reframes", "Reframing prompted by repeated unanswered research.",
                                                     to_entity_id=question.id),),
            )


def _numeric_divergence(ctx: DiscoveryContext, *, ratio_threshold: float = 2.0) -> Iterable[Finding]:
    by_type: dict[str, list[tuple[models.SubstrateEntity, dict[str, Any]]]] = defaultdict(list)
    for row in ctx.entities():
        by_type[row.entity_type].append((row, ctx.attributes(row)))
    for entity_type, rows in sorted(by_type.items()):
        if len(rows) < 3:
            continue
        numeric_keys = sorted({key for _, attrs in rows for key, value in attrs.items()
                               if _is_number(value) and key != "id" and not key.endswith("_id")})
        group_keys = sorted({key for _, attrs in rows for key, value in attrs.items()
                             if isinstance(value, str) and 0 < len(value) <= 80})
        for number_key in numeric_keys:
            for group_key in group_keys:
                groups: dict[str, list[tuple[models.SubstrateEntity, float]]] = defaultdict(list)
                for row, attrs in rows:
                    if _is_number(attrs.get(number_key)) and isinstance(attrs.get(group_key), str):
                        groups[attrs[group_key]].append((row, float(attrs[number_key])))
                if len(groups) < 2 or sum(len(items) for items in groups.values()) < 3:
                    continue
                medians = {name: statistics.median(value for _, value in items) for name, items in groups.items()}
                low = min(medians, key=lambda name: (medians[name], name))
                high = max(medians, key=lambda name: (medians[name], name))
                if medians[low] <= 0 or medians[high] / medians[low] < ratio_threshold:
                    continue
                ratio = medians[high] / medians[low]
                members = groups[low] + groups[high]
                yield Finding(
                    kind="observation",
                    key=f"divergence:{entity_type}:{number_key}:{group_key}:{low}:{high}",
                    statement=(f"Recorded {entity_type} entities differ {ratio:.1f}x in {number_key} across "
                               f"{group_key}: {group_key}={high!r} has median {medians[high]:g} versus "
                               f"{group_key}={low!r} with median {medians[low]:g}."),
                    basis=tuple(BasisRef("entity", row.id) for row, _ in members[:25]),
                    epistemic_state="hypothesized",
                    subject_entity_ids=(groups[low][0][0].id, groups[high][0][0].id),
                    facets={"pattern": "difference", "entity_type": entity_type, "measure": number_key,
                            "dimension": group_key, "low_group": low, "high_group": high,
                            "low_median": medians[low], "high_median": medians[high], "ratio": round(ratio, 4),
                            "sample_sizes": {low: len(groups[low]), high: len(groups[high])}},
                    next_step="Check whether the difference is real (same unit, same period, same quality) before treating it as usable.",
                    follow_up_questions=(
                        f"Is the {ratio:.1f}x difference in {number_key} between {group_key}={low!r} and "
                        f"{group_key}={high!r} real, what explains it, and could it be used?",
                    ),
                )


_IGNORED_VALUES = {"true", "false", "none", "null", "yes", "no", "unknown", "active", "open", "closed"}


def _non_engine_relation_pairs(db: Session) -> set[tuple[int, int]]:
    """Endpoint pairs of all recorded non-engine relations, orientation-normalized.

    One query up front so callers like ``_disconnection`` do not issue one
    relation lookup per candidate pair (N+1 on large substrates).
    """
    pairs: set[tuple[int, int]] = set()
    for start, end in db.query(models.WorldRelation.from_entity_id, models.WorldRelation.to_entity_id).filter(
        models.WorldRelation.created_by != ENGINE_ACTOR
    ).all():
        pairs.add((start, end) if start <= end else (end, start))
    return pairs


def _disconnection(ctx: DiscoveryContext, *, max_holders: int = 4) -> Iterable[Finding]:
    db = ctx.db
    holders: dict[str, dict[int, tuple[models.SubstrateEntity, str]]] = defaultdict(dict)
    for row in ctx.entities():
        for key, value in ctx.attributes(row).items():
            if not isinstance(value, str):
                continue
            normalized = " ".join(value.split()).casefold()
            if len(normalized) < 3 or len(normalized) > 120 or normalized in _IGNORED_VALUES \
                    or normalized.replace(".", "").isdigit():
                continue
            holders[normalized].setdefault(row.id, (row, key))
    linked_pairs = _non_engine_relation_pairs(db)
    for value, members in sorted(holders.items()):
        if not 2 <= len(members) <= max_holders:
            continue
        ordered = sorted(members.values(), key=lambda item: item[0].id)
        if len({row.entity_type for row, _ in ordered}) < 2:
            continue
        for index, (left, left_key) in enumerate(ordered):
            for right, right_key in ordered[index + 1:]:
                if left.entity_type == right.entity_type:
                    continue
                pair = (left.id, right.id) if left.id <= right.id else (right.id, left.id)
                if pair in linked_pairs:
                    continue
                yield Finding(
                    kind="hypothesis",
                    key=f"disconnection:{left.id}:{right.id}:{value}",
                    statement=(f"{_label(left)} and {_label(right)} both record {value!r} "
                               f"({left_key} / {right_key}) but have no recorded relation; they may be connected."),
                    basis=(BasisRef("entity", left.id), BasisRef("entity", right.id)),
                    epistemic_state="possible",
                    subject_entity_ids=(left.id, right.id),
                    facets={"pattern": "disconnection", "shared_value": value,
                            "attributes": [left_key, right_key],
                            "entity_types": [left.entity_type, right.entity_type]},
                    next_step="Look for evidence of an actual connection; the shared value alone proves nothing.",
                    proposed_relations=(ProposedRelation(
                        "may_relate", f"Both record {value!r}; untested.",
                        from_entity_id=left.id, to_entity_id=right.id, direction="bidirectional",
                    ),),
                    follow_up_questions=(
                        f"What evidence would show whether {left.display_name} and {right.display_name} are "
                        f"actually connected through {value!r}, and what would that connection make possible?",
                    ),
                )


def _isolation(ctx: DiscoveryContext, *, min_connected_share: float = 0.5) -> Iterable[Finding]:
    db = ctx.db
    connected: set[int] = set()
    for start, end in db.query(models.WorldRelation.from_entity_id, models.WorldRelation.to_entity_id).filter(
        models.WorldRelation.created_by != ENGINE_ACTOR
    ).all():
        connected.update((start, end))
    by_type: dict[str, list[models.SubstrateEntity]] = defaultdict(list)
    for row in ctx.entities():
        by_type[row.entity_type].append(row)
    for entity_type, rows in sorted(by_type.items()):
        if len(rows) < 3:
            continue
        linked = [row for row in rows if row.id in connected]
        isolated = [row for row in rows if row.id not in connected]
        if not isolated or len(linked) / len(rows) < min_connected_share:
            continue
        for row in isolated:
            yield Finding(
                kind="observation",
                key=f"isolated:{row.id}",
                statement=(f"{_label(row)} has no recorded relations while {len(linked)} of {len(rows)} "
                           f"{entity_type} entities do; it may be neglected, unused capacity, or simply unrecorded."),
                basis=(BasisRef("entity", row.id),) + tuple(BasisRef("entity", peer.id) for peer in linked[:5]),
                epistemic_state="possible",
                subject_entity_ids=(row.id,),
                facets={"pattern": "isolation", "entity_type": entity_type,
                        "connected_peers": len(linked), "peer_count": len(rows)},
                follow_up_questions=(f"Is {row.display_name} unused, or is its use simply not recorded?",),
            )


_BOOKKEEPING_EVENTS = {
    "entity_created", "relation_created", "type_status_changed", "discovery_run_completed",
    "discovery_deferred", "entity_identity_changed",
}


def _recurrence(ctx: DiscoveryContext, *, min_repeats: int = 3) -> Iterable[Finding]:
    db = ctx.db
    grouped: dict[tuple[str, int], list[models.WorldEvent]] = defaultdict(list)
    for event in db.query(models.WorldEvent).filter(models.WorldEvent.entity_id.isnot(None)).order_by(models.WorldEvent.id).all():
        if event.event_type not in _BOOKKEEPING_EVENTS:
            grouped[(event.event_type, event.entity_id)].append(event)
    for (event_type, entity_id), events in sorted(grouped.items()):
        entity = db.get(models.SubstrateEntity, entity_id)
        if len(events) < min_repeats or entity is None or is_discovery_entity(entity):
            continue
        first, last = events[0].occurred_at, events[-1].occurred_at
        yield Finding(
            kind="observation",
            key=f"recurrence:{event_type}:{entity_id}",
            statement=(f"{_label(entity)} repeatedly records {event_type} ({len(events)} times between "
                       f"{first:%Y-%m-%d} and {last:%Y-%m-%d} UTC)."),
            basis=(BasisRef("entity", entity_id),) + tuple(BasisRef("event", event.id) for event in events[:25]),
            epistemic_state="hypothesized",
            subject_entity_ids=(entity_id,),
            facets={"pattern": "recurrence", "event_type": event_type, "count": len(events)},
            follow_up_questions=(f"Why does {event_type} keep recurring for {entity.display_name}, and is it an unserved need?",),
        )


def _capability_integrity(ctx: DiscoveryContext) -> Iterable[Finding]:
    db = ctx.db
    for capability in db.query(models.ForgeCapability).filter_by(status="active").order_by(models.ForgeCapability.id).all():
        if world_graph.capability_activation_record(db, capability) is not None:
            continue
        yield Finding(
            kind="capability_gap",
            key=f"unverified:{capability.id}",
            statement=(f"Capability {capability.name!r} (#{capability.id}) is marked active but has no attributable "
                       "passing test run; Hami cannot rely on it, so this capability is effectively missing."),
            basis=(BasisRef("capability", capability.id),),
            epistemic_state="hypothesized",
            facets={"capability_id": capability.id, "capability_type": capability.capability_type,
                    "claimed_status": capability.status, "verified": False},
            next_step="Re-verify it through mark_capability_tested with actor, revision, and a command naming its test, or stop depending on it.",
        )


def _refuted_basis_stop(ctx: DiscoveryContext) -> Iterable[Finding]:
    db = ctx.db
    evidence = _evidence_by_subject(db)
    for relation in db.query(models.WorldRelation).filter_by(created_by=ENGINE_ACTOR, truth_state="refuted").order_by(models.WorldRelation.id).all():
        attrs = _load(relation.attributes)
        refuting = [row for row in evidence.get(("relation", relation.id), []) if row.support_level == "refuted"]
        origin = attrs.get("discovery_entity_id")
        if not refuting or not isinstance(origin, int) or db.get(models.SubstrateEntity, origin) is None:
            continue
        start = db.get(models.SubstrateEntity, relation.from_entity_id)
        end = db.get(models.SubstrateEntity, relation.to_entity_id)
        yield Finding(
            kind="reason_to_stop",
            key=f"refuted-relation:{relation.id}",
            statement=(f"The proposed {relation.relation_type} between {_label(start)} and {_label(end)} was refuted "
                       f"by evidence {', '.join('#' + str(row.id) for row in refuting)}; stop pursuing it unless new evidence appears."),
            basis=(BasisRef("relation", relation.id), BasisRef("entity", origin))
            + tuple(BasisRef("evidence", row.id) for row in refuting),
            epistemic_state="hypothesized",
            subject_entity_ids=(origin,),
            facets={"stopped_relation_id": relation.id, "stopped_discovery_entity_id": origin},
            proposed_relations=(ProposedRelation("stops", "Refuted by recorded evidence.", to_entity_id=origin),),
        )
    for entity in db.query(models.SubstrateEntity).filter_by(source_system=ENGINE_ACTOR).order_by(models.SubstrateEntity.id).all():
        refuting = _refuted_without_later_support(evidence.get(("entity", entity.id), []))
        if not refuting or entity.entity_type == "reason_to_stop":
            continue
        yield Finding(
            kind="reason_to_stop",
            key=f"refuted-discovery:{entity.id}",
            statement=(f"Discovery {_label(entity)} was refuted by evidence "
                       f"{', '.join('#' + str(row.id) for row in refuting)}; stop pursuing it unless new evidence appears."),
            basis=(BasisRef("entity", entity.id),) + tuple(BasisRef("evidence", row.id) for row in refuting),
            epistemic_state="hypothesized",
            subject_entity_ids=(entity.id,),
            facets={"stopped_discovery_entity_id": entity.id},
            proposed_relations=(ProposedRelation("stops", "Refuted by recorded evidence.", to_entity_id=entity.id),),
        )


_SUBSTRATE = ("substrate.entities", "substrate.relations", "substrate.evidence")


# ---------------------------------------------------------------------------
# Step 3B-1: Recovered from PR #15 (unknown-unknown discovery loop).
# These 5 methods adapt PR #15's grounded sources as DiscoveryMethods.
# All are DB queries (no network); empty results are honest "no discovery".
# ---------------------------------------------------------------------------

# Local copy of PR #15's watch-horizon marker (not in main's operating_v4).
_PR15_WATCH_HORIZON_NAME = "__current_watch_horizon__"


def _pr15_horizon_attrs(h: models.SubstrateEntity) -> dict:
    try:
        return json.loads(h.attributes or "{}")
    except (ValueError, TypeError):
        return {}


def _pr15_bet_text(db) -> list[tuple[int, str]]:
    """(id, searchable text) for live candidate Bet projections."""
    from app.services import operating_v4 as _opv4

    rows = (
        db.query(models.SubstrateEntity)
        .filter(models.SubstrateEntity.entity_type == _opv4.BET_ENTITY_TYPE)
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


def _map_gap(ctx: DiscoveryContext) -> Iterable[Finding]:
    """Owner-curated horizon domains with zero candidate coverage. (PR #15)"""
    from app.services import operating_v4 as _opv4

    db = ctx.db
    bet_text = _pr15_bet_text(db)
    for h in _opv4.list_horizon_domains(db):
        attrs = _pr15_horizon_attrs(h)
        if attrs.get("name") == _PR15_WATCH_HORIZON_NAME:
            continue
        if attrs.get("status") == "parked":
            continue
        name = (attrs.get("name") or "").strip()
        if not name:
            continue
        covered = any(name.lower() in text for _, text in bet_text)
        if not covered:
            yield Finding(
                kind="new_unknown",
                key=f"map-gap:{h.id}",
                statement=(
                    f"Horizon domain '{name}' is owner-curated as important, yet no "
                    "candidate Bet references it. Hami may be missing the questions "
                    "that live in this territory."
                ),
                basis=(BasisRef("entity", h.id),),
                epistemic_state="possible",
                subject_entity_ids=(h.id,),
                facets={"source": "map_gap", "horizon_domain": name,
                        "horizon_relation": "inside", "provenance": "model-proposed",
                        "confirmed": False},
                next_step=(
                    f"Bounded review of existing evidence touching '{name}'; "
                    "list candidate unknowns it suggests."
                ),
                follow_up_questions=(
                    f"There are material unknowns in '{name}' that no current candidate investigates.",
                ),
            )


def _superseded_belief(ctx: DiscoveryContext) -> Iterable[Finding]:
    """Beliefs superseded by other beliefs: the record disagrees with itself. (PR #15)"""
    db = ctx.db
    superseded = (
        db.query(models.Belief)
        .filter(models.Belief.merged_into_id.isnot(None))
        .order_by(models.Belief.id.asc())
        .all()
    )
    for belief in superseded:
        statement = (belief.statement or "")[:160]
        yield Finding(
            kind="contradiction",
            key=f"superseded-belief:{belief.id}",
            statement=(
                f"Belief #{belief.id} ('{statement}…') was superseded by belief "
                f"#{belief.merged_into_id}. The assumption that produced the wrong "
                "belief may have infected sibling conclusions Hami still holds."
            ),
            basis=(BasisRef("entity", belief.id),) if hasattr(belief, "id") else (),
            epistemic_state="hypothesized",
            facets={"source": "evidence_contradiction", "superseded_belief_id": belief.id,
                    "merged_into_id": belief.merged_into_id,
                    "provenance": "model-proposed", "confirmed": False},
            next_step=(
                "Trace the superseded belief's basis; check sibling beliefs "
                "built on the same assumption."
            ),
            follow_up_questions=(
                "The flawed assumption behind the superseded belief also supports other current beliefs.",
            ),
        )


def _outcome_anomaly(ctx: DiscoveryContext) -> Iterable[Finding]:
    """Real outcomes that failed their objective or are disputed. (PR #15)"""
    db = ctx.db
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
        yield Finding(
            kind="anomaly",
            key=f"outcome-anomaly:{outcome.id}",
            statement=(
                f"Outcome #{outcome.id} ({outcome.outcome_type}) {label}: "
                f"'{detail}…'. The current model did not predict or explain this."
            ),
            basis=(BasisRef("entity", outcome.id),),
            epistemic_state="possible",
            facets={"source": "outcome_anomaly", "outcome_id": outcome.id,
                    "outcome_type": outcome.outcome_type, "label": label,
                    "provenance": "model-proposed", "confirmed": False},
            next_step=(
                "Reconstruct the causal chain behind the outcome; name the "
                "variable the model lacks."
            ),
            follow_up_questions=(
                "The anomalous outcome reveals a missing variable in Hami's model.",
            ),
        )


def _pending_capability(ctx: DiscoveryContext) -> Iterable[Finding]:
    """Capabilities the ledger says are needed but not yet active. (PR #15)"""
    db = ctx.db
    pending = (
        db.query(models.ForgeCapability)
        .filter(models.ForgeCapability.status.in_(("proposed", "building")))
        .order_by(models.ForgeCapability.id.asc())
        .all()
    )
    for cap in pending:
        yield Finding(
            kind="capability_gap",
            key=f"pending-capability:{cap.id}",
            statement=(
                f"Capability '{cap.name}' is '{cap.status}', not active. "
                "Investigations it would enable are currently impossible, "
                "so unknowns in its territory cannot even be asked."
            ),
            basis=(BasisRef("capability", cap.id),),
            epistemic_state="possible",
            facets={"source": "capability_gap", "capability_id": cap.id,
                    "capability_name": cap.name, "status": cap.status,
                    "provenance": "model-proposed", "confirmed": False},
            next_step=(
                "Enumerate the investigations the missing capability blocks; "
                "assess which territories stay dark without it."
            ),
            follow_up_questions=(
                f"Activating '{cap.name}' would expose material unknowns Hami cannot currently see.",
            ),
        )


def _horizon_escape(ctx: DiscoveryContext) -> Iterable[Finding]:
    """Parked domains: owner-acknowledged territory outside the watch horizon. (PR #15)"""
    from app.services import operating_v4 as _opv4

    db = ctx.db
    for h in _opv4.list_horizon_domains(db):
        attrs = _pr15_horizon_attrs(h)
        if attrs.get("name") == _PR15_WATCH_HORIZON_NAME:
            continue
        if attrs.get("status") != "parked":
            continue
        name = (attrs.get("name") or "").strip()
        if not name:
            continue
        reason = (attrs.get("reason_parked") or "no reason recorded")[:160]
        yield Finding(
            kind="blind_spot",
            key=f"horizon-escape:{h.id}",
            statement=(
                f"Domain '{name}' is parked ({reason}). The watch horizon is a focus, "
                "not a universe boundary; unknown unknowns are most likely where "
                "Hami is not looking."
            ),
            basis=(BasisRef("entity", h.id),),
            epistemic_state="possible",
            subject_entity_ids=(h.id,),
            facets={"source": "horizon_escape", "parked_domain": name,
                    "reason_parked": reason, "horizon_relation": "outside",
                    "provenance": "model-proposed", "confirmed": False},
            next_step=(
                f"Bounded probe of '{name}' for anomalies, contradictions, "
                "or unasked questions."
            ),
            follow_up_questions=(
                f"There are material unknowns in parked domain '{name}'.",
            ),
        )


def _curiosity_questions(ctx: DiscoveryContext) -> Iterable[Finding]:
    """Step 3B-2: Recover curiosity_engine's question-generation into the discovery path.

    Uses CuriosityEngine's 8 weak-spot probes (read-only) to generate research
    questions, emitting each as a Finding of kind="question". Questions are
    MODEL-PROPOSED / UNCONFIRMED until supported by evidence (epistemic_state=
    "hypothesized", facets.confirmed=False).

    Does NOT call run_curiosity_scan() (which stores ResearchQuestions); this
    is a pure read-only probe yielding Findings. The legacy
    FORGEOS_LEGACY_INTELLIGENCE_ENABLED flag is not needed because this method
    creates no side effects — it only observes and proposes.
    """
    from app.services import curiosity_engine as _ce

    db = ctx.db
    ce = _ce.CuriosityEngine(db)

    # 1. Low-confidence beliefs -> questions about confirming/disproving evidence
    try:
        for belief in ce.find_low_confidence_beliefs():
            for q in ce.generate_questions_for_belief(belief):
                yield Finding(
                    kind="question",
                    key=f"curiosity-low-confidence-belief:{belief.id}:{_hash(q)[:8]}",
                    statement=q,
                    basis=(BasisRef("entity", belief.id),),
                    epistemic_state="hypothesized",
                    facets={"source": "curiosity_questions", "probe": "low_confidence_belief",
                            "belief_id": belief.id, "provenance": "model-proposed",
                            "confirmed": False},
                    next_step="Gather evidence that would confirm or disprove the belief.",
                )
    except Exception:
        # Source failure is not "no discovery" — skip this probe, continue others.
        pass

    # 2. Unexplored patterns -> questions about the pattern topic
    try:
        for pattern in ce.find_unexplored_patterns():
            for q in ce.generate_questions_for_pattern(pattern):
                yield Finding(
                    kind="question",
                    key=f"curiosity-unexplored-pattern:{pattern.id}:{_hash(q)[:8]}",
                    statement=q,
                    basis=(BasisRef("entity", pattern.id),),
                    epistemic_state="hypothesized",
                    facets={"source": "curiosity_questions", "probe": "unexplored_pattern",
                            "pattern_id": pattern.id, "provenance": "model-proposed",
                            "confirmed": False},
                    next_step="Investigate the pattern to form or refute a belief.",
                )
    except Exception:
        pass

    # 3. Contradicting patterns -> questions about why signals disagree
    try:
        for a, b in ce.find_contradictions():
            for q in ce.generate_questions_for_contradiction(a, b):
                yield Finding(
                    kind="question",
                    key=f"curiosity-contradiction:{a.id}-{b.id}:{_hash(q)[:8]}",
                    statement=q,
                    basis=(BasisRef("entity", a.id), BasisRef("entity", b.id)),
                    epistemic_state="hypothesized",
                    facets={"source": "curiosity_questions", "probe": "contradiction",
                            "pattern_a_id": a.id, "pattern_b_id": b.id,
                            "provenance": "model-proposed", "confirmed": False},
                    next_step="Resolve why the two signals disagree.",
                )
    except Exception:
        pass

    # 4. Unstable beliefs -> questions about why confidence keeps changing
    try:
        for belief in ce.find_unstable_beliefs():
            for q in ce.generate_questions_for_instability(belief):
                yield Finding(
                    kind="question",
                    key=f"curiosity-unstable-belief:{belief.id}:{_hash(q)[:8]}",
                    statement=q,
                    basis=(BasisRef("entity", belief.id),),
                    epistemic_state="hypothesized",
                    facets={"source": "curiosity_questions", "probe": "unstable_belief",
                            "belief_id": belief.id, "provenance": "model-proposed",
                            "confirmed": False},
                    next_step="Find what would settle the belief's truth.",
                )
    except Exception:
        pass

    # 5. Untested important beliefs -> questions about validating actions
    try:
        for belief in ce.find_untested_important_beliefs():
            for q in ce.generate_questions_for_untested_belief(belief):
                yield Finding(
                    kind="question",
                    key=f"curiosity-untested-belief:{belief.id}:{_hash(q)[:8]}",
                    statement=q,
                    basis=(BasisRef("entity", belief.id),),
                    epistemic_state="hypothesized",
                    facets={"source": "curiosity_questions", "probe": "untested_belief",
                            "belief_id": belief.id, "provenance": "model-proposed",
                            "confirmed": False},
                    next_step="Design a test that would validate or disprove the belief.",
                )
    except Exception:
        pass

    # 6. Contradictory causal knowledge -> questions about inconsistent results
    try:
        for causal in ce.find_contradictory_causal_knowledge():
            for q in ce.generate_questions_for_contradictory_causal(causal):
                basis = (BasisRef("entity", causal.belief_id),) if causal.belief_id else ()
                yield Finding(
                    kind="question",
                    key=f"curiosity-contradictory-causal:{causal.id}:{_hash(q)[:8]}",
                    statement=q,
                    basis=basis,
                    epistemic_state="hypothesized",
                    facets={"source": "curiosity_questions", "probe": "contradictory_causal",
                            "causal_id": causal.id, "provenance": "model-proposed",
                            "confirmed": False},
                    next_step="Investigate why the action produces inconsistent results.",
                )
    except Exception:
        pass

    # 7. Low-confidence strategies -> questions about needed evidence
    try:
        for strategy in ce.find_low_confidence_strategies():
            for q in ce.generate_questions_for_uncertain_strategy(strategy):
                yield Finding(
                    kind="question",
                    key=f"curiosity-uncertain-strategy:{strategy.id}:{_hash(q)[:8]}",
                    statement=q,
                    basis=(BasisRef("entity", strategy.id),),
                    epistemic_state="hypothesized",
                    facets={"source": "curiosity_questions", "probe": "low_confidence_strategy",
                            "strategy_id": strategy.id, "provenance": "model-proposed",
                            "confirmed": False},
                    next_step="Gather evidence to increase strategy confidence.",
                )
    except Exception:
        pass

    # 8. Unvalidated opportunities -> questions about revenue experiments
    try:
        for opportunity, _score in ce.find_unvalidated_opportunities():
            for q in ce.generate_questions_for_unvalidated_opportunity(opportunity):
                yield Finding(
                    kind="question",
                    key=f"curiosity-unvalidated-opportunity:{opportunity.id}:{_hash(q)[:8]}",
                    statement=q,
                    basis=(BasisRef("entity", opportunity.id),),
                    epistemic_state="hypothesized",
                    facets={"source": "curiosity_questions", "probe": "unvalidated_opportunity",
                            "opportunity_id": opportunity.id, "provenance": "model-proposed",
                            "confirmed": False},
                    next_step="Run a revenue experiment to validate willingness to pay.",
                )
    except Exception:
        pass

    # 9. Ungrounded opportunities -> questions about real payout mechanisms
    try:
        for opportunity in ce.find_ungrounded_opportunities():
            for q in ce.generate_questions_for_ungrounded_opportunity(opportunity):
                yield Finding(
                    kind="question",
                    key=f"curiosity-ungrounded-opportunity:{opportunity.id}:{_hash(q)[:8]}",
                    statement=q,
                    basis=(BasisRef("entity", opportunity.id),),
                    epistemic_state="hypothesized",
                    facets={"source": "curiosity_questions", "probe": "ungrounded_opportunity",
                            "opportunity_id": opportunity.id, "provenance": "model-proposed",
                            "confirmed": False},
                    next_step="Identify a real platform or program that would pay.",
                )
    except Exception:
        pass


DEFAULT_REGISTRY = DiscoveryMethodRegistry([
    DiscoveryMethod("evidence_contradiction", "1",
                    "Subjects whose recorded evidence both supports and refutes them, including held assumptions.",
                    _evidence_contradiction, emits=("contradiction",), requires=_SUBSTRATE),
    DiscoveryMethod("question_reframe", "1",
                    "Questions whose premise is refuted, or that repeated research could not answer.",
                    _question_reframe, emits=("question",), requires=_SUBSTRATE + ("substrate.research",)),
    DiscoveryMethod("numeric_divergence", "1",
                    "Large differences in any recorded measure across any recorded dimension (price, time, place, ...).",
                    _numeric_divergence, emits=("observation", "question"), requires=("substrate.entities",)),
    DiscoveryMethod("disconnection", "1",
                    "Entities of different kinds sharing a distinctive value with no recorded relation.",
                    _disconnection, emits=("hypothesis", "question"), requires=("substrate.entities", "substrate.relations")),
    DiscoveryMethod("isolation", "1",
                    "Entities left unconnected while their peers are connected (neglect, unused capacity, missing data).",
                    _isolation, emits=("observation", "question"), requires=("substrate.entities", "substrate.relations")),
    DiscoveryMethod("recurrence", "1",
                    "Events that keep repeating for the same entity (repeated behaviour, persistent needs).",
                    _recurrence, emits=("observation", "question"), requires=("substrate.events",)),
    DiscoveryMethod("capability_integrity", "1",
                    "Capabilities claimed active without an attributable passing test.",
                    _capability_integrity, emits=("capability_gap",), requires=("substrate.capabilities",)),
    DiscoveryMethod("refuted_basis_stop", "1",
                    "Earlier discoveries or proposed relations that evidence has refuted.",
                    _refuted_basis_stop, emits=("reason_to_stop",), requires=_SUBSTRATE),
    # Step 3B-1: recovered from PR #15 (unknown-unknown discovery loop).
    DiscoveryMethod("map_gap", "1",
                    "Owner-curated horizon domains with zero candidate coverage.",
                    _map_gap, emits=("new_unknown",), requires=("substrate.entities",)),
    DiscoveryMethod("superseded_belief", "1",
                    "Beliefs superseded by other beliefs; flawed assumptions may persist.",
                    _superseded_belief, emits=("contradiction",), requires=("substrate.entities",)),
    DiscoveryMethod("outcome_anomaly", "1",
                    "Real outcomes that failed their objective or are disputed.",
                    _outcome_anomaly, emits=("anomaly",), requires=("substrate.entities",)),
    DiscoveryMethod("pending_capability", "1",
                    "Capabilities the ledger says are needed but not yet active.",
                    _pending_capability, emits=("capability_gap",), requires=("substrate.capabilities",)),
    DiscoveryMethod("horizon_escape", "1",
                    "Parked domains outside the watch horizon where unknowns likely live.",
                    _horizon_escape, emits=("blind_spot",), requires=("substrate.entities",)),
    # Step 3B-2: recover curiosity_engine's question-generation into the discovery path.
    DiscoveryMethod("curiosity_questions", "1",
                    "Research questions generated from weak spots in the knowledge base (low-confidence beliefs, unexplored patterns, contradictions, unstable beliefs, untested beliefs, contradictory causal knowledge, uncertain strategies, unvalidated/ungrounded opportunities).",
                    _curiosity_questions, emits=("question",), requires=("substrate.entities",)),
])
