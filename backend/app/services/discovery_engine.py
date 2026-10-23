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


def _finding_cursor_digest(method: DiscoveryMethod, finding: Finding) -> str:
    """Opaque, versioned cursor for resuming a deterministic method stream.

    Do not persist raw finding keys: they can contain user-supplied domain
    values. Hashing also keeps cursor records compact and non-content-bearing.
    """
    basis = sorted((ref.kind, ref.id) for ref in finding.basis)
    return _hash(
        "discovery-cursor-v1", method.name, method.version,
        finding.kind, finding.key, basis,
    )[:32]


def _next_method_page(
    method: DiscoveryMethod,
    ctx: DiscoveryContext,
    cursor_digest: str | None,
    limit: int,
) -> tuple[list[Finding], str | None]:
    """Take the next bounded window, resuming after the last persisted finding.

    If the cursor disappeared because the method's output changed, restart from
    the beginning. If the cursor is at the end of the current stream, wrap to
    the beginning. That prevents deterministic first-N output from monopolizing
    every run while preserving lazy iteration and bounded result windows.
    """
    if limit <= 0:
        return [], cursor_digest

    def first_page() -> tuple[list[Finding], str | None]:
        rows = list(itertools.islice(method.run(ctx), limit))
        return rows, _finding_cursor_digest(method, rows[-1]) if rows else None

    if not cursor_digest:
        return first_page()

    cursor_found = False
    rows: list[Finding] = []
    for finding in method.run(ctx):
        if not cursor_found:
            if _finding_cursor_digest(method, finding) == cursor_digest:
                cursor_found = True
            continue
        rows.append(finding)
        if len(rows) >= limit:
            break

    if cursor_found and rows:
        return rows, _finding_cursor_digest(method, rows[-1])

    # A missing cursor means the stream changed; an exhausted cursor means the
    # previous window reached the end. In both cases take a fresh leading page.
    return first_page()


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

    # Resume each method from the last persisted cursor. The EVENT itself is
    # the durable continuation state; no new table or parallel queue is needed.
    cursors: dict[str, Any] = {}
    if persist:
        previous_run = (
            db.query(models.WorldEvent)
            .filter_by(event_type="discovery_run_completed")
            .order_by(models.WorldEvent.id.desc())
            .first()
        )
        previous_payload = _load(previous_run.payload) if previous_run is not None else {}
        previous_cursors = previous_payload.get("discovery_cursors", {})
        if isinstance(previous_cursors, dict):
            cursors = dict(previous_cursors)

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
        next_cursor_digest: str | None = None
        try:
            if persist:
                saved = cursors.get(method.name)
                cursor_digest = None
                if isinstance(saved, dict) and saved.get("version") == method.version:
                    candidate_digest = saved.get("last_key_digest")
                    if isinstance(candidate_digest, str) and re.fullmatch(r"[0-9a-f]{32}", candidate_digest):
                        cursor_digest = candidate_digest
                findings, next_cursor_digest = _next_method_page(
                    method, ctx, cursor_digest, max_findings_per_method
                )
            else:
                # Preview remains a read-only first-page view and does not move
                # the durable cursor.
                findings = list(itertools.islice(method.run(ctx), max_findings_per_method))
        except Exception as exc:  # a broken plugin must not stop the others
            entry["status"] = "error"
            report["errors"].append({"method": method.name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if persist:
            cursors[method.name] = {
                "version": method.version,
                "last_key_digest": next_cursor_digest,
            }
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
        event_payload = {
            key: (value if key == "methods" else len(value))
            for key, value in report.items() if isinstance(value, list) and key != "preview"
        }
        event_payload["discovery_cursors"] = cursors
        world_graph.create_event(
            db, event_type="discovery_run_completed", source=actor,
            payload=event_payload,
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


def build_global_frontier(db: Session, *, limit: int = 50) -> dict[str, Any]:
    """Read-only, cross-domain projection of unresolved recorded work.

    This deliberately does not rank every kind of value on one numeric scale.
    It interleaves work lanes and discovery kinds so a large pool in one lane
    cannot monopolize the whole result. Domain labels are surfaced only when
    explicitly recorded; they are never inferred from a title. No records are
    written, promoted, authorized, or executed by this projection.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("limit must be an integer from 1 to 200")
    scan_limit = min(1000, limit * 4)
    lanes: dict[str, list[dict[str, Any]]] = defaultdict(list)
    scan_counts: dict[str, int] = {}
    scan_limited: list[str] = []

    def stamp(value: Any) -> str | None:
        return value.isoformat() if hasattr(value, "isoformat") else None

    def recorded_hint(facets: Any) -> str | None:
        if not isinstance(facets, dict):
            return None
        for key in ("domain", "territory", "geography", "geographic_scope"):
            value = facets.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    # Persisted discovery findings retain their open-world kinds. A new kind
    # automatically gets its own lane instead of requiring taxonomy code.
    findings = (
        db.query(models.SubstrateEntity)
        .filter_by(source_system=ENGINE_ACTOR, status="active")
        .order_by(models.SubstrateEntity.created_at.asc(), models.SubstrateEntity.id.asc())
        .limit(scan_limit)
        .all()
    )
    scan_counts["discovery_findings"] = len(findings)
    if len(findings) == scan_limit:
        scan_limited.append("discovery_findings")
    for row in findings:
        attrs = _load(row.attributes)
        kind = attrs.get("discovery_kind") or row.entity_type
        if not isinstance(kind, str) or not kind:
            kind = "unclassified"
        facets = attrs.get("facets")
        basis = attrs.get("basis")
        if not isinstance(basis, list):
            basis = []
        lane = f"discovery:{kind}"
        lanes[lane].append({
            "frontier_id": f"discovery:{row.id}",
            "record_type": "discovery_finding",
            "lane": lane,
            "kind": kind,
            "title": str(attrs.get("statement") or row.display_name),
            "status": row.status,
            "epistemic_state": attrs.get("epistemic_state"),
            "basis": basis,
            "source_refs": [{"kind": "entity", "id": row.id}],
            "domain_hint": recorded_hint(facets),
            "value_dimensions": (
                [v for v in facets.get("value_dimensions", []) if isinstance(v, str)]
                if isinstance(facets, dict) and isinstance(facets.get("value_dimensions"), list)
                else []
            ),
            "next_step": str(attrs.get("next_step") or (
                "Review the recorded finding and cited basis; investigate, refute, defer, or stop."
            )),
            "created_at": stamp(row.created_at),
        })

    # UNKNOWN_MAP.md is the authoritative unknown registry; Claim rows are
    # its additive operational projection. Keep unresolved rows in the frontier
    # with their registered IDs and cheapest-test provenance.
    unknown_claims = (
        db.query(models.Claim)
        .filter(models.Claim.provenance.like("%UNKNOWN_MAP.md%"))
        .filter(models.Claim.epistemic_state.in_(("unknown", "hypothesized", "blocked", "tested")))
        .order_by(models.Claim.created_at.asc(), models.Claim.id.asc())
        .limit(scan_limit)
        .all()
    )
    scan_counts["unknown_map_claims"] = len(unknown_claims)
    if len(unknown_claims) == scan_limit:
        scan_limited.append("unknown_map_claims")
    for row in unknown_claims:
        provenance = str(row.provenance or "")
        identity_match = re.search(r"UNKNOWN_MAP\.md\s+§([A-D])\s+row\s+([A-Z]+\d+)", provenance)
        unknown_id = identity_match.group(2) if identity_match else f"claim-{row.id}"
        section = identity_match.group(1) if identity_match else "unclassified"
        cheapest_match = re.search(r"Cheapest test:\s*(.*)$", provenance)
        lane = f"unknown_map:{section}"
        lanes[lane].append({
            "frontier_id": f"unknown_map:{unknown_id}",
            "record_type": "unknown_map_entry",
            "lane": lane,
            "kind": "open_unknown",
            "title": row.statement,
            "status": row.epistemic_state,
            "epistemic_state": row.epistemic_state,
            "basis": [],
            "source_refs": [{"kind": "claim", "id": row.id}],
            "unknown_id": unknown_id,
            "registry_provenance": provenance,
            "recorded_cheapest_test": cheapest_match.group(1).strip() if cheapest_match else None,
            "domain_hint": None,
            "next_step": (
                "Review the registered cheapest test and access boundary; "
                "do not treat this record as authorization to perform it."
            ),
            "created_at": stamp(row.created_at),
        })

    # Operational questions are included independently of commercial Bet
    # candidates. Their stored priority is local metadata, not a universal
    # value score and is never compared against other record types.
    questions = (
        db.query(models.ResearchQuestion)
        .filter(models.ResearchQuestion.status.in_(("open", "planned")))
        .order_by(
            models.ResearchQuestion.priority_score.desc(),
            models.ResearchQuestion.created_at.asc(),
            models.ResearchQuestion.id.asc(),
        )
        .limit(scan_limit)
        .all()
    )
    scan_counts["research_questions"] = len(questions)
    if len(questions) == scan_limit:
        scan_limited.append("research_questions")
    for row in questions:
        source_refs = []
        for field_name, kind in (
            ("source_pattern_id", "pattern"),
            ("source_belief_id", "belief"),
            ("source_claim_id", "claim"),
            ("source_rare_signal_id", "rare_signal_assessment"),
        ):
            value = getattr(row, field_name, None)
            if value is not None:
                source_refs.append({"kind": kind, "id": value})
        lanes["research_questions"].append({
            "frontier_id": f"research_question:{row.id}",
            "record_type": "research_question",
            "lane": "research_questions",
            "kind": "open_question",
            "title": row.question,
            "status": row.status,
            "basis": [],
            "source_refs": source_refs,
            "recorded_priority_score": row.priority_score,
            "priority_scope": "research-question ordering only; not comparable across lanes",
            "domain_hint": None,
            "next_step": (
                "Use the existing research planner to form a bounded plan; "
                "check source clearance before any collection."
            ),
            "created_at": stamp(row.created_at),
        })

    # Existing research lifecycle states are visible here, not re-created in
    # a new queue. Running work is shown for observability, not resubmitted.
    tasks = (
        db.query(models.ResearchTask)
        .filter(models.ResearchTask.status.in_(("planned", "needs_research", "failed", "running")))
        .order_by(models.ResearchTask.created_at.asc(), models.ResearchTask.id.asc())
        .limit(scan_limit)
        .all()
    )
    scan_counts["research_tasks"] = len(tasks)
    if len(tasks) == scan_limit:
        scan_limited.append("research_tasks")
    task_next_steps = {
        "planned": "Review prerequisites and source clearance before bounded collection.",
        "needs_research": "Inspect unresolved requirements and plan a permitted follow-up.",
        "failed": "Inspect the recorded failure and use the existing retry policy if eligible.",
        "running": "Check the existing task lifecycle and stale-task recovery; do not duplicate the task.",
    }
    for row in tasks:
        lanes["research_tasks"].append({
            "frontier_id": f"research_task:{row.id}",
            "record_type": "research_task",
            "lane": "research_tasks",
            "kind": "unfinished_research",
            "title": str(row.objective or row.query),
            "status": row.status,
            "basis": [],
            "source_refs": [{"kind": "research_question", "id": row.question_id}],
            "research_source": row.source,
            "attempts": row.attempts,
            "max_attempts": row.max_attempts,
            "domain_hint": None,
            "next_step": task_next_steps.get(row.status, "Review task state."),
            "created_at": stamp(row.created_at),
        })

    capabilities = (
        db.query(models.ForgeCapability)
        .filter(models.ForgeCapability.status.in_(("proposed", "building", "tested")))
        .order_by(models.ForgeCapability.created_at.asc(), models.ForgeCapability.id.asc())
        .limit(scan_limit)
        .all()
    )
    scan_counts["capabilities"] = len(capabilities)
    if len(capabilities) == scan_limit:
        scan_limited.append("capabilities")
    capability_next_steps = {
        "proposed": "Validate the requirement and specification before starting a build.",
        "building": "Test the implementation with attributable evidence and the existing lifecycle.",
        "tested": "Verify the test record and complete activation only through the existing lifecycle.",
    }
    for row in capabilities:
        attrs = _load(row.attributes)
        lanes["capabilities"].append({
            "frontier_id": f"capability:{row.id}",
            "record_type": "capability",
            "lane": "capabilities",
            "kind": row.capability_type,
            "title": row.name,
            "description": row.description,
            "status": row.status,
            "basis": [],
            "source_refs": [{"kind": "capability", "id": row.id}],
            "provides": attrs.get("provides", []),
            "domain_hint": recorded_hint(attrs),
            "next_step": capability_next_steps.get(row.status, "Review capability lifecycle state."),
            "created_at": stamp(row.created_at),
        })

    outcomes = (
        db.query(models.Outcome)
        .filter(
            (models.Outcome.success.is_(False))
            | (models.Outcome.verification_state == "DISPUTED")
        )
        .order_by(models.Outcome.id.asc())
        .limit(scan_limit)
        .all()
    )
    scan_counts["outcomes"] = len(outcomes)
    if len(outcomes) == scan_limit:
        scan_limited.append("outcomes")
    for row in outcomes:
        source_kind = getattr(row.source_kind, "value", row.source_kind)
        lanes["outcomes"].append({
            "frontier_id": f"outcome:{row.id}",
            "record_type": "outcome",
            "lane": "outcomes",
            "kind": "failed_or_disputed_outcome",
            "title": str(row.qualitative_result or row.outcome_type or f"Outcome {row.id}"),
            "status": row.verification_state,
            "success": row.success,
            "actual_value": row.actual_value,
            "unit": row.unit,
            "data_scope": row.data_scope,
            "source_kind": source_kind,
            "basis": [],
            "source_refs": [{"kind": "outcome", "id": row.id}],
            "domain_hint": None,
            "next_step": "Review the outcome evidence and causal assumptions before changing a belief or repeating the intervention.",
            "created_at": None,
        })

    lane_counts = {name: len(items) for name, items in lanes.items()}
    candidate_count = sum(lane_counts.values())
    # Operational records appear in the first round; dynamic discovery kinds
    # are then interleaved too. A busy lane cannot fill the entire result.
    lane_rank = {"capabilities": 0, "outcomes": 1, "research_questions": 2, "research_tasks": 3}
    lane_names = sorted(lanes, key=lambda name: (lane_rank.get(name, 4), name))
    selected: list[dict[str, Any]] = []
    while len(selected) < limit:
        added = False
        for lane in lane_names:
            if lanes[lane] and len(selected) < limit:
                selected.append(lanes[lane].pop(0))
                added = True
        if not added:
            break

    return {
        "read_only": True,
        "selection_method": "round_robin_by_record_kind",
        "limit": limit,
        "candidate_count_scanned": candidate_count,
        "lane_counts_scanned": lane_counts,
        "source_counts_scanned": scan_counts,
        "scan_limited_sources": scan_limited,
        "truncated": candidate_count > len(selected) or bool(scan_limited),
        "items": selected,
        "boundary": (
            "Diversified view of recorded unresolved work, not a measure of total world value. "
            "Items are proposals or operational records, not proof, authorization, or instructions to execute."
        ),
    }


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
    from app.services.demand_understanding import normalize_observation_content

    by_type: dict[str, list[tuple[models.SubstrateEntity, dict[str, Any]]]] = defaultdict(list)
    for row in ctx.entities():
        by_type[row.entity_type].append((row, ctx.attributes(row)))
    for entity_type, rows in sorted(by_type.items()):
        if len(rows) < 3:
            continue
        numeric_keys = sorted({key for _, attrs in rows for key, value in attrs.items()
                               if _is_number(value) and key != "id" and not key.endswith("_id")
                               and not _SENSITIVE_DISCOVERY_ATTRIBUTE.search(str(key))})
        group_keys = sorted({key for _, attrs in rows for key, value in attrs.items()
                             if isinstance(value, str) and 0 < len(value) <= 80
                             and not _SENSITIVE_DISCOVERY_ATTRIBUTE.search(str(key))})
        for number_key in numeric_keys:
            for group_key in group_keys:
                groups: dict[str, list[tuple[models.SubstrateEntity, float]]] = defaultdict(list)
                for row, attrs in rows:
                    group_value = attrs.get(group_key)
                    if (
                        _is_number(attrs.get(number_key))
                        and isinstance(group_value, str)
                        and _safe_discovery_join_value(group_key, group_value, normalize_observation_content)
                    ):
                        groups[group_value].append((row, float(attrs[number_key])))
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
_SENSITIVE_DISCOVERY_ATTRIBUTE = re.compile(
    r"(?:^|[_\W])(?:email|e-mail|phone|telephone|mobile|contact|recipient|"
    r"person[_\s-]?name|customer[_\s-]?name|seller[_\s-]?name|owner[_\s-]?name|"
    r"full[_\s-]?name|first[_\s-]?name|last[_\s-]?name|display[_\s-]?name|"
    r"message|notes?|content|transcript|conversation|description|summary|body|"
    r"statement|claim|comment|raw|payload|provenance|"
    r"password|secret|token|credential|api[_\s-]?key|"
    r"account[_\s-]?(?:number|details?)|bank[_\s-]?(?:account|details?)|wallet|"
    r"payment[_\s-]?(?:reference|ref|id|details?)|transaction[_\s-]?(?:reference|ref|id)|"
    r"national[_\s-]?(?:id|identity)|citizenship|street|address|road|"
    r"house[_\s-]?(?:number|no|num)|flat[_\s-]?(?:number|no|num)|building[_\s-]?(?:number|no|num)|"
    r"postal[_\s-]?code|postcode|zip[_\s-]?code|pin(?:[_\s-]?code)?|"
    r"latitude|longitude|lat|lon|lng|geo[_\s-]?(?:lat(?:itude)?|lon(?:gitude)?)|"
    r"coordinates?|geolocation|gps)(?:$|[_\W])",
    re.IGNORECASE,
)
_PRIVATE_DISCOVERY_ENTITY_TYPE_TOKENS = frozenset({
    "person", "people", "individual", "customer", "customers", "seller", "sellers",
    "buyer", "buyers", "owner", "owners", "contact", "contacts", "member", "members",
    "lead", "leads", "applicant", "applicants", "subscriber", "subscribers", "worker",
    "workers", "employee", "employees", "user", "users", "recipient", "requester",
    "client", "patient", "student", "students",
})

# Precise locations are too identifying for an open-ended join key, even when
# a source placed them in a generic field or a list of tags.
_PRECISE_ADDRESS_VALUE = re.compile(
    r"(?i)(?:"
    r"\b[0-9०-९]{1,5}\s+(?:[\wऀ-ॿ.'-]+\s+){0,4}"
    r"(?:road|rd|street|st|avenue|ave|lane|ln|marg|marga|sadak|galli|tole|chowk|chok|path|highway|hwy|"
    r"सडक|मार्ग|गल्ली|गल्लि|टोल|चोक|चौक|घर)\b"
    r"|\b(?:[\wऀ-ॿ.'-]+\s+){1,4}"
    r"(?:road|rd|street|st|avenue|ave|lane|ln|marg|marga|sadak|galli|tole|chowk|chok|path|highway|hwy|"
    r"सडक|मार्ग|गल्ली|गल्लि|टोल|चोक|चौक)"
    r"\s*#?\s*[0-9०-९]{1,5}\b"
    r"|(?:घर(?:\s*(?:नं|नम्बर|number))?|टोल|गल्ली|गल्लि|मार्ग|सडक|चोक|चौक)"
    r"\s*[-:#.\s]*[0-9०-९]{1,5}\b"
    r")"
)
_PRECISE_COORDINATE_PAIR = re.compile(
    r"(?<!\d)-?\d{1,3}\.\d{3,}\s*[,/]\s*-?\d{1,3}\.\d{3,}(?!\d)"
)


def _safe_discovery_join_value(
    attribute: str,
    candidate: str,
    normalizer: Callable[[str], str],
) -> bool:
    """Whether a value is safe to persist as an open-ended discovery join key.

    Attribute names alone cannot identify every private field: arbitrary tags
    may themselves contain a home address or precise coordinates. Keep the
    location clues useful at a coarse level, but reject precise/address-shaped
    values before they become statements, facets, relations, or follow-up text.
    """
    if _SENSITIVE_DISCOVERY_ATTRIBUTE.search(str(attribute)):
        return False
    collapsed = " ".join((candidate or "").split())
    if not collapsed:
        return False
    if _PRECISE_ADDRESS_VALUE.search(collapsed) or _PRECISE_COORDINATE_PAIR.search(collapsed):
        return False
    normalized = collapsed.casefold()
    safe_value = normalizer(collapsed).casefold()
    return safe_value == normalized and "[redacted-" not in normalized


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
    """Find unrecorded cross-type connections from comparable, privacy-screened attributes."""
    from app.services.demand_understanding import normalize_observation_content

    def safe_label(row: models.SubstrateEntity) -> str:
        entity_type = str(row.entity_type or "entity")
        type_tokens = {
            token for token in re.split(r"[^a-z0-9]+", entity_type.casefold()) if token
        }
        if type_tokens & _PRIVATE_DISCOVERY_ENTITY_TYPE_TOKENS:
            return f"{entity_type} #{row.id}"
        display_name = " ".join((row.display_name or "").split())
        sanitized_name = normalize_observation_content(display_name)
        if (
            not display_name
            or sanitized_name.casefold() != display_name.casefold()
            or "[redacted-" in sanitized_name.casefold()
        ):
            return f"{entity_type} #{row.id}"
        return f"{display_name} ({entity_type} #{row.id})"

    db = ctx.db
    holders: dict[str, dict[int, tuple[models.SubstrateEntity, str]]] = defaultdict(dict)
    for row in ctx.entities():
        for key, value in ctx.attributes(row).items():
            # Avoid joining free-form/private fields into durable discovery output.
            if _SENSITIVE_DISCOVERY_ATTRIBUTE.search(str(key)):
                continue
            if isinstance(value, str):
                candidates = ((value, str(key)),)
            elif isinstance(value, list):
                # Tags and other enumerated values are useful cross-domain clues.
                # Ignore nested structures and numbers; don't stringify whole lists.
                candidates = (
                    (item, f"{key}[]")
                    for item in value
                    if isinstance(item, str)
                )
            else:
                continue

            for candidate, field_name in candidates:
                collapsed = " ".join(candidate.split())
                normalized = collapsed.casefold()
                if len(normalized) < 3 or len(normalized) > 120:
                    continue
                if normalized in _IGNORED_VALUES or normalized.replace(".", "").isdigit():
                    continue
                # Screen both the source field and the value. Precise addresses
                # can arrive through generic tag/list attributes, not only fields
                # explicitly named "address".
                if not _safe_discovery_join_value(str(key), candidate, normalize_observation_content):
                    continue
                holders[normalized].setdefault(row.id, (row, field_name))
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
                    statement=(f"{safe_label(left)} and {safe_label(right)} both record {value!r} "
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
                        f"What evidence would show whether {safe_label(left)} and {safe_label(right)} are "
                        f"actually connected through {value!r}, and what would that connection make possible?",
                    ),
                )



def _capability_chain(
    ctx: DiscoveryContext,
    *,
    max_holders: int = 8,
    max_findings: int = 250,
) -> Iterable[Finding]:
    """Compose explicit output/input declarations into bounded chain hypotheses.

    This is not semantic matching: only exact normalized declarations in
    named fields are joined. A chain is a research candidate, never evidence
    that the capabilities are compatible, available, authorized, agreed, or
    valuable in practice.
    """
    from app.services.demand_understanding import normalize_observation_content

    output_fields = ("provides", "outputs", "capabilities", "capability_tags")
    input_fields = ("requires", "inputs", "needs", "required_tags")
    rows = ctx.entities()
    outputs_by_token: dict[str, list[tuple[models.SubstrateEntity, str, str]]] = defaultdict(list)
    inputs_by_token: dict[str, list[tuple[models.SubstrateEntity, str, str]]] = defaultdict(list)
    outputs_by_entity: dict[int, list[tuple[str, str, str]]] = {}
    inputs_by_entity: dict[int, list[tuple[str, str, str]]] = {}

    def declarations(row: models.SubstrateEntity, fields: tuple[str, ...]) -> list[tuple[str, str, str]]:
        attrs = ctx.attributes(row)
        by_token: dict[str, tuple[str, str]] = {}
        for field_name in fields:
            raw = attrs.get(field_name)
            values = [raw] if isinstance(raw, str) else raw if isinstance(raw, list) else ()
            for value in values:
                if not isinstance(value, str):
                    continue
                collapsed = " ".join(value.split())
                normalized = collapsed.casefold()
                if (
                    len(normalized) < 3
                    or len(normalized) > 120
                    or normalized.replace(".", "").isdigit()
                    or normalized in _IGNORED_VALUES
                    or not _safe_discovery_join_value(field_name, collapsed, normalize_observation_content)
                ):
                    continue
                # One declaration per entity/token prevents duplicated aliases
                # from multiplying the same candidate path.
                by_token.setdefault(normalized, (collapsed, field_name))
        return [(token, value, field_name) for token, (value, field_name) in sorted(by_token.items())]

    def safe_label(row: models.SubstrateEntity) -> str:
        entity_type = str(row.entity_type or "entity")
        type_tokens = {
            token for token in re.split(r"[^a-z0-9]+", entity_type.casefold()) if token
        }
        if type_tokens & _PRIVATE_DISCOVERY_ENTITY_TYPE_TOKENS:
            return f"{entity_type} #{row.id}"
        display_name = " ".join((row.display_name or "").split())
        safe_name = normalize_observation_content(display_name)
        if not display_name or safe_name.casefold() != display_name.casefold() or "[redacted-" in safe_name.casefold():
            return f"{entity_type} #{row.id}"
        return f"{display_name} ({entity_type} #{row.id})"

    for row in rows:
        declared_outputs = declarations(row, output_fields)
        declared_inputs = declarations(row, input_fields)
        outputs_by_entity[row.id] = declared_outputs
        inputs_by_entity[row.id] = declared_inputs
        for token, value, field_name in declared_outputs:
            outputs_by_token[token].append((row, field_name, value))
        for token, value, field_name in declared_inputs:
            inputs_by_token[token].append((row, field_name, value))

    # Deterministic ordering makes bounded pagination resumable and idempotent.
    for index in (outputs_by_token, inputs_by_token):
        for holders in index.values():
            holders.sort(key=lambda item: (item[0].id, item[1]))

    emitted = 0
    for middle in rows:
        middle_inputs = inputs_by_entity.get(middle.id, [])
        middle_outputs = outputs_by_entity.get(middle.id, [])
        for input_token, _input_value, middle_input_field in middle_inputs:
            suppliers = outputs_by_token.get(input_token, [])
            if not suppliers or len({row.id for row, _, _ in suppliers}) > max_holders:
                continue
            for source_row, source_field, source_value in suppliers:
                if source_row.id == middle.id:
                    continue
                for output_token, output_value, middle_output_field in middle_outputs:
                    if output_token == input_token:
                        continue
                    consumers = inputs_by_token.get(output_token, [])
                    if not consumers or len({row.id for row, _, _ in consumers}) > max_holders:
                        continue
                    for target_row, target_field, _target_value in consumers:
                        if target_row.id in {source_row.id, middle.id}:
                            continue
                        fingerprint = _hash(input_token, output_token)[:12]
                        key = (
                            f"capability-chain:{source_row.id}:{middle.id}:{target_row.id}:"
                            f"{source_field}:{middle_input_field}:{middle_output_field}:{target_field}:{fingerprint}"
                        )
                        yield Finding(
                            kind="hypothesis",
                            key=key,
                            statement=(
                                "Recorded declarations form a possible three-entity capability chain: "
                                f"{safe_label(source_row)} lists an output matching a declared input on "
                                f"{safe_label(middle)}; that entity lists a different output matching a declared "
                                f"input on {safe_label(target_row)}. This is only a composition hypothesis; "
                                "compatibility, capacity, permission, agreement, cost, benefit, and real-world "
                                "availability have not been verified."
                            ),
                            basis=(
                                BasisRef("entity", source_row.id),
                                BasisRef("entity", middle.id),
                                BasisRef("entity", target_row.id),
                            ),
                            epistemic_state="hypothesized",
                            subject_entity_ids=(source_row.id, middle.id, target_row.id),
                            facets={
                                "pattern": "capability_chain",
                                "chain_entity_ids": [source_row.id, middle.id, target_row.id],
                                "handoffs": [
                                    {
                                        "matched_declaration": source_value,
                                        "producer_attribute": source_field,
                                        "consumer_attribute": middle_input_field,
                                    },
                                    {
                                        "matched_declaration": output_value,
                                        "producer_attribute": middle_output_field,
                                        "consumer_attribute": target_field,
                                    },
                                ],
                                "declarations_are_not_verification": True,
                            },
                            next_step=(
                                "Verify the actual specifications and authority for each handoff; define one "
                                "measurable benefit and a falsifying test before any contact, commitment, or action."
                            ),
                            proposed_relations=(
                                ProposedRelation(
                                    "may_relate",
                                    "Explicit output/input declarations match; practical compatibility is unverified.",
                                    from_entity_id=source_row.id,
                                    to_entity_id=middle.id,
                                    direction="directed",
                                ),
                                ProposedRelation(
                                    "may_relate",
                                    "Explicit output/input declarations match; practical compatibility is unverified.",
                                    from_entity_id=middle.id,
                                    to_entity_id=target_row.id,
                                    direction="directed",
                                ),
                            ),
                            follow_up_questions=(
                                "What evidence would show whether this chain can produce a measurable benefit, "
                                "at what cost, and under which constraints?",
                            ),
                        )
                        emitted += 1
                        if emitted >= max_findings:
                            return

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


def _ignorance_map(ctx: DiscoveryContext) -> Iterable[Finding]:
    """Explicit map of what Hami cannot investigate: capability-blocked domains.

    Scans capability gaps and unanswered questions to identify domains where
    Hami lacks the means to investigate. For each, records whether existing
    collectors could help or if the domain is blocked by a missing capability.

    This makes Hami's ignorance visible and actionable — a prerequisite for
    autonomous expansion. It does not fake discovery; it names the blocker.
    """
    from app import models as _models

    db = ctx.db

    # Find capability gaps (things Hami needs but cannot do)
    gaps = (
        db.query(_models.ForgeCapability)
        .filter(_models.ForgeCapability.status.in_(["proposed"]))
        .limit(20)
        .all()
    )
    for gap in gaps:
        gap_name = gap.name or f"capability_{gap.id}"
        yield Finding(
            kind="blind_spot",
            key=f"ignorance-gap:{gap.id}",
            statement=(
                f"Hami lacks capability '{gap_name}'. "
                f"Domains requiring this capability cannot be investigated. "
                f"Blocker: {gap.description or 'no description'}"
            ),
            basis=(BasisRef("capability", gap.id),),
            epistemic_state="possible",
            facets={"source": "ignorance_map", "gap_type": "capability",
                    "capability_name": gap_name,
                    "provenance": "model-proposed", "confirmed": False},
            next_step=(
                f"Determine if existing collectors can substitute for '{gap_name}', "
                "or record the specific infrastructure needed."
            ),
            follow_up_questions=(
                f"What investigations are blocked by missing capability '{gap_name}'?",
            ),
        )

    # Find questions with no research tasks (uninvestigated)
    uninvestigated = (
        db.query(_models.ResearchQuestion)
        .outerjoin(_models.ResearchTask,
                   _models.ResearchTask.question_id == _models.ResearchQuestion.id)
        .filter(_models.ResearchTask.id.is_(None))
        .filter(_models.ResearchQuestion.status.in_(["open", "proposed"]))
        .limit(10)
        .all()
    )
    for q in uninvestigated:
        q_text = (q.question or "")[:120]
        yield Finding(
            kind="new_unknown",
            key=f"ignorance-uninvestigated:{q.id}",
            statement=(
                f"Question '{q_text}...' has no research tasks. "
                "Hami has identified the unknown but not yet investigated it."
            ),
            basis=(BasisRef("research_question", q.id),),
            epistemic_state="possible",
            facets={"source": "ignorance_map", "gap_type": "uninvestigated",
                    "provenance": "model-proposed", "confirmed": False},
            next_step=(
                "Create a bounded research task using an existing cleared collector, "
                "or record why no collector can address this question."
            ),
            follow_up_questions=(
                f"What is the cheapest useful observation for '{q_text}...'?",
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
    DiscoveryMethod("numeric_divergence", "2",
                    "Large differences in recorded measures across non-sensitive dimensions; precise addresses and coordinates are excluded.",
                    _numeric_divergence, emits=("observation", "question"), requires=("substrate.entities",)),
    DiscoveryMethod("disconnection", "2",
                    "Entities of different kinds sharing a distinctive scalar or list-tag value without a recorded relation; contact-bearing fields, precise addresses, coordinates and email/phone values are excluded.",
                    _disconnection, emits=("hypothesis", "question"), requires=("substrate.entities", "substrate.relations")),
    DiscoveryMethod("capability_chain", "1",
                    "Bounded composition of explicit outputs/provides declarations through an intermediate entity into a second declared input; hypotheses only.",
                    _capability_chain, emits=("hypothesis", "question"), requires=("substrate.entities",)),
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
    DiscoveryMethod("ignorance_map", "1",
                    "Capability-blocked domains and uninvestigated questions: explicit map of what Hami cannot currently investigate.",
                    _ignorance_map, emits=("blind_spot", "new_unknown"),
                    requires=("substrate.capabilities", "substrate.research")),
    # Step 3B-2: recover curiosity_engine's question-generation into the discovery path.
    DiscoveryMethod("curiosity_questions", "1",
                    "Research questions generated from weak spots in the knowledge base (low-confidence beliefs, unexplored patterns, contradictions, unstable beliefs, untested beliefs, contradictory causal knowledge, uncertain strategies, unvalidated/ungrounded opportunities).",
                    _curiosity_questions, emits=("question",), requires=("substrate.entities",)),
])
