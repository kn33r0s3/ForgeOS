"""DimagFeatureBuilder: field rows -> (Xg, Xh, Xl, graph, allowed, target).

Inputs are plain dicts with the column names of backend/app/models.py
(design section 1.2, re-verified 22 Nov 2026) -- never live ORM
objects -- so the builder is testable from anonymized fixture rows and
never needs a database.

Row conventions (all fields optional unless noted; missing values use
the design's missing-value rules):
  gate (SubstrateEntity, entity_type == "gate"):
    id, display_name, attributes (dict or JSON string; may carry
    "criteria" (list of criterion names), "zone_id" (int 0-11 or None),
    "run_state" (one of schema.RUN_STATES)).
  relation (WorldRelation):
    id, from_entity_id, to_entity_id, relation_type, direction
    ("directed"/"bidirectional"), strength (0-1 or None),
    truth_state, valid_from, valid_to.
  evidence (Evidence):
    id, subject_kind, subject_id, claim, support_level,
    content_fingerprint, source, verifier, proof_level, provenance,
    consent_status, recorded_at / observed_at, source_kind.
    A gate's evidence is linked by subject_kind == "gate" and
    subject_id == gate id.
  event (WorldEvent):
    id, event_type, entity_id, relation_id, payload (dict or JSON
    string), source, occurred_at, idempotency_key.
    Gate lifecycle events: gate_started / gate_paused / gate_resumed /
    gate_stopped / gate_completed / gate_retired / gate_needs_approval /
    gate_reconciling. Evaluation events: gate_evaluated, whose payload
    may carry "state" (one of the 5 evidence states) and "criteria" +
    "met" (parallel lists) or "criteria_met" / "criteria_total".
  action (Action):
    id, decision_id, goal_id, opportunity_id, action_type, objective,
    gate_id (caller-resolved join key: the gate this action belongs
    to -- the Action table has no gate column; the caller resolves
    decision_id / goal_id / opportunity_id linkage before calling),
    parameters_json (dict or JSON string), status, policy_result,
    approved_at, started_at, completed_at, verification_state,
    contact_entity_id (for DoNotContact checks).
  outcome (Outcome):
    id, action_id, observed_at, outcome_type, actual_value, success,
    verification_state, data_scope, source_kind.

Documented v1 interpretations (design leaves these open; each is
recorded here, never hidden):
  * Complete evidence contract (helper ch6, gate slot 0): claim +
    content_fingerprint (artifact hash) + source + verifier +
    proof_level >= 1 + provenance present. Evidence has no dedicated
    scope/method columns; scope is proxied by subject_kind/subject_id
    and method by provenance. If dedicated columns ever land, the
    schema version bumps.
  * Evidence state when no gate_evaluated event carries a state:
    CONTESTED if one claim has both supporting and refuted evidence;
    BLOCKED if any linked evidence is refuted; PROVEN if at least one
    linked evidence is supported/tested with a complete contract and
    none is refuted; IN_PROGRESS if any linked evidence exists;
    UNKNOWN otherwise.
  * Candidates are PROPOSED / APPROVAL_REQUIRED / APPROVED actions,
    PLUS the executed label action when one exists (design 2.3 + 2.6
    only cohere this way: an executed action is not a candidate by
    status, yet the label must point at a lead). If the label action
    falls outside the top 5, the example is unlabelled (target -1)
    and metadata records label_dropped_out_of_top5.
  * Lead slot 9 (uncertainty_gate) = Xg[0] * resolution factor, the
    factor from parameters_json "uncertainty_resolution" (default 1.0).
    This honors both clauses of design 2.3 slot 9.
  * Helper ch8 (NEVER COPY) value = 1 - duplicated share.
  * "Gate family" for benefit/risk history = the gates of this
    example's neighborhood.
  * SUPPORTS strength for action_value / graph_value is the mean
    strength of SUPPORTS (and DERIVED_FROM, for graph_value)
    relations touching the gate; objective-level matching has no
    column, so the gate-level mean is used and recorded.
"""

import hashlib
import json
import math
from datetime import datetime, timezone

import numpy as np

from . import schema
from .governance_mask import GovernanceInput, allowed_mask, needs_approval
from .relations import (
    UnknownRelationTypeError,
    canonical_relation_name,
    relation_id,
    reverse_relation_id,
)

MAX_LEADS = 5
MAX_BASE_EDGES = 56  # G * (G - 1); the ranker's make_graph cap.
CYCLE_WINDOW_DAYS = 7
DORMANT_DECAY_DAYS = 7
COST_BUDGET_SCALE_NPR = 100000.0  # v1 scale: NPR 100k of budget == cost 1.0.

# Gate lifecycle event -> run state (design 2.1, run_state slots).
LIFECYCLE_EVENT_STATES = {
    "gate_started": "RUNNING",
    "gate_paused": "PAUSED",
    "gate_resumed": "RUNNING",
    "gate_stopped": "STOPPED",
    "gate_completed": "COMPLETED",
    "gate_retired": "RETIRED",
    "gate_needs_approval": "NEEDS_APPROVAL",
    "gate_reconciling": "RECONCILING",
}

# Truth-state order for neighborhood ranking (design 3):
# supported / tested before hypothesized, then possible, unknown.
TRUTH_ORDER = {"supported": 0, "tested": 1, "hypothesized": 2, "possible": 3, "unknown": 4}

CANDIDATE_STATUSES = ("PROPOSED", "APPROVAL_REQUIRED", "APPROVED")
EXECUTED_STATUSES = ("RUNNING", "SUCCEEDED", "VERIFIED", "FAILED")


def _as_dict(value):
    """Parse a JSON-string-or-dict field; anything else becomes {}."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _as_datetime(value):
    """Parse an ISO datetime (or datetime); None stays None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return None


def _hours_between(later, earlier):
    if later is None or earlier is None:
        return None
    return max(0.0, (later - earlier).total_seconds() / 3600.0)


def _is_complete_contract(evidence):
    """Complete evidence contract, v1 interpretation (see module docstring)."""
    return bool(
        evidence.get("claim")
        and evidence.get("content_fingerprint")
        and evidence.get("source")
        and evidence.get("verifier")
        and (evidence.get("proof_level") or 0) >= 1
        and evidence.get("provenance")
    )


def _gate_attrs(gate):
    return _as_dict(gate.get("attributes"))


def _gate_claims(evidence_rows):
    """Distinct non-empty claims on the gate's linked evidence."""
    return {row.get("claim") for row in evidence_rows if row.get("claim")}


def example_hash(example):
    """sha256 over the canonical JSON of an example's tensors + mask.

    Used by the restart/rebuild test: the same gate IDs rebuilt after a
    restart must hash identically.
    """
    payload = {
        "schema_version": example["schema_version"],
        "gate_ids": example["gate_ids"],
        "Xg": np.asarray(example["Xg"], dtype=np.float32).tolist(),
        "Xh": np.asarray(example["Xh"], dtype=np.float32).tolist(),
        "Xl": np.asarray(example["Xl"], dtype=np.float32).tolist(),
        "graph": [np.asarray(v, dtype=np.int64).tolist() for v in example["graph"]],
        "allowed": np.asarray(example["allowed"], dtype=bool).tolist(),
        "target": np.asarray(example["target"], dtype=np.int64).tolist(),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


class DimagFeatureBuilder:
    """Builds dimag-feature-schema v1 examples from field rows."""

    def __init__(self, *, now=None, governance=None):
        self.now = _as_datetime(now) or datetime.now(timezone.utc)
        self.governance = governance if governance is not None else GovernanceInput(now=self.now)

    # ------------------------------------------------------------ public
    def build_example(self, target_gate, gates, relations, evidence, events,
                      actions, outcomes, *, training_review=None):
        """Build one example: a neighborhood of up to 8 gates.

        The target gate sits at position 0; neighbors follow in ranked
        order (design 3). Returns a dict with Xg/Xh/Xl/graph/allowed/
        target (numpy, ranker contract) + metadata + gate_ids.
        training_review: optional {"reviewed": bool, "decision":
        "granted"|"denied"} for the training-rights field (design 2.6);
        without a reviewed grant the example is training_rights "pending".
        """
        gates_by_id = {g["id"]: g for g in gates}
        target_id = target_gate["id"]
        neighborhood = self._neighborhood(target_gate, gates_by_id, relations, events)
        gate_ids = [g["id"] if g is not None else None for g in neighborhood]
        positions = {g["id"]: i for i, g in enumerate(neighborhood) if g is not None}

        per_gate = []
        for gate in neighborhood:
            per_gate.append(
                None if gate is None else self._gate_features(
                    gate, gates_by_id, relations, evidence, events, actions, outcomes
                )
            )

        Xg = np.zeros((schema.G, schema.GDIM), dtype=np.float32)
        Xh = np.zeros((schema.G, schema.HDIM), dtype=np.float32)
        Xl = np.zeros((schema.G, schema.L, schema.LDIM), dtype=np.float32)
        allowed = np.zeros((schema.G, schema.L), dtype=bool)
        target = np.full((schema.G,), -1, dtype=np.int64)
        metadata = {
            "schema_version": schema.SCHEMA_VERSION,
            "gate_ids": gate_ids,
            "target_gate_id": target_id,
            "zone_missing": [],
            "contested": [],
            "excluded_neighbors": [],
            "relation_alias_resolutions": [],
            "dropped_edges": [],
            "label_dropped_out_of_top5": [],
            "benefit_no_history": [],
            "risk_no_history": [],
            "run_states": {},
            "evidence_states": {},
            "label_verification_state": {},
            "label_outcome": {},
            "training_rights": self._training_rights(evidence, training_review),
        }

        for pos, bundle in enumerate(per_gate):
            if bundle is None:
                continue
            Xg[pos] = bundle["Xg"]
            Xh[pos] = bundle["Xh"]
            Xl[pos] = bundle["Xl"]
            allowed[pos] = bundle["allowed"]
            target[pos] = bundle["target"]
            gid = gate_ids[pos]
            metadata["run_states"][gid] = bundle["run_state"]
            metadata["evidence_states"][gid] = bundle["evidence_state"]
            if bundle["zone_missing"]:
                metadata["zone_missing"].append(gid)
            if bundle["contested"]:
                metadata["contested"].append(gid)
            if bundle["label_dropped_out_of_top5"]:
                metadata["label_dropped_out_of_top5"].append(gid)
            metadata["benefit_no_history"].extend(bundle["benefit_no_history"])
            metadata["risk_no_history"].extend(bundle["risk_no_history"])
            metadata["relation_alias_resolutions"].extend(bundle["alias_resolutions"])
            if bundle["label_verification_state"] is not None:
                metadata["label_verification_state"][gid] = bundle["label_verification_state"]
            if bundle["label_outcome"] is not None:
                metadata["label_outcome"][gid] = bundle["label_outcome"]

        graph, dropped = self._graph_edges(neighborhood, positions, relations)
        metadata["dropped_edges"] = dropped
        metadata["excluded_neighbors"] = self._excluded_neighbors(
            target_gate, gates_by_id, relations, events, set(gate_ids)
        )

        example = {
            "schema_version": schema.SCHEMA_VERSION,
            "gate_ids": gate_ids,
            "Xg": Xg,
            "Xh": Xh,
            "Xl": Xl,
            "graph": graph,
            "allowed": allowed,
            "target": target,
            "metadata": metadata,
        }
        metadata["input_hash"] = example_hash(example)
        return example

    # -------------------------------------------------------- neighborhood
    def _neighborhood(self, target_gate, gates_by_id, relations, events):
        """Target gate at 0 + up to 7 connected gates, ranked (design 3)."""
        target_id = target_gate["id"]
        scored = {}
        for rel in relations:
            if rel.get("truth_state") == "refuted":
                continue
            src, dst = rel.get("from_entity_id"), rel.get("to_entity_id")
            if src == target_id and dst in gates_by_id and dst != target_id:
                other, rel_type = dst, rel.get("relation_type")
            elif dst == target_id and src in gates_by_id and src != target_id:
                other, rel_type = src, rel.get("relation_type")
            else:
                continue
            try:
                canonical, _ = canonical_relation_name(rel_type)
            except UnknownRelationTypeError:
                raise
            priority = 0 if canonical in ("DEPENDS_ON", "CONTRADICTS") else 1
            strength = rel.get("strength")
            strength = 0.5 if strength is None else float(strength)
            truth = TRUTH_ORDER.get(str(rel.get("truth_state") or "unknown").lower(), 4)
            recency = self._latest_event_time(other, events)
            key = (priority, -strength, truth, -(recency.timestamp() if recency else 0.0))
            if other not in scored or key < scored[other]:
                scored[other] = key
        ranked = sorted(scored, key=lambda gid: scored[gid])[: schema.G - 1]
        neighborhood = [target_gate] + [gates_by_id[gid] for gid in ranked]
        while len(neighborhood) < schema.G:
            neighborhood.append(None)
        return neighborhood

    def _excluded_neighbors(self, target_gate, gates_by_id, relations, events, included_ids):
        """Connected gates beyond the 8-slot neighborhood (never silent)."""
        target_id = target_gate["id"]
        excluded = set()
        for rel in relations:
            src, dst = rel.get("from_entity_id"), rel.get("to_entity_id")
            other = None
            if src == target_id and dst in gates_by_id and dst != target_id:
                other = dst
            elif dst == target_id and src in gates_by_id and src != target_id:
                other = src
            if other is not None and other not in included_ids:
                excluded.add(other)
        return sorted(excluded)

    # ------------------------------------------------------------ one gate
    def _gate_features(self, gate, gates_by_id, relations, evidence, events, actions, outcomes):
        gid = gate["id"]
        gate_evidence = [e for e in evidence if e.get("subject_kind") == "gate" and e.get("subject_id") == gid]
        gate_events = [ev for ev in events if ev.get("entity_id") == gid]
        gate_relations = [
            r for r in relations if r.get("from_entity_id") == gid or r.get("to_entity_id") == gid
        ]
        evaluated = self._latest_event(gate_events, "gate_evaluated")
        ev_state, contested = self._evidence_state(gate_evidence, evaluated)
        run_state = self._run_state(gate, gate_events)
        uncertainty = self._uncertainty(gate_evidence)
        progress = self._progress(evaluated)
        recency = self._recency(gate_events)
        blocked_share = self._blocked_share(gate, gate_relations, gates_by_id, evidence, events)
        zone_id = _gate_attrs(gate).get("zone_id")
        zone_missing = zone_id is None

        xg = np.zeros(schema.GDIM, dtype=np.float32)
        xg[0] = schema.clip01(uncertainty)
        xg[1] = schema.clip01(progress)
        xg[2] = schema.clip01(recency)
        xg[3] = schema.clip01(blocked_share)
        if not zone_missing and isinstance(zone_id, int) and 0 <= zone_id < schema.ZONE_COUNT:
            xg[4 + zone_id] = 1.0
        elif not zone_missing:
            zone_missing = True  # out-of-range zone id == no placed zone.
        xg[16 + schema.run_state_slot(run_state)] = 1.0
        ev_slot, contested_flag = schema.evidence_state_slot(ev_state)
        contested = contested or bool(contested_flag)
        xg[20 + ev_slot] = 1.0

        xh = self._helper_features(gate, gate_evidence, gate_events, gate_relations, actions, evidence)
        xl, allowed, target, label_info = self._lead_features(
            gate, xg, xh, gates_by_id, relations, actions, outcomes, evidence, events
        )
        return {
            "Xg": xg,
            "Xh": xh,
            "Xl": xl,
            "allowed": allowed,
            "target": target,
            "run_state": run_state,
            "evidence_state": ev_state,
            "zone_missing": zone_missing,
            "contested": contested,
            "label_dropped_out_of_top5": label_info["dropped"],
            "benefit_no_history": label_info["benefit_no_history"],
            "risk_no_history": label_info["risk_no_history"],
            "alias_resolutions": label_info["alias_resolutions"],
            "label_verification_state": label_info["verification_state"],
            "label_outcome": label_info["outcome"],
        }

    # ------------------------------------------------------- gate features
    def _uncertainty(self, gate_evidence):
        """1 - evidence coverage: complete-contract rows / claims."""
        claims = _gate_claims(gate_evidence)
        if not claims:
            return 1.0
        covered = set()
        for row in gate_evidence:
            if _is_complete_contract(row) and row.get("claim"):
                covered.add(row["claim"])
        return schema.clip01(1.0 - len(covered) / len(claims))

    def _progress(self, evaluated_event):
        """Fraction of the gate's criteria met, from gate_evaluated."""
        if evaluated_event is None:
            return 0.0
        payload = _as_dict(evaluated_event.get("payload"))
        criteria = payload.get("criteria")
        met = payload.get("met")
        if isinstance(criteria, list) and isinstance(met, list) and criteria:
            met_set = {m for m in met if isinstance(m, str)}
            done = sum(1 for c in criteria if c in met_set)
            return schema.clip01(done / len(criteria))
        total = payload.get("criteria_total")
        done = payload.get("criteria_met")
        if isinstance(total, (int, float)) and total and isinstance(done, (int, float)):
            return schema.clip01(done / total)
        return 0.0

    def _recency(self, gate_events):
        """1 / (1 + hours since the gate's latest event)."""
        latest = self._latest_event_time(None, gate_events)
        if latest is None:
            return 0.0
        hours = _hours_between(self.now, latest)
        return schema.clip01(1.0 / (1.0 + hours))

    def _blocked_share(self, gate, gate_relations, gates_by_id, evidence, events):
        """Fraction of outgoing `blocks` targets that are BLOCKED."""
        if self._evidence_state_for_gate(gate, evidence, events)[0] == "BLOCKED":
            return 1.0
        targets = []
        for rel in gate_relations:
            if rel.get("from_entity_id") != gate["id"]:
                continue
            try:
                canonical, _ = canonical_relation_name(rel.get("relation_type"))
            except UnknownRelationTypeError:
                raise
            if canonical == "CONTRADICTS":
                targets.append(rel.get("to_entity_id"))
        if not targets:
            return 0.0
        blocked = 0
        for tid in targets:
            other = gates_by_id.get(tid)
            if other is not None and self._evidence_state_for_gate(other, evidence, events)[0] == "BLOCKED":
                blocked += 1
        return schema.clip01(blocked / len(targets))

    def _evidence_state_for_gate(self, gate, evidence, events):
        gate_evidence = [e for e in evidence if e.get("subject_kind") == "gate" and e.get("subject_id") == gate["id"]]
        gate_events = [ev for ev in events if ev.get("entity_id") == gate["id"]]
        evaluated = self._latest_event(gate_events, "gate_evaluated")
        return self._evidence_state(gate_evidence, evaluated)

    def _evidence_state(self, gate_evidence, evaluated_event):
        """Computed evidence state (v1 derivation, see module docstring)."""
        if evaluated_event is not None:
            state = _as_dict(evaluated_event.get("payload")).get("state")
            if isinstance(state, str) and state.upper() in schema.EVIDENCE_STATES:
                key = state.upper()
                return key, key == "CONTESTED"
        by_claim = {}
        for row in gate_evidence:
            claim = row.get("claim")
            if claim:
                by_claim.setdefault(claim, set()).add(str(row.get("support_level") or "").lower())
        for _claim, levels in by_claim.items():
            if levels & {"supported", "tested"} and "refuted" in levels:
                return "CONTESTED", True
        if any(str(r.get("support_level") or "").lower() == "refuted" for r in gate_evidence):
            return "BLOCKED", False
        if any(
            str(r.get("support_level") or "").lower() in ("supported", "tested")
            and _is_complete_contract(r)
            for r in gate_evidence
        ):
            return "PROVEN", False
        if gate_evidence:
            return "IN_PROGRESS", False
        return "UNKNOWN", False

    def _run_state(self, gate, gate_events):
        """Run state: gate attributes first, else latest lifecycle event."""
        attrs_state = _gate_attrs(gate).get("run_state")
        if isinstance(attrs_state, str) and attrs_state.upper() in schema.RUN_STATES:
            return attrs_state.upper()
        latest = None
        latest_time = None
        for event in gate_events:
            state = LIFECYCLE_EVENT_STATES.get(event.get("event_type"))
            if state is None:
                continue
            when = _as_datetime(event.get("occurred_at"))
            if latest_time is None or (when is not None and when > latest_time):
                latest, latest_time = state, when
        return latest if latest is not None else "PAUSED"

    # ----------------------------------------------------- helper features
    def _helper_features(self, gate, gate_evidence, gate_events, gate_relations, actions, all_evidence):
        xh = np.zeros(schema.HDIM, dtype=np.float32)
        # 0 LOG EVERYTHING: events with complete records.
        if gate_events:
            complete = sum(
                1 for ev in gate_events
                if ev.get("idempotency_key") and ev.get("payload") and ev.get("source")
            )
            xh[0] = schema.clip01(complete / len(gate_events))
        # 1 SUMMARIZE AND FINALIZE THE NEXT MOVE: latest event names one.
        latest = self._latest_event(gate_events, None)
        if latest is not None:
            payload = _as_dict(latest.get("payload"))
            if any(k in payload for k in ("next_lead", "next_action", "next_step")):
                xh[1] = 1.0
        # 2 ADVANCE EVERY TIME: state advanced or a decision recorded recently.
        window_start = self.now.timestamp() - CYCLE_WINDOW_DAYS * 86400
        for ev in gate_events:
            when = _as_datetime(ev.get("occurred_at"))
            if when is not None and when.timestamp() >= window_start and ev.get("event_type") in (
                "gate_evaluated", "decision_recorded", "gate_started",
                "gate_resumed", "gate_completed",
            ):
                xh[2] = 1.0
                break
        # 3 SPEED AT PEAK: 1 - (oldest open lead queue age / 7 days).
        # Open leads are this gate's own candidates only.
        open_leads = [
            a for a in actions
            if a.get("gate_id") == gate["id"] and a.get("status") in CANDIDATE_STATUSES
        ]
        if open_leads:
            oldest = None
            for action in open_leads:
                when = _as_datetime(action.get("proposed_at"))
                if when is not None and (oldest is None or when < oldest):
                    oldest = when
            if oldest is not None:
                age_days = max(0.0, (self.now - oldest).total_seconds() / 86400.0)
                xh[3] = schema.clip01(1.0 - age_days / CYCLE_WINDOW_DAYS)
            else:
                xh[3] = 1.0
        else:
            xh[3] = 1.0
        # 4 NEVER START FROM SQUARE ONE: leads reusing prior work.
        if open_leads:
            reuse_links = {
                r.get("from_entity_id") for r in gate_relations
                if self._canonical_or_none(r.get("relation_type")) in ("DERIVED_FROM", "SUPPORTS")
            } | {
                r.get("to_entity_id") for r in gate_relations
                if self._canonical_or_none(r.get("relation_type")) in ("DERIVED_FROM", "SUPPORTS")
            }
            xh[4] = schema.clip01(1.0 if gate["id"] in reuse_links else 0.0)
        # 5 ADVANCEMENT MULTIPLIES WITH TIME: proven-evidence growth, 7d.
        proven = [r for r in gate_evidence if str(r.get("support_level") or "").lower() == "supported"]
        if proven:
            recent = 0
            for row in proven:
                when = _as_datetime(row.get("recorded_at") or row.get("observed_at"))
                if when is not None and when.timestamp() >= window_start:
                    recent += 1
            xh[5] = schema.clip01(recent / len(proven))
        # 6 VERIFY FROM EVIDENCE: claims backed by a complete contract.
        claims = _gate_claims(gate_evidence)
        if claims:
            covered = {r["claim"] for r in gate_evidence if _is_complete_contract(r) and r.get("claim")}
            xh[6] = schema.clip01(len(covered) / len(claims))
        # 7 NOTHING DORMANT: 1.0 if an event in the last 24h, 0 at 7 days.
        latest_time = self._latest_event_time(None, gate_events)
        if latest_time is not None:
            hours = _hours_between(self.now, latest_time)
            if hours <= 24:
                xh[7] = 1.0
            else:
                xh[7] = schema.clip01(1.0 - (hours - 24) / (DORMANT_DECAY_DAYS * 24 - 24))
        # 8 NEVER COPY: 1 - duplicated content_fingerprint share.
        if gate_evidence:
            fingerprints = {}
            for row in all_evidence:
                fp = row.get("content_fingerprint")
                if fp:
                    fingerprints.setdefault(fp, set()).add(row.get("subject_id"))
            duplicated = 0
            for row in gate_evidence:
                fp = row.get("content_fingerprint")
                if fp and len(fingerprints.get(fp, set()) - {gate["id"]}) > 0:
                    duplicated += 1
            xh[8] = schema.clip01(1.0 - duplicated / len(gate_evidence))
        else:
            xh[8] = 1.0
        # 9 NEVER LOSE TRACK: open leads with owner + next-check time.
        if open_leads:
            covered = 0
            for action in open_leads:
                params = _as_dict(action.get("parameters_json"))
                if params.get("owner") and params.get("next_check_at"):
                    covered += 1
            xh[9] = schema.clip01(covered / len(open_leads))
        else:
            xh[9] = 1.0
        return xh

    # ------------------------------------------------------- lead features
    def _lead_features(self, gate, xg, xh, gates_by_id, relations, actions, outcomes, evidence, events):
        gid = gate["id"]
        candidates, label_action, dropped = self._candidates(gate, actions, outcomes)
        benefit_no_history = []
        risk_no_history = []
        alias_resolutions = []
        for rel in relations:
            try:
                _name, was_alias = canonical_relation_name(rel.get("relation_type"))
            except UnknownRelationTypeError:
                raise
            if was_alias:
                alias_resolutions.append({"relation_id": rel.get("id"), "given": rel.get("relation_type")})
        xl = np.zeros((schema.L, schema.LDIM), dtype=np.float32)
        allowed = np.zeros((schema.L,), dtype=bool)
        target = -1
        label_verification_state = None
        label_outcome = None
        if candidates:
            allowed_list = allowed_mask(gate, candidates, self.governance)
            allowed[: len(candidates)] = allowed_list
            family_ids = set(gates_by_id.keys())
            supports_strength = self._mean_strength(relations, gid, ("SUPPORTS",))
            graph_strength = self._mean_strength(relations, gid, ("SUPPORTS", "DERIVED_FROM"))
            downstream = self._downstream_gates(gate, gates_by_id, relations)
            downstream_blocked = self._downstream_blocked_share(downstream, evidence, events)
            for i, action in enumerate(candidates):
                params = _as_dict(action.get("parameters_json"))
                benefit, no_hist = self._benefit(action, outcomes, family_ids)
                if no_hist:
                    benefit_no_history.append(action.get("id"))
                risk, no_hist_risk = self._risk(action, actions, family_ids)
                if no_hist_risk:
                    risk_no_history.append(action.get("id"))
                cost = self._cost(params)
                effort = self._effort(params, candidates)
                xl[i, 0] = schema.clip01(benefit)
                xl[i, 1] = schema.clip01(benefit * xh[6])
                xl[i, 2] = 1.0 if any(k in params for k in ("fallback", "alternative", "mitigation")) else 0.0
                xl[i, 3] = schema.clip01(benefit * (1.0 + supports_strength))
                xl[i, 4] = schema.clip01(cost)
                xl[i, 5] = schema.clip01(effort)
                xl[i, 6] = schema.clip01(benefit * xg[0])
                xl[i, 7] = schema.clip01(risk)
                xl[i, 8] = schema.clip01(graph_strength)
                resolution = params.get("uncertainty_resolution")
                resolution = 1.0 if resolution is None else schema.clip01(resolution)
                xl[i, 9] = schema.clip01(xg[0] * resolution)
                xl[i, 10] = 1.0 if needs_approval(action, self.governance) else 0.0
                xl[i, 11] = schema.clip01(len([d for d in downstream if self._evidence_state_for_gate(d, evidence, events)[0] == "BLOCKED"]) / 5.0)
                xl[i, 12] = 1.0 if params.get("produces_capability") or params.get("output_type") in ("capability", "artifact") else 0.0
                xl[i, 13] = schema.clip01(downstream_blocked)
                xl[i, 14] = schema.clip01(params.get("zone_cost", 0.0))
                xl[i, 15] = schema.clip01(self._evidence_yield(action, actions, outcomes))
                xl[i, 16] = 1.0 if params.get("research_question_id") else 0.0
                xl[i, 17] = schema.clip01(cost * (1.0 - xh[8]))
            if label_action is not None:
                for i, action in enumerate(candidates):
                    if action.get("id") == label_action.get("id") and bool(allowed[i]):
                        target = i
                        label_verification_state = label_action.get("verification_state")
                        outcome_row = self._outcome_for(label_action, outcomes)
                        label_outcome = outcome_row.get("outcome_type") if outcome_row else None
                        break
        return xl, allowed, target, {
            "dropped": dropped,
            "benefit_no_history": benefit_no_history,
            "risk_no_history": risk_no_history,
            "alias_resolutions": alias_resolutions,
            "verification_state": label_verification_state,
            "outcome": label_outcome,
        }

    def _candidates(self, gate, actions, outcomes):
        """Ordered candidate leads: policy first, then recency (design 2.3)."""
        gid = gate["id"]
        # An action belongs to this gate when its dict carries gate_id ==
        # gid. The Action table has no gate column; the caller resolves
        # decision_id / goal_id / opportunity_id linkage to a gate before
        # calling the builder (that join is DIMAG-004's worker, not this
        # builder). Unlinked rows belong to no gate.
        gate_actions = [a for a in actions if a.get("gate_id") == gid]
        label_action = None
        for action in gate_actions:
            if action.get("status") in EXECUTED_STATUSES and self._outcome_for(action, outcomes) is not None:
                if label_action is None or self._action_time(action) > self._action_time(label_action):
                    label_action = action
        pool = [a for a in gate_actions if a.get("status") in CANDIDATE_STATUSES]
        if label_action is not None and all(a.get("id") != label_action.get("id") for a in pool):
            pool.append(label_action)

        def sort_key(action):
            policy_rank = 0 if action.get("policy_result") == "ALLOW" else 1
            when = self._action_time(action)
            return (policy_rank, -(when.timestamp() if when else 0.0))

        pool.sort(key=sort_key)
        dropped = False
        if label_action is not None and all(a.get("id") != label_action.get("id") for a in pool[:MAX_LEADS]):
            dropped = True
        return pool[:MAX_LEADS], label_action, dropped

    def _action_time(self, action):
        for key in ("completed_at", "started_at", "approved_at", "proposed_at"):
            when = _as_datetime(action.get(key))
            if when is not None:
                return when
        return datetime(1970, 1, 1, tzinfo=timezone.utc)

    def _outcome_for(self, action, outcomes):
        for row in outcomes:
            if row.get("action_id") == action.get("id"):
                return row
        return None

    def _benefit(self, action, outcomes, family_ids):
        """Expected value from same-type Outcome history (design 2.3/0)."""
        same_type = [
            row for row in outcomes
            if row.get("action_type") == action.get("action_type")
            and row.get("success") is True
            and isinstance(row.get("actual_value"), (int, float))
        ]
        if not same_type:
            return 0.5, True
        family_max = max(
            (abs(float(r["actual_value"])) for r in outcomes if isinstance(r.get("actual_value"), (int, float))),
            default=0.0,
        )
        mean_value = sum(float(r["actual_value"]) for r in same_type) / len(same_type)
        if family_max <= 0:
            return 0.5, True
        return schema.clip01(mean_value / family_max), False

    def _risk(self, action, actions, family_ids):
        """1 - share of past same-type actions reaching VERIFIED_SUCCESS."""
        past = [a for a in actions if a.get("action_type") == action.get("action_type") and a.get("status") in EXECUTED_STATUSES]
        if not past:
            return 0.5, True
        verified = sum(1 for a in past if a.get("verification_state") == "VERIFIED_SUCCESS")
        return schema.clip01(1.0 - verified / len(past)), False

    def _cost(self, params):
        if "cost_norm" in params:
            return schema.clip01(params["cost_norm"])
        for key in ("budget_npr", "budget", "cost"):
            if isinstance(params.get(key), (int, float)):
                return schema.clip01(params[key] / COST_BUDGET_SCALE_NPR)
        for key in ("time_hours", "estimated_hours"):
            if isinstance(params.get(key), (int, float)):
                return schema.clip01(params[key] / 168.0)  # one week == 1.0.
        return 0.5

    def _effort(self, params, candidates):
        steps = params.get("steps")
        if steps is None:
            steps = params.get("calls")
        if not isinstance(steps, (int, float)):
            return 0.5
        largest = 0.0
        for action in candidates:
            other = _as_dict(action.get("parameters_json"))
            value = other.get("steps", other.get("calls"))
            if isinstance(value, (int, float)):
                largest = max(largest, float(value))
        if largest <= 0:
            return 0.5
        return schema.clip01(float(steps) / largest)

    def _mean_strength(self, relations, gate_id, types):
        strengths = []
        for rel in relations:
            if rel.get("truth_state") == "refuted":
                continue
            if rel.get("from_entity_id") != gate_id and rel.get("to_entity_id") != gate_id:
                continue
            try:
                canonical, _ = canonical_relation_name(rel.get("relation_type"))
            except UnknownRelationTypeError:
                raise
            if canonical in types:
                strength = rel.get("strength")
                strengths.append(0.5 if strength is None else float(strength))
        if not strengths:
            return 0.0
        return sum(strengths) / len(strengths)

    def _downstream_gates(self, gate, gates_by_id, relations):
        downstream = []
        for rel in relations:
            if rel.get("from_entity_id") != gate["id"]:
                continue
            try:
                canonical, _ = canonical_relation_name(rel.get("relation_type"))
            except UnknownRelationTypeError:
                raise
            if canonical in ("LEADS_TO", "ADVANCES_TO") and rel.get("to_entity_id") in gates_by_id:
                downstream.append(gates_by_id[rel["to_entity_id"]])
        return downstream

    def _downstream_blocked_share(self, downstream, evidence, events):
        if not downstream:
            return 0.0
        blocked = sum(
            1 for g in downstream
            if self._evidence_state_for_gate(g, evidence, events)[0] == "BLOCKED"
        )
        return schema.clip01(blocked / len(downstream))

    def _evidence_yield(self, action, actions, outcomes):
        """Expected new evidence rows from same-type history (v1, see docstring)."""
        past = [a for a in actions if a.get("action_type") == action.get("action_type") and a.get("status") in EXECUTED_STATUSES]
        if not past:
            return 0.0
        return schema.clip01(len(past) / 5.0)

    # ------------------------------------------------------------ graph
    def _graph_edges(self, neighborhood, positions, relations):
        """Directed edges (+ reverse forms) for the example's gates."""
        base = []
        for rel in relations:
            src, dst = rel.get("from_entity_id"), rel.get("to_entity_id")
            if src not in positions or dst not in positions:
                continue
            if rel.get("truth_state") == "refuted":
                continue
            try:
                canonical, _ = canonical_relation_name(rel.get("relation_type"))
            except UnknownRelationTypeError:
                raise
            base_id = relation_id(canonical)
            strength = rel.get("strength")
            strength = 0.5 if strength is None else float(strength)
            entry = (positions[src], positions[dst], base_id, strength, rel.get("id"))
            base.append(entry)
            if str(rel.get("direction") or "directed").lower() == "bidirectional":
                base.append((positions[dst], positions[src], base_id, strength, rel.get("id")))
        base.sort(key=lambda e: e[3])  # lowest strength first for the cap.
        dropped = []
        if len(base) > MAX_BASE_EDGES:
            dropped = [{"relation_id": e[4], "strength": e[3]} for e in base[: len(base) - MAX_BASE_EDGES]]
            base = base[len(base) - MAX_BASE_EDGES:]
        # First half: base edges (src->dst, typ). Second half: the reverse
        # forms (dst->src, typ+10), matching the ranker's make_graph
        # convention. Bidirectional relations already contributed both
        # directions above, so each direction gets its own reverse form.
        first_src = np.array([e[0] for e in base], dtype=np.int64)
        first_dst = np.array([e[1] for e in base], dtype=np.int64)
        first_typ = np.array([e[2] for e in base], dtype=np.int64)
        src = np.concatenate([first_src, first_dst])
        dst = np.concatenate([first_dst, first_src])
        typ = np.concatenate([first_typ, first_typ + 10])
        return (src, dst, typ), dropped

    def _canonical_or_none(self, relation_type):
        try:
            canonical, _ = canonical_relation_name(relation_type)
            return canonical
        except UnknownRelationTypeError:
            return None

    # ------------------------------------------------------------ misc
    def _latest_event(self, events, event_type):
        latest, latest_time = None, None
        for event in events:
            if event_type is not None and event.get("event_type") != event_type:
                continue
            when = _as_datetime(event.get("occurred_at"))
            if latest_time is None or (when is not None and when > latest_time):
                latest, latest_time = event, when
        return latest

    def _latest_event_time(self, _gate_id, events):
        latest = None
        for event in events:
            when = _as_datetime(event.get("occurred_at"))
            if when is not None and (latest is None or when > latest):
                latest = when
        return latest

    def _training_rights(self, evidence, training_review):
        """granted only with a reviewed grant; else pending (or denied)."""
        if isinstance(training_review, dict) and training_review.get("reviewed"):
            decision = training_review.get("decision")
            if decision in ("granted", "denied"):
                return decision
        return "pending"
