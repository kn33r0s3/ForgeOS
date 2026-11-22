"""DIMAG-004 field-mode seam for ForgeOS on the Mac.

The bridge between the stdlib-only worker (worker.py) and the live
ForgeOS field (backend/app/models.py + DIMAG-001 governance_mask.py).

Two pieces, both testable without a database:

  ForgeOSSeam -- the DIMAG-001 SS2.5 governance seam in field mode.
  Same verdict-dict interface as worker.FileSeam (.allowed_mask(lead_id)
  -> {"lead_id", "allowed", "reason", "checked_at"}), so execute_lead
  and run_cycle use it interchangeably with FileSeam. The verdict is
  computed from the LIVE Action row (via the worker's action_reader
  hook) + live STOP state + live DoNotContact rows + env gate flags,
  and the final authority is governance_mask.is_allowed(): if the
  reason mapping and is_allowed ever disagree, the seam fails closed
  (allowed=False, reason="seam_inconsistent").

  field_wiring(session, worker) -- builds the action_reader hook and
  the ForgeOSSeam from a live SQLAlchemy session. All app.models
  imports happen inside that function, lazily, so this module stays
  importable without SQLAlchemy -- like the rest of the dimag package.

What the field reader supplies for every Action row (the exact
ACTION_FIELDS keys -- worker._check_keys rejects missing AND unknown
fields):
  the 14 live columns (id, decision_id, action_type, objective,
  parameters_json parsed to a dict, status, policy_result,
  policy_reason, approved_at as ISO Z or None, execution_result,
  execution_error, verification_state, adapter_name) + approved_by
  None (no such column exists on the live row -- documented, not
  invented) + fixture=False, schematic=False + adapter_receipt from
  the adapter registry (default False: no registry entry means the
  adapter's receipt mechanism is unknown, and design SS7.3 parks the
  lead rather than executing speculatively) + gate_flags_open computed
  from the env flags live at read time + target_in_do_not_contact
  from the live DoNotContact rows + scope_grant_expires_at from the
  scope grants (None = no grant recorded; governance_mask treats that
  as "no grant to expire", the DIMAG-001 decided semantics) +
  executor_behavior / expected_outcome None (fixture-only keys, never
  read in field mode) + record_hash recomputed over the filled dict.

Owner STOP in the field is OpHamiRuntimeControl.safe_mode_enabled
(default True in the schema -- STOP is ON until lifted). The seam
checks BOTH the field STOP (via stop_active_fn) and the worker's own
STOP record (worker.stop_active()); either one blocks. A field STOP
that cannot be read (no control row, query error) is treated as
active -- fail closed.

RULE 1: no model, no API, no network in this module. It reads rows
and env flags and returns a verdict. It never writes a ForgeOS row.
"""

import json
import os
from datetime import timezone

from . import governance_mask
from . import worker as worker_mod


def _get(row, name, default=None):
    """Attribute-or-key read, so fake rows in tests work like ORM rows."""
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def _iso(value):
    """A datetime (naive = UTC by ForgeOS convention) or ISO string to
    UTC ISO-8601 with a Z suffix; None stays None."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    dt = value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def open_flags_now():
    """Gate flags open in the environment right now (docs/GATES.md:
    every flag defaults closed). Read live on every call, never cached
    at wiring time."""
    open_flags = set()
    for flag in governance_mask.FLAG_FOR_OPERATION.values():
        if os.environ.get(flag, "").strip().lower() in (
                "1", "true", "yes", "on"):
            open_flags.add(flag)
    return open_flags


def action_dict_from_row(row, *, open_flags=(), do_not_contact_ids=(),
                         scope_grants=None, adapter_receipt_fn=None):
    """Convert a live ForgeOS Action row (or a duck-typed fake with the
    same attributes) into the worker's exact action dict.

    ``open_flags`` is the live set of open gate flags; ``do_not_contact_ids``
    the live set of DoNotContact candidate_entity_id values;
    ``scope_grants`` maps action_id -> expiry (datetime or ISO string);
    ``adapter_receipt_fn`` maps adapter_name -> bool (does that adapter
    provide a receipt mechanism?). Defaults fail closed: no receipt
    function means adapter_receipt=False, and E7 parks the lead."""
    params = _get(row, "parameters_json")
    if isinstance(params, str):
        try:
            params = json.loads(params) if params else {}
        except ValueError:
            params = {}
    if not isinstance(params, dict):
        params = {}
    action_id = _get(row, "id")
    action_type = _get(row, "action_type")
    touched = governance_mask.action_flags_touched({
        "action_type": action_type,
        "operation": params.get("operation")})
    gate_flags_open = not (touched - set(open_flags))
    contact_id = params.get("contact_entity_id")
    target_in_dnc = (contact_id is not None
                     and contact_id in set(do_not_contact_ids))
    adapter_name = _get(row, "adapter_name")
    if adapter_receipt_fn is not None:
        adapter_receipt = bool(adapter_receipt_fn(adapter_name))
    else:
        adapter_receipt = False
    grant = (scope_grants or {}).get(action_id)
    scope_expires = _iso(grant) if grant is not None else None
    action = {
        "id": action_id,
        "decision_id": _get(row, "decision_id"),
        "action_type": action_type,
        "objective": _get(row, "objective"),
        "parameters_json": params,
        "status": _get(row, "status"),
        "policy_result": _get(row, "policy_result"),
        "policy_reason": _get(row, "policy_reason"),
        "approved_at": _iso(_get(row, "approved_at")),
        # No approved_by column exists on the live Action row; the
        # approver is whoever set approved_at through the governance
        # path. None, not invented.
        "approved_by": None,
        "execution_result": _get(row, "execution_result"),
        "execution_error": _get(row, "execution_error"),
        "verification_state": _get(row, "verification_state"),
        "adapter_name": adapter_name,
        "fixture": False,
        "schematic": False,
        "adapter_receipt": adapter_receipt,
        "gate_flags_open": gate_flags_open,
        "target_in_do_not_contact": target_in_dnc,
        "scope_grant_expires_at": scope_expires,
        "executor_behavior": None,
        "expected_outcome": None,
        "record_hash": "",
    }
    action["record_hash"] = worker_mod.record_hash(action, "record_hash")
    return action


class ForgeOSSeam:
    """The DIMAG-001 SS2.5 governance seam in field mode.

    Same interface as worker.FileSeam: .allowed_mask(lead_id) returns
    {"lead_id", "allowed", "reason", "checked_at"} and logs a
    "seam_consult" event. Reasons use the FileSeam vocabulary
    (lead_not_in_registry, no_binding, action_not_found,
    approval_missing, policy_<X>, stop_active, gate_flags_closed,
    do_not_contact, scope_grant_expired, ok) plus "seam_inconsistent"
    for a disagreement with governance_mask.is_allowed (fail closed).

    ``read_action_fn`` overrides the Action-row read (default: the
    worker's read_action, i.e. the live hook when set, else the
    fixture). ``stop_active_fn`` reads the field STOP live (default
    None: only the worker's own STOP record is checked -- the runner's
    --field wiring MUST supply the field reader; a field seam without
    one is a wiring gap, and the seam says so in its docstring, not by
    pretending the field STOP was checked)."""

    def __init__(self, worker, read_action_fn=None, stop_active_fn=None):
        self.worker = worker
        self._read_action_fn = read_action_fn
        self._stop_active_fn = stop_active_fn

    def _read_action(self, action_id):
        if self._read_action_fn is not None:
            return self._read_action_fn(self.worker, action_id)
        return worker_mod.read_action(self.worker, action_id)

    def _field_stop_active(self):
        """Field STOP (OpHamiRuntimeControl.safe_mode_enabled). An
        unreadable STOP state blocks -- fail closed, never assume."""
        if self._stop_active_fn is None:
            return False
        try:
            return bool(self._stop_active_fn())
        except Exception:
            return True

    def allowed_mask(self, lead_id):
        worker = self.worker
        registry = worker.load_registry()
        entry = registry.get(lead_id)
        verdict = {"lead_id": lead_id, "allowed": False, "reason": "",
                   "checked_at": worker.now_iso()}
        if entry is None:
            verdict["reason"] = "lead_not_in_registry"
        elif entry.get("bound_action_id") is None:
            verdict["reason"] = "no_binding"
        else:
            action = self._read_action(entry["bound_action_id"])
            if action is None:
                verdict["reason"] = "action_not_found"
            else:
                verdict.update(self._verdict_for(action))
        worker.log_event("seam_consult", lead_id=lead_id,
                         allowed=verdict["allowed"],
                         reason=verdict["reason"])
        return verdict

    def _verdict_for(self, action):
        # (a) policy, in design SS8.1 order.
        policy = action.get("policy_result")
        if policy == "ALLOW":
            pass
        elif policy == "REQUIRE_APPROVAL" and action.get("approved_at"):
            pass
        elif policy == "REQUIRE_APPROVAL":
            return {"allowed": False, "reason": "approval_missing"}
        else:
            return {"allowed": False, "reason": "policy_%s" % policy}
        # (b) owner STOP -- field STOP or the worker's own STOP record.
        if self.worker.stop_active() or self._field_stop_active():
            return {"allowed": False, "reason": "stop_active"}
        # (c) every touched gate flag must be open (computed live at
        # read time by the action reader).
        if not action.get("gate_flags_open", False):
            return {"allowed": False, "reason": "gate_flags_closed"}
        # (d) DoNotContact where contact is involved (computed live at
        # read time by the action reader from the live rows).
        if action.get("target_in_do_not_contact"):
            return {"allowed": False, "reason": "do_not_contact"}
        # (e) scope grant unexpired.
        expires = action.get("scope_grant_expires_at")
        if expires and worker_mod.parse_iso(expires) <= self.worker.now():
            return {"allowed": False, "reason": "scope_grant_expired"}
        # Final authority: DIMAG-001 governance_mask.is_allowed must
        # agree. It can only make the seam more restrictive, never
        # less: the reason mapping above already enforced (a)-(e), and
        # a disagreement means the two readings of the same state
        # differ -- fail closed rather than execute on one of them.
        gov = self._governance_input(action)
        if not governance_mask.is_allowed(action, gov):
            return {"allowed": False, "reason": "seam_inconsistent"}
        return {"allowed": True, "reason": "ok"}

    def _governance_input(self, action):
        action_id = action.get("id")
        approvals = {}
        if action.get("approved_at"):
            approvals[action_id] = True
        scope_grants = {}
        expires = action.get("scope_grant_expires_at")
        if expires:
            scope_grants[action_id] = worker_mod.parse_iso(expires)
        # do_not_contact_ids / open_flags are intentionally empty here:
        # (d) is enforced by the seam via target_in_do_not_contact
        # (the mask reads a top-level contact_entity_id key, which is
        # not in ACTION_FIELDS), and (c) via gate_flags_open (the mask
        # reads only a top-level "operation" key, which is likewise not
        # in ACTION_FIELDS). The mask's verdict is the second opinion
        # on (a), (b) and (e) only.
        return governance_mask.GovernanceInput(
            owner_stop_active=(self.worker.stop_active()
                               or self._field_stop_active()),
            do_not_contact_ids=set(),
            open_flags=set(),
            approvals=approvals,
            scope_grants=scope_grants,
            now=self.worker.now())


def field_wiring(session, worker, *, scope_grants=None,
                 adapter_receipt_fn=None):
    """Wire a live SQLAlchemy session into a worker.

    Returns (action_reader, seam). The caller sets
    ``worker.action_reader = action_reader`` and passes ``seam`` to
    run_cycle / execute_lead. All app.models imports happen here,
    lazily, so this module imports without SQLAlchemy.

    ``scope_grants`` maps action_id -> expiry (datetime or ISO string)
    from the standing-authorization envelope. The envelope's store is
    NOT yet wired -- no such source was found in ForgeOS -- so the
    default is no grants recorded, which governance_mask treats as "no
    grant to expire" (the DIMAG-001 decided semantics). Wiring the
    envelope is an open item, not a silent default: until it exists,
    an action with a grant that should have expired is not caught by
    (e) -- stated here so it is not discovered by accident.

    The session is only ever READ by this wiring (Action rows,
    OpHamiRuntimeControl, DoNotContact candidate ids). The worker
    never writes a ForgeOS row."""
    from app import models  # noqa: PLC0415 -- lazy: DB only in field mode

    def query_action(action_id):
        return session.query(models.Action).filter_by(
            id=action_id).first()

    def field_stop_active():
        row = session.query(models.OpHamiRuntimeControl).first()
        # No control row: the STOP state is unknown -- fail closed.
        return bool(row is None or row.safe_mode_enabled)

    def do_not_contact_now():
        rows = session.query(
            models.DoNotContact.candidate_entity_id).all()
        return {r[0] for r in rows}

    def action_reader(w, action_id):
        row = query_action(action_id)
        if row is None:
            return None
        return action_dict_from_row(
            row,
            open_flags=open_flags_now(),
            do_not_contact_ids=do_not_contact_now(),
            scope_grants=scope_grants,
            adapter_receipt_fn=adapter_receipt_fn)

    seam = ForgeOSSeam(worker, stop_active_fn=field_stop_active)
    return action_reader, seam
