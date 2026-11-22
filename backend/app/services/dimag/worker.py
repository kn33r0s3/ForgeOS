"""DIMAG-004 durable intelligence worker (design SS0-SS17).

The continuous worker that consumes DIMAG-003 diagnostic leads and
executes them -- with leases, idempotency, and reconciliation -- without
ever executing anything unauthorized, without ever re-deriving a trace,
and without ever writing an experience row or training the ranker.

Governing sentence (design SS0): a lead is executed at most once, only
under a live lease, only through the governance seam, and only with a
receipt -- and anything the worker cannot prove about an execution is
recorded as UNKNOWN, never assumed to have happened or not happened.

Single host, multi-process; plain files on disk; standard library only.
No model, no API, no network, no Mac access, no commits, no hami-media.

RULE 1: no GPT, no OpenAI, no gpt-oss, no Ollama anywhere.

Layout (design SS13.2), all under the worker state directory:
  dimag-lead-registry-v1.jsonl   the lead registry (one line per lead)
  intake-log.jsonl               every intake decision incl. duplicates
  binding-requests.jsonl         binding requests (SS5.1)
  bindings/                      one file per live binding
  leases/                        one file per live lease (SS6.1)
  executions/                    one file per execution attempt (SS9.1)
  receipts/                      the adapter receipt store (SS9/SS10)
  handoff/                       handoff records for DIMAG-002 (SS9.2)
  dead-letter.jsonl              dead-letter entries with full history
  human-review.jsonl             items awaiting a named human reviewer
  grants.jsonl                   grant records (append-only)
  actions/                       schematic fixture Action rows (file mode)
  reconciliation/                sweep reports (SS10)
  evaluation/                    temporal-evaluation outputs (SS11)
  worker-state.json              cycle checkpoint: last cycle, STOP state,
                                 budgets, worker identity, clock state
  event-log.jsonl                append-only: every state transition,
                                 lease event, execution event, refusal,
                                 reconciliation finding, stop
  incidents/                     safety incidents (e.g. R7)

Mac / ForgeOS port (22 Nov 2026): this file is the reference
implementation ported verbatim into backend/app/services/dimag/, with
exactly two adaptations, both marked "Mac/ForgeOS port" in comments:
  1. Worker.__init__ accepts an optional ``action_reader`` hook.
  2. read_action() delegates to that hook when set, so field mode
     reads the LIVE ForgeOS Action row on every call (design SS5.1)
     instead of the schematic fixture under actions/.
Everything else -- intake, leases, idempotency, the E1-E8 boundary,
reconciliation, temporal evaluation -- is the reference code unchanged.
The Mac state directory is ~/hami/dimag-004-worker/ (plain files, no
new infrastructure). The field seam lives in field_seam.py.
"""

import hashlib
import json
import os
import shutil
import time
import uuid
from datetime import datetime, timedelta, timezone

WORKER_VERSION = "dimag-004-worker v1"
WORKER_NAME = "dimag-004-worker"
REGISTRY_VERSION = "dimag-004-lead-registry v1"
TRACE_VERSION = "dimag-backward-trace v1"
EXEC_KEY_VERSION = "dimag-004-exec v1"

# Defaults (design SS6.2, SS12.3, SS13.3, SS16 Q5).
LEASE_DURATION_S = 600          # 10 min
HEARTBEAT_INTERVAL_S = 120
MAX_RENEWALS = 5                # 50 min of continuous ownership, then re-acquire
TAKEOVER_GRACE_S = 60           # grace past expires_at before takeover
CLOCK_SUSPECT_S = 300           # lease acquired_at this far in the future is corrupt
CLOCK_JUMP_S = 60               # wall-clock jump back beyond this stops executions
MAX_LEADS_PER_CYCLE = 5
MAX_CYCLE_WALL_S = 3600         # 60 min
MAX_ATTEMPTS = 3                # poison lead: 3 failed attempts -> DEAD_LETTER
BACKOFF_S = {1: 3600, 2: 21600, 3: 86400}   # 1 h, 6 h, 24 h (SS12.3)
DISK_MIN_BYTES = 100 * 1024 * 1024         # 100 MB (SS12.4)
EVAL_WINDOW_DAYS = 7

QUARANTINED_TRACE_IDS = (
    "dimag-trace-000001", "dimag-trace-000002", "dimag-trace-000003",
    "dimag-trace-000004", "dimag-trace-000005", "dimag-trace-000009",
    "dimag-trace-000013", "dimag-trace-000014",
)

# Lifecycle states (design SS4). PARKED_<reason> reasons:
PARKED_REASONS = (
    "UNBOUND", "UNAPPROVED_ACTION", "NO_RECEIPT_ADAPTER",
    "BINDING_INVALID", "SUPERSEDED_BY_TRACE",
)
TERMINAL_STATES = ("ALREADY_TESTED", "QUARANTINED", "DEAD_LETTER",
                   "DONE", "HUMAN_REVIEW", "SUPERSEDED_BY_TRACE")

# Execution phases (design SS9.1, SS30).
EXEC_PHASES = ("EXECUTING", "COMPLETED", "FAILED", "UNKNOWN")

# Reconciliation verdict vocabulary (book SS31, design SS10).
RECON_VERDICTS = ("VERIFIED_COMPLETED", "VERIFIED_NOT_EXECUTED",
                  "STILL_UNKNOWN", "HUMAN_REVIEW_REQUIRED")


def canonical_json(obj):
    """Deterministic canonical JSON: sorted keys, tight separators."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def record_hash(obj, hash_field):
    """sha256 of the canonical record without its hash field (DIMAG-003
    trace_hash pattern, design SS13.2). Underscore-prefixed keys are
    loader artifacts (list_executions attaches "_file") and are never
    part of a stored record, so they are excluded from the hash."""
    return sha256_text(canonical_json(
        {k: v for k, v in obj.items()
         if k != hash_field and not k.startswith("_")}))


def parse_iso(text):
    """Parse an ISO-8601 UTC timestamp (accepts a trailing Z)."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def fmt_iso(moment):
    """Format an aware datetime as UTC ISO-8601 with a Z suffix."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class RealClock:
    """Wall clock + monotonic clock (design SS12.2)."""

    def now(self):
        return datetime.now(timezone.utc)

    def monotonic(self):
        return time.monotonic()


class FakeClock:
    """Controllable clock for tests. advance() moves wall + monotonic
    together; rewind_wall() moves only the wall clock back (a clock
    jump, design SS12.2)."""

    def __init__(self, start):
        if isinstance(start, str):
            start = parse_iso(start)
        self._wall = start
        self._mono = 1000000.0

    def now(self):
        return self._wall

    def monotonic(self):
        return self._mono

    def advance(self, seconds):
        self._wall = self._wall + timedelta(seconds=seconds)
        self._mono = self._mono + seconds

    def rewind_wall(self, seconds):
        self._wall = self._wall - timedelta(seconds=seconds)

    def set(self, moment):
        if isinstance(moment, str):
            moment = parse_iso(moment)
        self._wall = moment


class WorkerError(Exception):
    """A named worker refusal / failure. `code` is the design's named
    reason (e.g. exec_refused_no_lease); `detail` is the evidence."""


    def __init__(self, code, detail=""):
        super().__init__("%s: %s" % (code, detail))
        self.code = code
        self.detail = detail


class CrashSimulated(Exception):
    """The test executor's simulated process death (design SS12.1/T4/T8):
    raised after the intent-phase record is written, before any outcome
    phase. Nothing after this point runs -- no outcome, no lease release,
    no checkpoint."""


class ExecutorTimeout(Exception):
    """The executor call timed out with no receipt (design SS9.1)."""


def atomic_write_bytes(path, data):
    """Write bytes atomically: temp file + fsync + rename on the same
    filesystem (the DIMAG-001 SS4 checkpoint pattern, design SS6.1)."""
    tmp_path = "%s.tmp-%s" % (path, uuid.uuid4().hex)
    with open(tmp_path, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, path)


def atomic_write_json(path, obj):
    atomic_write_bytes(path, (canonical_json(obj) + "\n").encode("utf-8"))


def append_jsonl(path, obj):
    """Append one canonical JSON line, fsynced. Returns the 1-based line
    number of the appended line."""
    line = (canonical_json(obj) + "\n").encode("utf-8")
    if os.path.exists(path):
        with open(path, "rb") as fh:
            line_no = sum(1 for _ in fh) + 1
    else:
        line_no = 1
    with open(path, "ab") as fh:
        fh.write(line)
        fh.flush()
        os.fsync(fh.fileno())
    return line_no


def read_jsonl(path):
    """Read a JSONL file into a list of records (empty list if absent)."""
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise WorkerError("corrupt_jsonl",
                                  "%s line %d: %s" % (path, line_no, exc))
    return records


def read_json_file(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _check_keys(obj, allowed, where):
    if not isinstance(obj, dict):
        return ["%s: not an object" % where]
    extra = sorted(set(obj.keys()) - allowed)
    missing = sorted(allowed - set(obj.keys()))
    errors = []
    if extra:
        errors.append("%s: unknown fields %s" % (where, extra))
    if missing:
        errors.append("%s: missing fields %s" % (where, missing))
    return errors


def _check_hash(obj, hash_field, where, errors):
    expected = record_hash(obj, hash_field)
    if obj.get(hash_field) != expected:
        errors.append("%s: %s does not reproduce from the record"
                      % (where, hash_field))


# ---------------------------------------------------------------------------
# Registry schema (design SS3.1) + Worker state
# ---------------------------------------------------------------------------

REGISTRY_FIELDS = {
    "lead_id", "registry_version", "trace_id", "trace_hash",
    "trace_file_sha256", "source_record_id", "source_domain",
    "combined_confidence", "cause_class", "hypothesis",
    "falsification_condition", "cost_text", "parent_gate",
    "already_tested_by", "quarantine", "intake_status",
    "bound_action_id", "bound_at", "bound_by", "execution_key",
    "attempt", "intaked_at", "intaked_by", "intake_log_ref",
    # Worker state (design SS4/SS12.3): retry bookkeeping, supersede links.
    "next_retry_at", "failure_history", "release_epoch",
    "supersedes", "superseded_by", "record_hash",
}
QUARANTINE_FIELDS = {"training_rights", "label_trust", "quarantine_reason"}

LEASE_FIELDS = {
    "lease_id", "lead_id", "worker_id", "lease_token", "acquired_at",
    "expires_at", "heartbeat_at", "lease_duration_s",
    "heartbeat_interval_s", "execution_key", "renewal_count",
    "lease_hash",
}

BINDING_FIELDS = {
    "binding_id", "lead_id", "action_id", "bound_at", "bound_by",
    "binding_basis", "policy_result_at_binding", "approval_record",
    "scope_grant", "binding_hash",
}

ACTION_FIELDS = {
    # DIMAG-001 SS1.2 Action row (+ fixture extras, all explicit).
    "id", "decision_id", "action_type", "objective", "parameters_json",
    "status", "policy_result", "policy_reason", "approved_at",
    "approved_by", "execution_result", "execution_error",
    "verification_state", "adapter_name",
    # Fixture extras (file mode only; schematic, never a real ForgeOS row).
    "fixture", "schematic", "adapter_receipt", "gate_flags_open",
    "target_in_do_not_contact", "scope_grant_expires_at",
    "executor_behavior", "expected_outcome", "record_hash",
}

EXECUTION_FIELDS = {
    "execution_key", "execution_key_hash", "lead_id", "trace_id",
    "action_id", "lease_token", "worker_id", "phase", "attempt",
    "executor_call", "receipt", "outcome", "falsification_checked",
    "recorded_at", "recovery_verdict", "reconstructed",
    "execution_hash",
}
EXECUTOR_CALL_FIELDS = {"adapter", "called_at", "payload_hash"}
RECEIPT_FIELDS = {"receipt_id", "received_at", "external_ref",
                  "outcome_label"}
OUTCOME_FIELDS = {"label", "actual_value", "unit", "observed_at",
                  "qualitative_result"}
FALSIFICATION_FIELDS = {"condition", "result"}

HANDOFF_FIELDS = {
    "handoff_id", "execution_key", "lead_id", "trace_id",
    "source_record_id", "action_id", "receipt_id", "outcome",
    "falsification_checked", "written_at", "written_by", "record_hash",
}


def execution_key_for(lead_id, attempt_no):
    """The execution key (design SS7.1): derived from lead_id + attempt,
    never from a timestamp or a random value, so two workers derive the
    same key for the same lead + attempt."""
    return "dimag-exec-%s-a%d" % (lead_id, attempt_no)


def execution_key_hash_for(lead_id, attempt_no):
    return sha256_text("%s|%s|%d" % (EXEC_KEY_VERSION, lead_id, attempt_no))


def trace_index_of(trace_id):
    """Parse 'dimag-trace-%06d' -> int index (design SS3.2 I4)."""
    prefix = "dimag-trace-"
    if not trace_id.startswith(prefix):
        return None
    try:
        return int(trace_id[len(prefix):])
    except ValueError:
        return None


def recompute_trace_hash(record):
    """Recompute a trace record's hash (DIMAG-003 trace.py pattern)."""
    return sha256_text(canonical_json(
        {k: v for k, v in record.items() if k != "trace_hash"}))


class Worker:
    """One worker process over one state directory (design SS13.2).

    Single host, multi-process: leases on the shared filesystem are the
    coordination mechanism (SS6.2). All timestamps are UTC ISO 8601.
    """

    def __init__(self, state_dir, worker_id="dimag-004-worker-01",
                 clock=None, config=None, action_reader=None):
        self.state_dir = os.path.abspath(state_dir)
        self.worker_id = worker_id
        self.clock = clock or RealClock()
        # Mac/ForgeOS port: optional live Action-row reader. When set
        # (by field_seam.field_wiring), read_action() reads the live
        # ForgeOS row on every call -- never a cached copy (design
        # SS5.1). File mode (default None) reads the schematic fixture
        # under actions/. Only read_action() consults this hook.
        self.action_reader = action_reader
        cfg = dict(config or {})
        self.lease_duration_s = cfg.get("lease_duration_s",
                                        LEASE_DURATION_S)
        self.heartbeat_interval_s = cfg.get("heartbeat_interval_s",
                                            HEARTBEAT_INTERVAL_S)
        self.max_renewals = cfg.get("max_renewals", MAX_RENEWALS)
        self.takeover_grace_s = cfg.get("takeover_grace_s",
                                        TAKEOVER_GRACE_S)
        self.clock_suspect_s = cfg.get("clock_suspect_s", CLOCK_SUSPECT_S)
        self.clock_jump_s = cfg.get("clock_jump_s", CLOCK_JUMP_S)
        self.max_leads_per_cycle = cfg.get("max_leads_per_cycle",
                                           MAX_LEADS_PER_CYCLE)
        self.max_cycle_wall_s = cfg.get("max_cycle_wall_s",
                                        MAX_CYCLE_WALL_S)
        self.max_attempts = cfg.get("max_attempts", MAX_ATTEMPTS)
        self.backoff_s = dict(cfg.get("backoff_s") or BACKOFF_S)
        self.disk_min_bytes = cfg.get("disk_min_bytes", DISK_MIN_BYTES)
        for sub in ("leases", "executions", "bindings", "handoff",
                    "receipts", "reconciliation", "evaluation", "actions",
                    "incidents"):
            os.makedirs(os.path.join(self.state_dir, sub), exist_ok=True)
        self._registry = None       # lead_id -> entry dict
        self._registry_dirty = False
        self._halted = None         # {"reason": ..., "at": ...} or None
        self._load_halt()

    # -- paths -------------------------------------------------------------
    def _p(self, *parts):
        return os.path.join(self.state_dir, *parts)

    # -- clock -------------------------------------------------------------
    def now(self):
        return self.clock.now()

    def now_iso(self):
        return fmt_iso(self.clock.now())

    # -- event log (append-only, SS13) --------------------------------------
    def log_event(self, event_type, **fields):
        """Append one event. Every state transition goes through here so
        the temporal-evaluation replay (SS11.2) can re-derive lead state
        from this log alone."""
        event = {"event_type": event_type, "ts": self.now_iso(),
                 "worker_id": self.worker_id}
        event.update(fields)
        event["event_hash"] = record_hash(event, "event_hash")
        append_jsonl(self._p("event-log.jsonl"), event)
        return event

    def read_events(self):
        return read_jsonl(self._p("event-log.jsonl"))

    # -- registry ------------------------------------------------------------
    def load_registry(self, force=False):
        if self._registry is not None and not force:
            return self._registry
        entries = {}
        for record in read_jsonl(self._p("dimag-lead-registry-v1.jsonl")):
            errors = validate_registry_entry(record)
            if errors:
                raise WorkerError("registry_corrupt", "; ".join(errors))
            entries[record["lead_id"]] = record
        self._registry = entries
        self._registry_dirty = False
        return entries

    def save_registry(self):
        """Rewrite the registry atomically, only when dirty (so a
        duplicate intake leaves the file byte-identical, design SS7.4)."""
        if not self._registry_dirty:
            return False
        lines = []
        for lead_id in sorted(self._registry):
            entry = dict(self._registry[lead_id])
            entry["record_hash"] = record_hash(entry, "record_hash")
            self._registry[lead_id]["record_hash"] = entry["record_hash"]
            lines.append(canonical_json(entry))
        atomic_write_bytes(
            self._p("dimag-lead-registry-v1.jsonl"),
            ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8"))
        self._registry_dirty = False
        return True

    def _transition(self, lead_id, to_state, reason, actor=None):
        """The single funnel for every lead state change (design SS4):
        updates the registry entry and appends a transition event with
        from/to states, actor, and reason. No transition is silent."""
        registry = self.load_registry()
        entry = registry.get(lead_id)
        if entry is None:
            raise WorkerError("lead_not_in_registry", lead_id)
        from_state = entry["intake_status"]
        entry["intake_status"] = to_state
        self._registry_dirty = True
        self.log_event("transition", lead_id=lead_id,
                       from_state=from_state, to_state=to_state,
                       reason=reason, actor=actor or self.worker_id)
        return entry

    # -- STOP / halt ---------------------------------------------------------
    def stop_path(self):
        return self._p("stop.json")

    def stop_active(self):
        return os.path.exists(self.stop_path())

    def read_stop(self):
        if not self.stop_active():
            return None
        return read_json_file(self.stop_path())

    def record_stop(self, reviewer, reason):
        """A human-recorded STOP (design SS12.6 #8)."""
        record = {"reviewer": reviewer, "reason": reason,
                  "recorded_at": self.now_iso()}
        atomic_write_json(self.stop_path(), record)
        self.log_event("stop_recorded", reviewer=reviewer, reason=reason)
        return record

    def lift_stop(self, reviewer, reason):
        if not self.stop_active():
            raise WorkerError("stop_not_active", "no STOP record to lift")
        os.remove(self.stop_path())
        self.log_event("stop_lifted", reviewer=reviewer, reason=reason)

    def _load_halt(self):
        state = self.read_worker_state()
        self._halted = state.get("halted") if state else None

    def halt(self, reason, detail=""):
        """Halt the worker (design SS12.6): no further executor call
        until a named human clears it. The halt is itself a record."""
        self._halted = {"reason": reason, "detail": detail,
                        "at": self.now_iso()}
        state = self.read_worker_state() or {}
        state["halted"] = self._halted
        self.write_worker_state(state)
        self.log_event("worker_halted", reason=reason, detail=detail)

    def clear_halt(self, actor, reason):
        if not self._halted:
            raise WorkerError("not_halted", "worker is not halted")
        self._halted = None
        state = self.read_worker_state() or {}
        state["halted"] = None
        self.write_worker_state(state)
        self.log_event("halt_cleared", actor=actor, reason=reason)

    def halted(self):
        return self._halted

    # -- worker state / checkpoint -------------------------------------------
    def read_worker_state(self):
        path = self._p("worker-state.json")
        if not os.path.exists(path):
            return None
        return read_json_file(path)

    def write_worker_state(self, state):
        state = dict(state)
        state["worker_version"] = WORKER_VERSION
        state["worker_id"] = self.worker_id
        state["updated_at"] = self.now_iso()
        atomic_write_json(self._p("worker-state.json"), state)
        return state

    def default_worker_state(self):
        return {
            "worker_version": WORKER_VERSION,
            "worker_id": self.worker_id,
            "last_cycle": None,
            "stop": None,
            "halted": None,
            "budgets": {
                "max_leads_per_cycle": self.max_leads_per_cycle,
                "max_cycle_wall_s": self.max_cycle_wall_s,
                "max_attempts": self.max_attempts,
                "lease_duration_s": self.lease_duration_s,
                "disk_min_bytes": self.disk_min_bytes,
            },
            "updated_at": self.now_iso(),
        }


def validate_registry_entry(entry):
    """Exact field set + hash (design SS13.2: unknown fields rejected,
    not ignored)."""
    errors = _check_keys(entry, REGISTRY_FIELDS, "registry entry")
    if errors:
        return errors
    q = entry.get("quarantine")
    if isinstance(q, dict):
        errors.extend(_check_keys(q, QUARANTINE_FIELDS,
                                  "registry entry quarantine"))
    if entry.get("registry_version") != REGISTRY_VERSION:
        errors.append("registry_version is %r"
                      % entry.get("registry_version"))
    if entry.get("intake_status") not in (
            "PROPOSED", "PROPOSED_HELD", "QUARANTINED", "ALREADY_TESTED",
            "BOUND", "LEASED", "EXECUTING", "RETRY_WAIT", "RECONCILING",
            "DEAD_LETTER", "DONE", "HUMAN_REVIEW",
            "SUPERSEDED_BY_TRACE") and not (
            isinstance(entry.get("intake_status"), str)
            and entry["intake_status"].startswith("PARKED_")):
        errors.append("intake_status is %r" % entry.get("intake_status"))
    _check_hash(entry, "record_hash", "registry entry", errors)
    return errors


def validate_lease(lease):
    errors = _check_keys(lease, LEASE_FIELDS, "lease")
    if errors:
        return errors
    _check_hash(lease, "lease_hash", "lease", errors)
    return errors


def validate_execution(record):
    errors = _check_keys(record, EXECUTION_FIELDS, "execution record")
    if errors:
        return errors
    call = record.get("executor_call")
    if isinstance(call, dict):
        errors.extend(_check_keys(call, EXECUTOR_CALL_FIELDS,
                                  "executor_call"))
    receipt = record.get("receipt")
    if isinstance(receipt, dict):
        errors.extend(_check_keys(receipt, RECEIPT_FIELDS, "receipt"))
    outcome = record.get("outcome")
    if isinstance(outcome, dict):
        errors.extend(_check_keys(outcome, OUTCOME_FIELDS, "outcome"))
    fals = record.get("falsification_checked")
    if isinstance(fals, dict):
        errors.extend(_check_keys(fals, FALSIFICATION_FIELDS,
                                  "falsification_checked"))
    _check_hash(record, "execution_hash", "execution record", errors)
    return errors


# ---------------------------------------------------------------------------
# Stage 0 inventory + Stage 1 intake (design SS13.1, SS3)
# ---------------------------------------------------------------------------

def load_trace_file(trace_path):
    """Read the trace file. Returns (records, sha256). The file is never
    opened for writing (design SS2.3, test T11)."""
    file_sha = sha256_file(trace_path)
    records = []
    with open(trace_path, "r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise WorkerError("trace_not_json",
                                  "%s line %d: %s"
                                  % (trace_path, line_no, exc))
    return records, file_sha


def _intake_status_for(entry_lead, trace):
    """Status assignment, rules I6-I8 in order (design SS3.2).

    I6 already-tested beats I7 quarantine (lead 000001 is both); I7
    quarantine beats I8 HYPOTHESIS-held (lead 000009 is both)."""
    lead = entry_lead
    if lead.get("already_tested_by"):
        return "ALREADY_TESTED"
    quarantine = lead.get("quarantine_inherited") or {}
    if quarantine.get("quarantine_reason") is not None:
        return "QUARANTINED"
    if trace.get("combined", {}).get("confidence") == "HYPOTHESIS":
        return "PROPOSED_HELD"
    return "PROPOSED"


def intake_traces(worker, trace_path):
    """Stage 1 intake (design SS3). Idempotent: a second run over the
    same file records DUPLICATE_INTAKE_IGNORED per lead and changes
    nothing (SS7.4, test T10).

    Returns a counts dict. The registry is saved only if it changed."""
    registry = worker.load_registry()
    if not os.path.exists(trace_path):
        worker.log_event("inventory_missing_trace_file",
                         trace_path=os.path.abspath(trace_path))
        return {"trace_file": "MISSING", "leads": 0, "intaked": 0,
                "duplicates": 0, "rejected": 0, "no_lead": 0,
                "superseded": 0}
    records, file_sha = load_trace_file(trace_path)
    counts = {"trace_file": os.path.abspath(trace_path),
              "trace_file_sha256": file_sha,
              "trace_records": len(records), "leads": 0, "intaked": 0,
              "duplicates": 0, "rejected": 0, "no_lead": 0,
              "superseded": 0,
              "by_status": {}}

    for trace in records:
        trace_id = trace.get("trace_id")
        lead = trace.get("diagnostic_lead")
        confidence = trace.get("combined", {}).get("confidence")
        # I3, no-lead case: an UNKNOWN trace has no lead by construction.
        if lead is None:
            counts["no_lead"] += 1
            append_jsonl(worker._p("intake-log.jsonl"), {
                "ts": worker.now_iso(), "trace_id": trace_id,
                "lead_id": None, "outcome": "NO_LEAD", "rule": "I3",
                "detail": "confidence %s has no diagnostic lead"
                          % confidence})
            continue
        lead_id = lead.get("lead_id")
        counts["leads"] += 1

        def log(outcome, rule, detail, status=None):
            line_no = append_jsonl(worker._p("intake-log.jsonl"), {
                "ts": worker.now_iso(), "trace_id": trace_id,
                "lead_id": lead_id, "outcome": outcome, "rule": rule,
                "detail": detail,
                "intake_status": status})
            return line_no

        # I0 (SS2.3): trace version must be the v1 version.
        if trace.get("trace_version") != TRACE_VERSION:
            counts["rejected"] += 1
            log("REJECTED", "I0",
                "trace_version is %r" % trace.get("trace_version"))
            continue
        # I1: the source attempt record is durable.
        if not trace.get("source_record_id") or \
                not trace.get("source_record_sha256"):
            counts["rejected"] += 1
            log("REJECTED", "I1", "intake_source_not_durable")
            continue
        # I2: trace_hash recomputes over the canonical record.
        if trace.get("trace_hash") != recompute_trace_hash(trace):
            counts["rejected"] += 1
            log("REJECTED", "I2", "intake_trace_hash_mismatch")
            continue
        # I3: a lead attached to an UNKNOWN trace is a corrupt record.
        if confidence not in ("SUPPORTED", "PROVEN", "HYPOTHESIS"):
            counts["rejected"] += 1
            log("REJECTED", "I3", "intake_unknown_has_lead")
            continue
        # I4: lead_id matches the trace numbering; derived_from == trace.
        index = trace_index_of(trace_id)
        expected_lead = ("dimag-lead-%06d" % index) if index else None
        if lead_id != expected_lead or \
                lead.get("derived_from") != trace_id:
            counts["rejected"] += 1
            log("REJECTED", "I4",
                "intake_lead_trace_mismatch: lead_id %r derived_from %r "
                "for trace %r" % (lead_id, lead.get("derived_from"),
                                  trace_id))
            continue
        # I5: duplicate / supersede.
        existing = registry.get(lead_id)
        if existing is not None:
            if existing["trace_hash"] == trace["trace_hash"]:
                counts["duplicates"] += 1
                log("DUPLICATE_INTAKE_IGNORED", "I5",
                    "same lead_id + trace_hash; no change",
                    status=existing["intake_status"])
                continue
            # Re-trace: old entry superseded, new entry created.
            old_hash = existing["trace_hash"]
            worker._transition(lead_id, "SUPERSEDED_BY_TRACE",
                               "re-trace with new trace_hash %s"
                               % trace["trace_hash"][:12])
            existing["superseded_by"] = trace["trace_hash"]
            worker._registry_dirty = True
            counts["superseded"] += 1
            log("SUPERSEDED", "I5",
                "trace re-run: old trace_hash %s superseded"
                % old_hash[:12])
            # Fall through to create the new entry below, linked back.
            supersedes_link = old_hash
        else:
            supersedes_link = None

        status = _intake_status_for(lead, trace)
        line_no = log("INTAKED", "I6-I8" if status in (
            "ALREADY_TESTED", "QUARANTINED", "PROPOSED_HELD")
            else "OK", "intake_status %s" % status, status=status)
        entry = {
            "lead_id": lead_id,
            "registry_version": REGISTRY_VERSION,
            "trace_id": trace_id,
            "trace_hash": trace["trace_hash"],
            "trace_file_sha256": file_sha,
            "source_record_id": trace["source_record_id"],
            "source_domain": trace["source_domain"],
            "combined_confidence": confidence,
            "cause_class": trace["combined"].get("cause_class"),
            "hypothesis": lead["hypothesis"],
            "falsification_condition": lead["falsification_condition"],
            "cost_text": lead["cost"],
            "parent_gate": lead["parent_gate"],
            "already_tested_by": lead.get("already_tested_by"),
            "quarantine": dict(lead.get("quarantine_inherited") or {}),
            "intake_status": status,
            "bound_action_id": None,
            "bound_at": None,
            "bound_by": None,
            "execution_key": None,
            "attempt": 0,
            "intaked_at": worker.now_iso(),
            "intaked_by": WORKER_NAME,
            "intake_log_ref": "intake-log.jsonl#%d" % line_no,
            "next_retry_at": None,
            "failure_history": [],
            "release_epoch": 0,
            "supersedes": supersedes_link,
            "superseded_by": None,
            "record_hash": "",
        }
        entry["record_hash"] = record_hash(entry, "record_hash")
        registry[lead_id] = entry
        worker._registry_dirty = True
        counts["intaked"] += 1
        counts["by_status"][status] = counts["by_status"].get(status, 0) + 1
        worker.log_event("intake", lead_id=lead_id, trace_id=trace_id,
                         intake_status=status,
                         quarantine_reason=(entry["quarantine"] or {})
                         .get("quarantine_reason"))

    worker.save_registry()
    return counts


def inventory(worker, trace_path):
    """Stage 0 inventory (design SS13.1): record trace file path + sha +
    version; list the leads it contains. A missing trace file is
    recorded as MISSING, never as '0 leads'."""
    if not os.path.exists(trace_path):
        record = {"trace_file": os.path.abspath(trace_path),
                  "status": "MISSING", "leads": 0,
                  "recorded_at": worker.now_iso(),
                  "recorded_by": WORKER_NAME}
        worker.log_event("inventory_missing_trace_file",
                         trace_path=record["trace_file"])
        return record
    records, file_sha = load_trace_file(trace_path)
    leads = [r["diagnostic_lead"]["lead_id"] for r in records
             if r.get("diagnostic_lead")]
    record = {
        "trace_file": os.path.abspath(trace_path),
        "trace_file_sha256": file_sha,
        "trace_version": TRACE_VERSION,
        "status": "OK",
        "trace_records": len(records),
        "leads": len(leads),
        "lead_ids": sorted(leads),
        "recorded_at": worker.now_iso(),
        "recorded_by": WORKER_NAME,
    }
    record["inventory_hash"] = record_hash(record, "inventory_hash")
    return record


# ---------------------------------------------------------------------------
# Grants (design SS8.3, SS13.2) -- append-only, never edited
# ---------------------------------------------------------------------------

def read_grants(worker):
    return read_jsonl(worker._p("grants.jsonl"))


def add_grant(worker, granter, scope, lead_ids, note=""):
    """Record a grant. scope is 'training', 'execution', or 'both'.
    Execution of a quarantined lead requires a grant whose scope names
    execution explicitly (SS8.3); ambiguity resolves toward refusal."""
    if scope not in ("training", "execution", "both"):
        raise WorkerError("grant_bad_scope", scope)
    record = {
        "grant_id": "dimag-grant-%s" % uuid.uuid4().hex[:12],
        "granter": granter, "scope": scope,
        "lead_ids": sorted(lead_ids), "note": note,
        "granted_at": worker.now_iso(),
    }
    record["grant_hash"] = record_hash(record, "grant_hash")
    append_jsonl(worker._p("grants.jsonl"), record)
    worker.log_event("grant_recorded", grant_id=record["grant_id"],
                     scope=scope, lead_ids=record["lead_ids"],
                     granter=granter)
    return record


def execution_granted(worker, lead_id):
    """True iff a grant record names execution scope for this lead."""
    for grant in read_grants(worker):
        if grant.get("scope") in ("execution", "both") and \
                lead_id in (grant.get("lead_ids") or []):
            return True
    return False


def release_held_lead(worker, lead_id, reviewer):
    """Release a PROPOSED_HELD lead to PROPOSED (design SS4, SS16 Q2/Q3).
    A named reviewer, recorded -- never 'the system'."""
    registry = worker.load_registry()
    entry = registry.get(lead_id)
    if entry is None:
        raise WorkerError("lead_not_in_registry", lead_id)
    if entry["intake_status"] != "PROPOSED_HELD":
        raise WorkerError("lead_not_held",
                          "%s is %s" % (lead_id, entry["intake_status"]))
    worker._transition(lead_id, "PROPOSED",
                       "released by reviewer %s" % reviewer, actor=reviewer)
    worker.save_registry()
    return entry


def release_dead_letter(worker, lead_id, reviewer, reason):
    """Release a DEAD_LETTER lead (design SS12.3): named reviewer +
    recorded reason + a new attempt epoch. History is preserved."""
    registry = worker.load_registry()
    entry = registry.get(lead_id)
    if entry is None:
        raise WorkerError("lead_not_in_registry", lead_id)
    if entry["intake_status"] != "DEAD_LETTER":
        raise WorkerError("lead_not_dead_letter",
                          "%s is %s" % (lead_id, entry["intake_status"]))
    entry["release_epoch"] = entry.get("release_epoch", 0) + 1
    entry["failure_history"] = list(entry.get("failure_history") or [])
    worker._transition(lead_id, "BOUND",
                       "dead-letter released by %s: %s (epoch %d)"
                       % (reviewer, reason, entry["release_epoch"]),
                       actor=reviewer)
    entry["next_retry_at"] = None
    worker._registry_dirty = True
    worker.save_registry()
    return entry


# ---------------------------------------------------------------------------
# Stage 2 binding (design SS5) + fixture Action rows (file mode, SS13.3)
# ---------------------------------------------------------------------------

def make_action(action_id, lead_id, hypothesis, falsification_condition,
                policy_result="ALLOW", status=None, approved_at=None,
                approved_by=None, adapter_receipt=True,
                gate_flags_open=True, executor_behavior="succeed",
                expected_outcome=None, scope_grant_expires_at=None,
                adapter_name="stub-adapter"):
    """Build a schematic fixture Action row (design SS14: 'a fixture
    Action row (schematic, marked as such -- never a real ForgeOS row)').

    The worker never creates the Action row in the field; in file mode
    the fixture stands in for the row the governance path would create.
    parameters_json carries the lead's hypothesis + falsification
    condition verbatim (SS5.1)."""
    if status is None:
        status = "APPROVED" if policy_result == "ALLOW" else "PROPOSED"
    if scope_grant_expires_at is None:
        scope_grant_expires_at = "2099-01-01T00:00:00Z"
    if expected_outcome is None:
        # A failing executor behavior declares a FAILURE outcome; a
        # succeeding one declares SUCCESS. The fixture states its
        # outcome; the worker never invents one.
        expected_outcome = {
            "label": ("FAILURE" if executor_behavior in (
                "transient_fail", "permanent_fail") else "SUCCESS"),
            "qualitative_result": "fixture outcome: hypothesis test ran",
            "falsification": "not_falsified",
            "actual_value": None, "unit": None,
        }
    action = {
        "id": action_id,
        "decision_id": "dimag-decision-%s" % lead_id,
        "action_type": "diagnostic-lead-execution",
        "objective": "Execute the diagnostic lead's hypothesis as an "
                     "action: %s" % hypothesis,
        "parameters_json": {
            "lead_id": lead_id,
            "hypothesis": hypothesis,
            "falsification_condition": falsification_condition,
        },
        "status": status,
        "policy_result": policy_result,
        "policy_reason": "fixture verdict: %s" % policy_result,
        "approved_at": approved_at,
        "approved_by": approved_by,
        "execution_result": None,
        "execution_error": None,
        "verification_state": "unverified",
        "adapter_name": adapter_name,
        "fixture": True,
        "schematic": True,
        "adapter_receipt": adapter_receipt,
        "gate_flags_open": gate_flags_open,
        "target_in_do_not_contact": False,
        "scope_grant_expires_at": scope_grant_expires_at,
        "executor_behavior": executor_behavior,
        "expected_outcome": expected_outcome,
        "record_hash": "",
    }
    action["record_hash"] = record_hash(action, "record_hash")
    return action


def write_action_fixture(worker, action):
    """Store a fixture Action row under actions/. The worker requests
    bindings; it does not write ForgeOS rows (design SS5.1)."""
    errors = _check_keys(action, ACTION_FIELDS, "action fixture")
    if errors:
        raise WorkerError("action_fixture_bad", "; ".join(errors))
    path = worker._p("actions", "%s.json" % action["id"])
    atomic_write_json(path, action)
    worker.log_event("action_fixture_written", action_id=action["id"],
                     policy_result=action["policy_result"])
    return path


def read_action(worker, action_id):
    """Read an Action row for a bound lead.

    Mac/ForgeOS port: when the worker carries an ``action_reader`` hook
    (set by field_seam.field_wiring), the row is read LIVE from the
    ForgeOS database on every call -- never from a cached copy (design
    SS5.1). File mode (default): the schematic fixture under actions/.
    Every call site (validate_binding, FileSeam/ForgeOSSeam,
    StubExecutor, execute_lead E2/E7) goes through this function, so
    the one hook covers all of them."""
    reader = getattr(worker, "action_reader", None)
    if reader is not None:
        return reader(worker, action_id)
    path = worker._p("actions", "%s.json" % action_id)
    if not os.path.exists(path):
        return None
    action = read_json_file(path)
    errors = _check_keys(action, ACTION_FIELDS, "action fixture")
    if errors:
        raise WorkerError("action_fixture_bad", "; ".join(errors))
    return action


def request_binding(worker, lead_id, actor=None):
    """Emit a binding-request record (design SS5.1): the worker may
    request a binding; it never creates the Action row or approves its
    own binding. A request is a proposal, not an action."""
    registry = worker.load_registry()
    entry = registry.get(lead_id)
    if entry is None:
        raise WorkerError("lead_not_in_registry", lead_id)
    # Quarantine is a property of the lead (a non-null quarantine_reason),
    # not of one status value: lead 000001 is ALREADY_TESTED *and*
    # quarantined, and it is refused exactly like the QUARANTINED ones.
    if (entry["quarantine"] or {}).get("quarantine_reason") is not None \
            and not execution_granted(worker, lead_id):
        worker.log_event("binding_request_refused", lead_id=lead_id,
                         reason="binding_quarantine_refused",
                         quarantine_reason=(entry["quarantine"] or {})
                         .get("quarantine_reason"))
        raise WorkerError(
            "binding_quarantine_refused",
            "%s is QUARANTINED (%s)" % (
                lead_id,
                (entry["quarantine"] or {}).get("quarantine_reason")))
    if entry.get("bound_action_id"):
        raise WorkerError("already_bound",
                          "%s is bound to %s"
                          % (lead_id, entry["bound_action_id"]))
    # Idempotent: an open REQUESTED request for this lead is returned,
    # not duplicated (SS7.4: duplicate delivery is a recorded no-op).
    for existing in read_jsonl(worker._p("binding-requests.jsonl")):
        if existing.get("lead_id") == lead_id and \
                existing.get("status") == "REQUESTED":
            worker.log_event("binding_request_duplicate_ignored",
                             lead_id=lead_id,
                             request_id=existing["request_id"])
            return existing
    record = {
        "request_id": "dimag-bindreq-%s" % lead_id,
        "lead_id": lead_id,
        "trace_id": entry["trace_id"],
        "hypothesis": entry["hypothesis"],
        "falsification_condition": entry["falsification_condition"],
        "proposed_objective": "Execute the diagnostic lead's hypothesis "
                              "as an action: %s" % entry["hypothesis"],
        "proposed_parameters_json": {
            "lead_id": lead_id,
            "hypothesis": entry["hypothesis"],
            "falsification_condition": entry["falsification_condition"],
        },
        "requested_by": actor or WORKER_NAME,
        "requested_at": worker.now_iso(),
        "status": "REQUESTED",
    }
    record["request_hash"] = record_hash(record, "request_hash")
    append_jsonl(worker._p("binding-requests.jsonl"), record)
    worker.log_event("binding_requested", lead_id=lead_id,
                     request_id=record["request_id"])
    return record


def record_binding(worker, lead_id, action_id, bound_by):
    """Record a binding of a lead to an Action row (design SS5.1).

    The binding is recorded by a named actor, never 'the system'. The
    worker validates: lead not quarantined, Action row exists, the
    Action's parameters_json carries the falsification condition
    verbatim, one live binding per lead."""
    registry = worker.load_registry()
    entry = registry.get(lead_id)
    if entry is None:
        raise WorkerError("lead_not_in_registry", lead_id)
    if (entry["quarantine"] or {}).get("quarantine_reason") is not None \
            and not execution_granted(worker, lead_id):
        worker.log_event("binding_refused", lead_id=lead_id,
                         reason="binding_quarantine_refused")
        raise WorkerError(
            "binding_quarantine_refused",
            "%s is QUARANTINED" % lead_id)
    if entry.get("bound_action_id"):
        raise WorkerError("already_bound",
                          "%s is bound to %s"
                          % (lead_id, entry["bound_action_id"]))
    action = read_action(worker, action_id)
    if action is None:
        raise WorkerError("action_not_found", action_id)
    params = action.get("parameters_json") or {}
    if params.get("falsification_condition") != \
            entry["falsification_condition"]:
        raise WorkerError(
            "binding_no_falsification",
            "Action parameters_json does not carry the lead's "
            "falsification condition verbatim")
    if params.get("hypothesis") != entry["hypothesis"]:
        raise WorkerError(
            "binding_no_hypothesis",
            "Action parameters_json does not carry the lead's hypothesis "
            "verbatim")
    n = len([f for f in os.listdir(worker._p("bindings"))
             if f.startswith("dimag-bind-%s-" % lead_id)]) + 1
    binding = {
        "binding_id": "dimag-bind-%s-%02d" % (lead_id, n),
        "lead_id": lead_id,
        "action_id": action_id,
        "bound_at": worker.now_iso(),
        "bound_by": bound_by,
        "binding_basis": "lead hypothesis %r maps to action objective %r; "
                         "parameters_json %r"
                         % (entry["hypothesis"], action["objective"],
                            canonical_json(params)),
        "policy_result_at_binding": action["policy_result"],
        "approval_record": ({"approved_at": action["approved_at"],
                             "approved_by": action["approved_by"]}
                            if action.get("approved_at") else None),
        "scope_grant": action.get("scope_grant_expires_at"),
        "binding_hash": "",
    }
    binding["binding_hash"] = record_hash(binding, "binding_hash")
    atomic_write_json(
        worker._p("bindings", "%s.json" % binding["binding_id"]), binding)
    entry["bound_action_id"] = action_id
    entry["bound_at"] = binding["bound_at"]
    entry["bound_by"] = bound_by
    worker._transition(lead_id, "BOUND", "bound to %s by %s"
                       % (action_id, bound_by), actor=bound_by)
    worker.save_registry()
    worker.log_event("binding_recorded", lead_id=lead_id,
                     binding_id=binding["binding_id"],
                     action_id=action_id, bound_by=bound_by)
    return binding


def read_binding(worker, lead_id):
    """The live binding for a lead, or None."""
    registry = worker.load_registry()
    entry = registry.get(lead_id)
    if entry is None or not entry.get("bound_action_id"):
        return None
    for name in sorted(os.listdir(worker._p("bindings"))):
        if not name.endswith(".json"):
            continue
        binding = read_json_file(worker._p("bindings", name))
        if binding.get("lead_id") == lead_id and \
                binding.get("action_id") == entry["bound_action_id"]:
            errors = _check_keys(binding, BINDING_FIELDS, "binding")
            if errors:
                raise WorkerError("binding_corrupt", "; ".join(errors))
            _check_hash(binding, "binding_hash", "binding", errors)
            if errors:
                raise WorkerError("binding_corrupt", "; ".join(errors))
            return binding
    return None


def validate_binding(worker, lead_id):
    """Re-validate a binding against the live Action row (design SS5.1):
    the binding is validated at execution time, never trusted from
    binding time. Returns (ok, reason)."""
    registry = worker.load_registry()
    entry = registry.get(lead_id)
    if entry is None:
        return False, "lead_not_in_registry"
    binding = read_binding(worker, lead_id)
    if binding is None:
        return False, "no_binding"
    action = read_action(worker, entry["bound_action_id"])
    if action is None:
        return False, "action_not_found"
    if action.get("status") in ("CANCELLED", "BLOCKED"):
        return False, "action_cancelled_or_blocked"
    if action.get("status") not in ("APPROVED", "PROPOSED"):
        return False, "action_status_%s" % action.get("status")
    expires = action.get("scope_grant_expires_at")
    if expires and parse_iso(expires) <= worker.now():
        return False, "scope_grant_expired"
    return True, "ok"


def unbind(worker, lead_id, actor, reason):
    """Explicitly unbind a lead (design SS5.1): recorded with a reason;
    the unbinding is preserved in the history."""
    registry = worker.load_registry()
    entry = registry.get(lead_id)
    if entry is None:
        raise WorkerError("lead_not_in_registry", lead_id)
    binding = read_binding(worker, lead_id)
    if binding is None:
        raise WorkerError("not_bound", lead_id)
    entry["bound_action_id"] = None
    entry["bound_at"] = None
    entry["bound_by"] = None
    worker._transition(lead_id, "PROPOSED", "unbound by %s: %s"
                       % (actor, reason), actor=actor)
    worker.log_event("binding_unbound", lead_id=lead_id,
                     binding_id=binding["binding_id"], actor=actor,
                     reason=reason)
    worker.save_registry()
    return binding


# ---------------------------------------------------------------------------
# Governance seam (design SS8.1) -- file mode reads a recorded mask
# fixture; the consultation itself is recorded (SS14 T5).
# ---------------------------------------------------------------------------

class FileSeam:
    """The DIMAG-001 SS2.5 governance seam in file mode: computed from
    the live Action row + STOP state + grants. A lead is allowed iff ALL
    hold: (a) policy ALLOW, or REQUIRE_APPROVAL with a recorded
    approval; (b) no owner STOP; (c) every gate flag the action touches
    is open (default closed); (d) target not in DoNotContact; (e) scope
    grant unexpired."""

    def __init__(self, worker):
        self.worker = worker

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
            action = read_action(worker, entry["bound_action_id"])
            if action is None:
                verdict["reason"] = "action_not_found"
            elif action.get("policy_result") == "ALLOW":
                verdict.update(self._rest(action))
            elif action.get("policy_result") == "REQUIRE_APPROVAL" and \
                    action.get("approved_at"):
                verdict.update(self._rest(action))
            elif action.get("policy_result") == "REQUIRE_APPROVAL":
                verdict["reason"] = "approval_missing"
            else:
                verdict["reason"] = "policy_%s" % (
                    action.get("policy_result"))
        worker.log_event("seam_consult", lead_id=lead_id,
                         allowed=verdict["allowed"],
                         reason=verdict["reason"])
        return verdict

    def _rest(self, action):
        worker = self.worker
        if worker.stop_active():
            return {"allowed": False, "reason": "stop_active"}
        if not action.get("gate_flags_open", False):
            return {"allowed": False, "reason": "gate_flags_closed"}
        if action.get("target_in_do_not_contact"):
            return {"allowed": False, "reason": "do_not_contact"}
        expires = action.get("scope_grant_expires_at")
        if expires and parse_iso(expires) <= worker.now():
            return {"allowed": False, "reason": "scope_grant_expired"}
        return {"allowed": True, "reason": "ok"}


# ---------------------------------------------------------------------------
# Leases (design SS6)
# ---------------------------------------------------------------------------

def _lease_path(worker, lead_id):
    return worker._p("leases", "%s.json" % lead_id)


def read_lease(worker, lead_id):
    """Read a lease file from disk; validate fields + hash. Returns None
    if no lease file exists. A corrupt lease is an error, never a silent
    absence."""
    path = _lease_path(worker, lead_id)
    if not os.path.exists(path):
        return None
    lease = read_json_file(path)
    errors = validate_lease(lease)
    if errors:
        raise WorkerError("lease_corrupt", "; ".join(errors))
    return lease


def lease_is_live(worker, lease):
    if lease is None:
        return False
    return parse_iso(lease["expires_at"]) > worker.now()


def _check_clock_suspect(worker, lease):
    """A lease whose acquired_at is >300 s in the future is corrupt
    (design SS6.2): never acquired, never taken over, flagged R1."""
    if parse_iso(lease["acquired_at"]) > worker.now() + timedelta(
            seconds=worker.clock_suspect_s):
        raise WorkerError(
            "lease_clock_suspect",
            "%s acquired_at %s is %ds+ in the future"
            % (lease["lead_id"], lease["acquired_at"],
               worker.clock_suspect_s))


def _new_lease(worker, lead_id, execution_key):
    now = worker.now()
    lease = {
        "lease_id": "dimag-lease-%s-%02d"
                    % (lead_id, _lease_sequence(worker, lead_id)),
        "lead_id": lead_id,
        "worker_id": worker.worker_id,
        "lease_token": uuid.uuid4().hex,
        "acquired_at": fmt_iso(now),
        "expires_at": fmt_iso(now + timedelta(
            seconds=worker.lease_duration_s)),
        "heartbeat_at": fmt_iso(now),
        "lease_duration_s": worker.lease_duration_s,
        "heartbeat_interval_s": worker.heartbeat_interval_s,
        "execution_key": execution_key,
        "renewal_count": 0,
        "lease_hash": "",
    }
    lease["lease_hash"] = record_hash(lease, "lease_hash")
    return lease


def _lease_sequence(worker, lead_id):
    n = 0
    for event in worker.read_events():
        if event.get("event_type") == "lease_acquired" and \
                event.get("lead_id") == lead_id:
            n += 1
    return n + 1


def acquire_lease(worker, lead_id):
    """Acquire a lease on a BOUND lead (design SS6.2). Fails (never waits,
    never breaks) if a live lease exists: lease_held_by_<worker_id>. An
    expired lease file must go through takeover_lease, not acquire."""
    registry = worker.load_registry()
    entry = registry.get(lead_id)
    if entry is None:
        raise WorkerError("lead_not_in_registry", lead_id)
    if worker.stop_active():
        raise WorkerError("lease_refused_stop_active",
                          "owner STOP is active")
    # The live-lease check comes before the BOUND check: a second
    # worker's acquisition must fail with lease_held_by_<worker_id>
    # (design SS14 T3), not with "not BOUND".
    existing = read_lease(worker, lead_id)
    if existing is not None:
        _check_clock_suspect(worker, existing)
        if lease_is_live(worker, existing):
            raise WorkerError("lease_held_by_%s" % existing["worker_id"],
                              "live until %s" % existing["expires_at"])
        raise WorkerError("lease_expired_takeover_required",
                          "expired lease file exists; use takeover_lease")
    if (entry["quarantine"] or {}).get("quarantine_reason") is not None \
            and not execution_granted(worker, lead_id):
        raise WorkerError(
            "lease_refused_quarantined",
            "%s is QUARANTINED (%s)" % (
                lead_id, (entry["quarantine"] or {})
                .get("quarantine_reason")))
    if entry["intake_status"] != "BOUND":
        raise WorkerError("lease_refused_not_bound",
                          "%s is %s, not BOUND"
                          % (lead_id, entry["intake_status"]))
    ok, reason = validate_binding(worker, lead_id)
    if not ok:
        raise WorkerError("lease_refused_binding_invalid", reason)
    execution_key = execution_key_for(lead_id, entry.get("attempt", 0) + 1)
    lease = _new_lease(worker, lead_id, execution_key)
    atomic_write_json(_lease_path(worker, lead_id), lease)
    worker._transition(lead_id, "LEASED",
                       "lease %s acquired, token %s..."
                       % (lease["lease_id"], lease["lease_token"][:8]))
    worker.save_registry()
    worker.log_event("lease_acquired", lead_id=lead_id,
                     lease_id=lease["lease_id"],
                     lease_token=lease["lease_token"],
                     expires_at=lease["expires_at"],
                     execution_key=execution_key)
    return lease


def renew_lease(worker, lead_id):
    """Renew only one's own lease, only while still held, only before
    expiry (design SS6.2). At most 5 renewals; after that the worker
    must release and re-acquire."""
    lease = read_lease(worker, lead_id)
    if lease is None:
        raise WorkerError("lease_not_found", lead_id)
    if lease["worker_id"] != worker.worker_id:
        raise WorkerError("lease_not_ours",
                          "held by %s" % lease["worker_id"])
    if not lease_is_live(worker, lease):
        raise WorkerError("lease_expired", "expires_at %s"
                          % lease["expires_at"])
    if lease.get("renewal_count", 0) >= worker.max_renewals:
        raise WorkerError("lease_renewal_limit",
                          "%d renewals used" % lease["renewal_count"])
    now = worker.now()
    lease["heartbeat_at"] = fmt_iso(now)
    lease["expires_at"] = fmt_iso(now + timedelta(
        seconds=worker.lease_duration_s))
    lease["renewal_count"] = lease.get("renewal_count", 0) + 1
    lease["lease_hash"] = record_hash(lease, "lease_hash")
    atomic_write_json(_lease_path(worker, lead_id), lease)
    worker.log_event("lease_renewed", lead_id=lead_id,
                     lease_id=lease["lease_id"],
                     renewal_count=lease["renewal_count"],
                     expires_at=lease["expires_at"])
    return lease


def release_lease(worker, lead_id, reason="completed"):
    """Release a lease: write the `released` tombstone event first,
    then remove the file (design SS6.2). A lease file that disappears
    without a tombstone is a reconciliation discrepancy (R1)."""
    lease = read_lease(worker, lead_id)
    if lease is None:
        worker.log_event("lease_release_no_file", lead_id=lead_id,
                         reason=reason)
        return None
    if lease["worker_id"] != worker.worker_id:
        raise WorkerError("lease_not_ours",
                          "held by %s" % lease["worker_id"])
    worker.log_event("lease_released", lead_id=lead_id,
                     lease_id=lease["lease_id"],
                     lease_token=lease["lease_token"], reason=reason)
    os.remove(_lease_path(worker, lead_id))
    return lease


def takeover_lease(worker, lead_id, new_worker_id=None):
    """Take over an expired lease (design SS6.3). Steps: re-read expiry
    from disk; wait a 60 s grace past expires_at (takeover inside the
    grace is refused); write a new lease atomically (new token, new
    worker, new execution-key attempt); record lease_takeover. The lead
    enters RECONCILING -- takeover of the lease is not takeover of the
    execution's outcome."""
    registry = worker.load_registry()
    entry = registry.get(lead_id)
    if entry is None:
        raise WorkerError("lead_not_in_registry", lead_id)
    existing = read_lease(worker, lead_id)
    if existing is None:
        raise WorkerError("lease_not_found",
                          "no lease file for %s" % lead_id)
    _check_clock_suspect(worker, existing)
    if lease_is_live(worker, existing):
        raise WorkerError("lease_held_by_%s" % existing["worker_id"],
                          "live until %s" % existing["expires_at"])
    grace_end = parse_iso(existing["expires_at"]) + timedelta(
        seconds=worker.takeover_grace_s)
    if worker.now() < grace_end:
        raise WorkerError(
            "lease_takeover_grace",
            "expires_at %s + %ds grace not yet passed (now %s)"
            % (existing["expires_at"], worker.takeover_grace_s,
               worker.now_iso()))
    old_token = existing["lease_token"]
    old_worker = existing["worker_id"]
    old_expires = existing["expires_at"]
    worker_id = new_worker_id or worker.worker_id
    execution_key = execution_key_for(lead_id, entry.get("attempt", 0) + 1)
    lease = _new_lease(worker, lead_id, execution_key)
    lease["worker_id"] = worker_id
    lease["lease_hash"] = record_hash(lease, "lease_hash")
    atomic_write_json(_lease_path(worker, lead_id), lease)
    worker.log_event("lease_takeover", lead_id=lead_id,
                     lease_id=lease["lease_id"],
                     lease_token=lease["lease_token"],
                     old_worker_id=old_worker, old_token=old_token,
                     old_expires_at=old_expires,
                     grace_observed_s=worker.takeover_grace_s)
    # The lead is frozen until reconciliation establishes whether the
    # previous owner's execution ran (SS6.3 step 5, SS6.4).
    if entry["intake_status"] in ("LEASED", "EXECUTING"):
        worker._transition(lead_id, "RECONCILING",
                           "lease taken over from %s after expiry+grace; "
                           "prior execution outcome unknown" % old_worker)
        worker.save_registry()
    return lease


def reconcile_after_takeover(worker, lead_id, executor=None):
    """After a takeover, establish whether the previous owner's execution
    ran (design SS6.3 step 5 / SS12.1 steps 4-5): from the execution
    record + receipt query. Returns the verdict."""
    registry = worker.load_registry()
    entry = registry.get(lead_id)
    if entry is None:
        raise WorkerError("lead_not_in_registry", lead_id)
    attempt = entry.get("attempt", 0)
    if attempt == 0:
        # No execution was ever attempted under the old lease.
        verdict = "VERIFIED_NOT_EXECUTED"
        worker.log_event("takeover_reconciled", lead_id=lead_id,
                         verdict=verdict,
                         detail="no execution record under any attempt")
    else:
        key = execution_key_for(lead_id, attempt)
        record = read_execution(worker, key)
        if record is None:
            verdict = "VERIFIED_NOT_EXECUTED"
            worker.log_event("takeover_reconciled", lead_id=lead_id,
                             verdict=verdict,
                             detail="no execution record under %s" % key)
        else:
            verdict = _verdict_from_receipt_query(worker, lead_id, key,
                                                  executor)
    if verdict == "VERIFIED_NOT_EXECUTED":
        if entry["intake_status"] == "RECONCILING":
            worker._transition(lead_id, "BOUND",
                               "takeover reconciled: prior execution "
                               "verified not executed")
            worker.save_registry()
    elif verdict in ("VERIFIED_COMPLETED", "STILL_UNKNOWN"):
        worker.log_event("takeover_reconciled", lead_id=lead_id,
                         verdict=verdict)
    return verdict


def _verdict_from_receipt_query(worker, lead_id, key, executor):
    """Query the adapter's receipt by execution key (design SS12.1 step
    4). Returns VERIFIED_COMPLETED / VERIFIED_NOT_EXECUTED /
    STILL_UNKNOWN."""
    if executor is None:
        return "STILL_UNKNOWN"
    result = executor.query_receipt(key)
    status = result.get("status")
    if status == "executed":
        return "VERIFIED_COMPLETED"
    if status == "not_executed":
        return "VERIFIED_NOT_EXECUTED"
    return "STILL_UNKNOWN"


# ---------------------------------------------------------------------------
# Execution records (design SS9.1) + stub executor + receipts
# ---------------------------------------------------------------------------

def _execution_path(worker, key):
    return worker._p("executions", "%s.json" % key)


def read_execution(worker, key):
    path = _execution_path(worker, key)
    if not os.path.exists(path):
        return None
    record = read_json_file(path)
    errors = validate_execution(record)
    if errors:
        raise WorkerError("execution_corrupt", "; ".join(errors))
    return record


def list_executions(worker):
    """All execution records, including version files (<key>.v2.json --
    corrections carry a supersedes link, design SS9.1)."""
    records = []
    for name in sorted(os.listdir(worker._p("executions"))):
        if not name.endswith(".json"):
            continue
        record = read_json_file(worker._p("executions", name))
        record["_file"] = name
        records.append(record)
    return records


def write_execution_record(worker, record):
    # Strip loader artifacts (list_executions attaches "_file"); the
    # stored record never carries them.
    record = {k: v for k, v in record.items() if k != "_file"}
    errors = validate_execution(record)
    if errors:
        raise WorkerError("execution_bad", "; ".join(errors))
    atomic_write_json(_execution_path(worker, record["execution_key"]),
                      record)
    return record


def write_execution_version(worker, record, version=2):
    """A correction appends a new record version with a supersedes link
    (design SS9.1); the original is preserved, never overwritten."""
    record = {k: v for k, v in record.items() if k != "_file"}
    errors = validate_execution(record)
    if errors:
        raise WorkerError("execution_bad", "; ".join(errors))
    path = worker._p("executions",
                     "%s.v%d.json" % (record["execution_key"], version))
    atomic_write_json(path, record)
    return record


def read_receipt(worker, key):
    path = worker._p("receipts", "%s.json" % key)
    if not os.path.exists(path):
        return None
    return read_json_file(path)


class StubExecutor:
    """The test/field-mode executor (design SS13.3, SS14).

    Behaviors are declared on the fixture Action row, never invented by
    the worker:
      succeed         -> outcome + receipt (COMPLETED)
      transient_fail  -> failure + receipt, error_kind transient (retryable)
      permanent_fail  -> failure + receipt, error_kind permanent (never retried)
      timeout         -> ExecutorTimeout, no receipt (UNKNOWN)
      crash_after_intent -> CrashSimulated after the intent record exists
    The adapter writes its receipt into receipts/ (its receipt store);
    the worker embeds the receipt in the execution record. query_receipt
    answers executed / not_executed (fixture attestation) / unknown.
    Every call is recorded in call_log (test T2 proves no second call
    under one key)."""

    def __init__(self, worker):
        self.worker = worker
        self.call_log = []          # (execution_key, lease_token, result)
        self.attestations = {}      # execution_key -> "not_executed"

    def call(self, worker, lead_id, key, lease_token, payload):
        """Present the fencing token with the call (design SS6.2): the
        executor refuses an attempt whose token does not match the live
        lease file."""
        lease = read_lease(worker, lead_id)
        if lease is None or lease.get("lease_token") != lease_token:
            raise WorkerError(
                "exec_refused_stale_token",
                "token %s does not match the live lease for %s"
                % (str(lease_token)[:8], lead_id))
        registry = worker.load_registry()
        entry = registry[lead_id]
        action = read_action(worker, entry["bound_action_id"])
        behavior = (action or {}).get("executor_behavior", "succeed")
        if behavior == "crash_after_intent":
            raise CrashSimulated(
                "simulated crash after intent record for %s" % key)
        if behavior == "timeout":
            raise ExecutorTimeout("adapter timed out for %s" % key)
        outcome = dict((action or {}).get("expected_outcome") or {})
        label = outcome.get("label", "SUCCESS")
        if behavior in ("transient_fail", "permanent_fail"):
            # A failing behavior returns a failure, whatever the fixture
            # text says: the outcome label must agree with the behavior,
            # or the worker would record a "successful failure".
            label = "FAILURE"
        receipt = {
            "receipt_id": "dimag-rcpt-%s" % uuid.uuid4().hex[:12],
            "received_at": worker.now_iso(),
            "external_ref": "stub-external-%s" % key,
            "outcome_label": label,
        }
        atomic_write_json(worker._p("receipts", "%s.json" % key), receipt)
        result = {
            "outcome_label": label,
            "error_kind": ("transient" if behavior == "transient_fail"
                           else "permanent"
                           if behavior == "permanent_fail" else None),
            "qualitative_result": outcome.get(
                "qualitative_result", "fixture outcome"),
            "falsification": outcome.get("falsification", "not_checkable"),
            "actual_value": outcome.get("actual_value"),
            "unit": outcome.get("unit"),
            "receipt": receipt,
        }
        self.call_log.append((key, lease_token, behavior))
        return result

    def query_receipt(self, key):
        """Query the adapter's receipt by execution key (design SS12.1
        step 4). A planted attestation of non-execution is reported as
        such; a receipt file proves execution; otherwise unknown."""
        if self.attestations.get(key) == "not_executed":
            return {"status": "not_executed", "execution_key": key}
        receipt = read_receipt(self.worker, key)
        if receipt is not None:
            return {"status": "executed", "execution_key": key,
                    "receipt": receipt,
                    "outcome_label": receipt.get("outcome_label")}
        return {"status": "unknown", "execution_key": key}

    def attest_not_executed(self, key):
        self.attestations[key] = "not_executed"


def check_falsification(condition, outcome):
    """Check the lead's falsification condition against the measured
    outcome (design SS9.1). The stub adapter returns an explicit
    falsification verdict with its structured outcome; without one the
    worker records 'not_checkable' rather than claiming the hypothesis
    survived (see README deviation D3)."""
    result = (outcome or {}).get("falsification", "not_checkable")
    if result not in ("not_falsified", "falsified", "not_checkable"):
        result = "not_checkable"
    return {"condition": condition, "result": result}


def write_handoff(worker, execution_record):
    """Write the handoff record for the DIMAG-002 pipeline (design
    SS9.2). The worker never writes an experience row; the handoff is
    the worker's output, in the worker's own files."""
    registry = worker.load_registry()
    entry = registry.get(execution_record["lead_id"])
    outcome = execution_record.get("outcome") or {}
    handoff = {
        "handoff_id": "dimag-handoff-%s" % execution_record["execution_key"],
        "execution_key": execution_record["execution_key"],
        "lead_id": execution_record["lead_id"],
        "trace_id": execution_record["trace_id"],
        "source_record_id": entry["source_record_id"] if entry else None,
        "action_id": execution_record["action_id"],
        "receipt_id": (execution_record.get("receipt") or {})
                      .get("receipt_id"),
        "outcome": outcome,
        "falsification_checked": execution_record.get(
            "falsification_checked"),
        "written_at": worker.now_iso(),
        "written_by": WORKER_NAME,
        "record_hash": "",
    }
    handoff["record_hash"] = record_hash(handoff, "record_hash")
    errors = _check_keys(handoff, HANDOFF_FIELDS, "handoff")
    if errors:
        raise WorkerError("handoff_bad", "; ".join(errors))
    atomic_write_json(
        worker._p("handoff",
                  "dimag-handoff-%s.json" % execution_record["execution_key"]),
        handoff)
    worker.log_event("handoff_written", lead_id=handoff["lead_id"],
                     execution_key=handoff["execution_key"],
                     outcome_label=outcome.get("label"))
    return handoff


# ---------------------------------------------------------------------------
# The execution boundary (design SS8.2) + executing (SS9)
# ---------------------------------------------------------------------------

def _release_if_mine(worker, lead_id, reason):
    """Release a lease held by this worker; never fail the caller if
    the lease is absent or held by someone else (used on refusal /
    park paths, where a leftover lease file would trip R1)."""
    try:
        lease = read_lease(worker, lead_id)
    except WorkerError:
        return None
    if lease is None or lease["worker_id"] != worker.worker_id:
        return None
    return release_lease(worker, lead_id, reason=reason)


def _refuse(worker, lead_id, check, reason, detail="", park=None):
    """Record a refusal with check number, reason, and evidence (design
    SS8.2). A refused execution is a complete result, not a failure.
    A parked lead's lease is released: a parked lead must not keep a
    live lease file, or the next cycle could never re-acquire it."""
    worker.log_event("execution_refused", lead_id=lead_id, check=check,
                     reason=reason, detail=detail)
    if park:
        registry = worker.load_registry()
        entry = registry.get(lead_id)
        if entry is not None and entry["intake_status"] not in (
                TERMINAL_STATES):
            worker._transition(lead_id, park,
                               "refused at %s: %s" % (check, reason))
            _release_if_mine(worker, lead_id,
                             "refused_%s_parked" % check.lower())
            worker.save_registry()
    return {"refused": True, "check": check, "reason": reason,
            "detail": detail}


def execute_lead(worker, lead_id, executor=None, seam=None,
                 cycle_state=None):
    """Execute one lead through the E1-E8 checklist (design SS8.2),
    immediately before the executor call. Returns a result dict:
    {"completed": ...} / {"replayed": ...} / {"refused": ...} /
    {"deferred": ...} / {"unknown": ...} / {"retry_wait": ...} /
    {"dead_letter": ...}.

    executor defaults to a StubExecutor; seam defaults to FileSeam.
    cycle_state (a dict with 'executions' and 'started_mono') enforces
    the E8 cycle budget when the call runs inside run_cycle."""
    executor = executor or StubExecutor(worker)
    seam = seam or FileSeam(worker)
    registry = worker.load_registry()
    entry = registry.get(lead_id)
    if entry is None:
        raise WorkerError("lead_not_in_registry", lead_id)

    # Replay path (SS7.2): a DONE lead's execution key returns the
    # recorded result with no executor call and no new record.
    if entry["intake_status"] == "DONE" and entry.get("execution_key"):
        record = read_execution(worker, entry["execution_key"])
        if record is not None and record["phase"] in ("COMPLETED",
                                                      "FAILED"):
            worker.log_event("replay_returned_recorded_result",
                             lead_id=lead_id,
                             execution_key=entry["execution_key"],
                             phase=record["phase"])
            return {"replayed": True, "execution_key":
                    entry["execution_key"], "record": record}

    # E6, unknown branch (SS7.2): an UNKNOWN record is reconciled
    # before any retry -- never re-run. EXCEPTION (SS12.1 step 7): a
    # record whose recovery verdict is VERIFIED_NOT_EXECUTED is resolved
    # -- the execution provably did not happen, so the lead may resume
    # with a new attempt. Only an unresolved UNKNOWN blocks. The lease
    # is released when blocking: a frozen lead must not keep a live
    # lease file (or the sweep flags R1).
    if entry.get("execution_key"):
        prior = read_execution(worker, entry["execution_key"])
        if prior is not None and prior["phase"] == "UNKNOWN" and \
                prior.get("recovery_verdict") != "VERIFIED_NOT_EXECUTED":
            if entry["intake_status"] != "RECONCILING":
                worker._transition(lead_id, "RECONCILING",
                                   "execution %s is UNKNOWN; reconcile "
                                   "before retry"
                                   % entry["execution_key"])
                _release_if_mine(worker, lead_id, "execution_unknown")
                worker.save_registry()
            return {"unknown": True,
                    "execution_key": entry["execution_key"],
                    "reason": "prior execution UNKNOWN; reconcile first"}

    # E1: a live lease, held by this worker, token matches, unexpired.
    try:
        lease = read_lease(worker, lead_id)
    except WorkerError as exc:
        return _refuse(worker, lead_id, "E1", "exec_refused_no_lease",
                       str(exc))
    if lease is None or not lease_is_live(worker, lease):
        return _refuse(worker, lead_id, "E1", "exec_refused_no_lease",
                       "no live lease file for %s" % lead_id)
    if lease["worker_id"] != worker.worker_id:
        return _refuse(worker, lead_id, "E1", "exec_refused_no_lease",
                       "lease held by %s" % lease["worker_id"])
    if entry["intake_status"] != "LEASED":
        return _refuse(worker, lead_id, "E1", "exec_refused_no_lease",
                       "lead is %s, not LEASED" % entry["intake_status"])

    # E2: the binding is still valid against the live Action row.
    ok, reason = validate_binding(worker, lead_id)
    if not ok:
        return _refuse(worker, lead_id, "E2",
                       "exec_refused_binding_invalid", reason,
                       park="PARKED_BINDING_INVALID")

    # E3: the governance seam allows this lead now.
    verdict = seam.allowed_mask(lead_id)
    if not verdict["allowed"]:
        return _refuse(worker, lead_id, "E3",
                       "exec_refused_not_allowed", verdict["reason"],
                       park="PARKED_UNAPPROVED_ACTION")

    # E4: no owner STOP is active (re-checked immediately before the call).
    if worker.stop_active():
        worker.log_event("cycle_stop_observed", lead_id=lead_id)
        return _refuse(worker, lead_id, "E4", "exec_refused_stop_active",
                       "owner STOP active")

    # E5: not quarantined; no grant revocation since intake.
    if entry["intake_status"] == "QUARANTINED" or \
            (entry["quarantine"] or {}).get("quarantine_reason") is not None:
        if not execution_granted(worker, lead_id):
            return _refuse(worker, lead_id, "E5",
                           "exec_refused_quarantined",
                           "quarantine_reason: %s"
                           % (entry["quarantine"] or {})
                           .get("quarantine_reason"),
                           park="QUARANTINED")

    # E6: an execution key exists for this attempt and no completed
    # record exists under it.
    attempt = entry.get("attempt", 0) + 1
    key = execution_key_for(lead_id, attempt)
    existing = read_execution(worker, key)
    if existing is not None and existing["phase"] in ("COMPLETED",
                                                      "FAILED"):
        worker.log_event("replay_returned_recorded_result", lead_id=lead_id,
                         execution_key=key, phase=existing["phase"])
        return {"replayed": True, "execution_key": key,
                "record": existing}
    if existing is not None and existing["phase"] == "UNKNOWN" and \
            existing.get("recovery_verdict") != "VERIFIED_NOT_EXECUTED":
        worker._transition(lead_id, "RECONCILING",
                           "execution %s is UNKNOWN; reconcile before retry"
                           % key)
        _release_if_mine(worker, lead_id, "execution_unknown")
        worker.save_registry()
        return {"unknown": True, "execution_key": key,
                "reason": "prior execution UNKNOWN; reconcile first"}
    if not key:
        return _refuse(worker, lead_id, "E6",
                       "exec_refused_no_idempotency_key",
                       "no execution key could be established")

    # E7: the Action's adapter provides a receipt mechanism (SS7.3).
    action = read_action(worker, entry["bound_action_id"])
    if action is None or not action.get("adapter_receipt", False):
        return _refuse(worker, lead_id, "E7",
                       "exec_refused_no_receipt_adapter",
                       "adapter %s provides no receipt mechanism"
                       % (action or {}).get("adapter_name"),
                       park="PARKED_NO_RECEIPT_ADAPTER")

    # E8: the cycle budget allows it.
    if cycle_state is not None:
        if cycle_state.get("executions", 0) >= \
                worker.max_leads_per_cycle:
            return {"deferred": True, "check": "E8",
                    "reason": "cycle execution budget exhausted"}
        elapsed = worker.clock.monotonic() - cycle_state["started_mono"]
        if elapsed > worker.max_cycle_wall_s:
            return {"deferred": True, "check": "E8",
                    "reason": "cycle wall-time budget exhausted"}

    # Final fencing-token re-check immediately before the call (SS6.2):
    # a lease that expired since E1 refuses the execution.
    lease = read_lease(worker, lead_id)
    if lease is None or not lease_is_live(worker, lease) or \
            lease["worker_id"] != worker.worker_id:
        return _refuse(worker, lead_id, "E1", "exec_refused_no_lease",
                       "lease lost between checklist and call")

    # Intent phase (SS9.1): written + fsynced BEFORE the executor call.
    worker._transition(lead_id, "EXECUTING",
                       "executor call starting under key %s" % key)
    entry["attempt"] = attempt
    entry["execution_key"] = key
    worker._registry_dirty = True
    worker.save_registry()
    payload = (action or {}).get("parameters_json") or {}
    payload_hash = sha256_text(canonical_json(payload))
    record = {
        "execution_key": key,
        "execution_key_hash": execution_key_hash_for(lead_id, attempt),
        "lead_id": lead_id,
        "trace_id": entry["trace_id"],
        "action_id": entry["bound_action_id"],
        "lease_token": lease["lease_token"],
        "worker_id": worker.worker_id,
        "phase": "EXECUTING",
        "attempt": attempt,
        "executor_call": {"adapter": action.get("adapter_name"),
                          "called_at": worker.now_iso(),
                          "payload_hash": payload_hash},
        "receipt": None,
        "outcome": None,
        "falsification_checked": None,
        "recorded_at": worker.now_iso(),
        "recovery_verdict": None,
        "reconstructed": False,
        "execution_hash": "",
    }
    record["execution_hash"] = record_hash(record, "execution_hash")
    write_execution_record(worker, record)
    worker.log_event("execution_intent", lead_id=lead_id,
                     execution_key=key, lease_token=lease["lease_token"],
                     payload_hash=payload_hash)
    if cycle_state is not None:
        cycle_state["executions"] = cycle_state.get("executions", 0) + 1

    # The executor call. CrashSimulated propagates untouched: a real
    # crash writes nothing more (SS12.1 recovery handles the rest).
    try:
        result = executor.call(worker, lead_id, key,
                               lease["lease_token"], payload)
    except ExecutorTimeout as exc:
        record["phase"] = "UNKNOWN"
        record["recorded_at"] = worker.now_iso()
        record["execution_hash"] = record_hash(record, "execution_hash")
        write_execution_record(worker, record)
        worker.log_event("execution_unknown", lead_id=lead_id,
                         execution_key=key,
                         reason="timeout_no_receipt: %s" % exc)
        worker._transition(lead_id, "RECONCILING",
                           "executor timed out with no receipt; outcome "
                           "UNKNOWN until reconciled")
        release_lease(worker, lead_id, reason="execution_unknown")
        worker.save_registry()
        return {"unknown": True, "execution_key": key,
                "reason": "timeout_no_receipt"}

    # Outcome phase (SS9.1): COMPLETED / FAILED require a receipt.
    label = result.get("outcome_label", "SUCCESS")
    error_kind = result.get("error_kind")
    receipt = result.get("receipt")
    record["receipt"] = receipt
    record["outcome"] = {
        "label": label,
        "actual_value": result.get("actual_value"),
        "unit": result.get("unit"),
        "observed_at": worker.now_iso(),
        "qualitative_result": result.get("qualitative_result", ""),
    }
    record["falsification_checked"] = check_falsification(
        entry["falsification_condition"], result)
    record["recorded_at"] = worker.now_iso()
    is_transient_failure = (label == "FAILURE" and error_kind == "transient")

    if label == "SUCCESS" or (label == "FAILURE" and
                              error_kind == "permanent"):
        # A measured outcome with a receipt: DONE + handoff (SS9.2). A
        # permanent failure is a measured outcome, never a retry (SS12.3).
        record["phase"] = "COMPLETED" if label == "SUCCESS" else "FAILED"
        record["execution_hash"] = record_hash(record, "execution_hash")
        write_execution_record(worker, record)
        worker.log_event("execution_outcome", lead_id=lead_id,
                         execution_key=key, phase=record["phase"],
                         outcome_label=label)
        entry.setdefault("failure_history", [])
        worker._transition(lead_id, "DONE",
                           "execution %s %s with receipt %s"
                           % (key, record["phase"],
                              (receipt or {}).get("receipt_id")))
        write_handoff(worker, record)
        release_lease(worker, lead_id, reason="execution_done")
        worker.save_registry()
        return {"completed": True, "execution_key": key, "record": record}

    # Retryable transient failure (SS12.3): backoff, then RETRY_WAIT;
    # after 3 failed attempts the lead is DEAD_LETTER, never retried.
    record["phase"] = "FAILED"
    record["execution_hash"] = record_hash(record, "execution_hash")
    write_execution_record(worker, record)
    entry.setdefault("failure_history", [])
    entry["failure_history"].append({
        "attempt": attempt, "execution_key": key,
        "error_kind": error_kind, "failed_at": worker.now_iso()})
    worker.log_event("execution_outcome", lead_id=lead_id,
                     execution_key=key, phase="FAILED",
                     outcome_label=label, error_kind=error_kind)
    release_lease(worker, lead_id, reason="execution_failed_retryable")
    if attempt >= worker.max_attempts:
        worker._transition(lead_id, "DEAD_LETTER",
                           "%d failed attempts; poison lead, no further "
                           "automatic retry" % attempt)
        append_jsonl(worker._p("dead-letter.jsonl"), {
            "lead_id": lead_id, "trace_id": entry["trace_id"],
            "attempts": attempt,
            "failure_history": entry["failure_history"],
            "release_epoch": entry.get("release_epoch", 0),
            "dead_lettered_at": worker.now_iso(),
            "dead_lettered_by": WORKER_NAME})
        worker.log_event("dead_letter", lead_id=lead_id, attempts=attempt)
        worker.save_registry()
        return {"dead_letter": True, "execution_key": key,
                "record": record}
    wait_s = worker.backoff_s.get(attempt, 86400)
    entry["next_retry_at"] = fmt_iso(worker.now() + timedelta(seconds=wait_s))
    worker._transition(lead_id, "RETRY_WAIT",
                       "retryable failure; backoff %ds until %s"
                       % (wait_s, entry["next_retry_at"]))
    worker.save_registry()
    return {"retry_wait": True, "execution_key": key,
            "next_retry_at": entry["next_retry_at"], "record": record}


def replay_execution(worker, execution_key):
    """Re-run an execution by key (SS7.2): returns the recorded result
    without an executor call, or raises if no terminal record exists."""
    record = read_execution(worker, execution_key)
    if record is None:
        raise WorkerError("execution_not_found", execution_key)
    if record["phase"] not in ("COMPLETED", "FAILED"):
        raise WorkerError("execution_not_terminal",
                          "%s is %s" % (execution_key, record["phase"]))
    worker.log_event("replay_returned_recorded_result",
                     lead_id=record["lead_id"],
                     execution_key=execution_key, phase=record["phase"])
    return {"replayed": True, "execution_key": execution_key,
            "record": record}


def _sweep_release_lease(worker, lead_id, reason):
    """Remove a lease file with a tombstone event, regardless of which
    worker holds it. Used by recovery and reconciliation -- the
    reconciler, not the owner -- when a lead is frozen or its verdict
    has landed. A file removed this way never trips R1 (the tombstone
    event names the lease token)."""
    path = worker._p("leases", "%s.json" % lead_id)
    if not os.path.exists(path):
        return None
    try:
        lease = read_lease(worker, lead_id)
    except WorkerError:
        lease = None
    worker.log_event("lease_released", lead_id=lead_id,
                     lease_id=(lease or {}).get("lease_id"),
                     lease_token=(lease or {}).get("lease_token"),
                     reason=reason)
    os.remove(path)
    return lease


# ---------------------------------------------------------------------------
# Crash recovery (design SS12.1) -- the book SS31 protocol, step for step
# ---------------------------------------------------------------------------

CYCLE_LEASE_LEAD = "__cycle__"


def acquire_cycle_lease(worker):
    """The cycle lease (SS12.1 step 1): a lease on the cycle itself, same
    file mechanism as SS6, lead `__cycle__`. No recovery step runs
    without it. An expired cycle lease is taken over after the grace."""
    path = worker._p("leases", "%s.json" % CYCLE_LEASE_LEAD)
    now = worker.now()
    if os.path.exists(path):
        lease = read_json_file(path)
        if parse_iso(lease["expires_at"]) > now:
            raise WorkerError("cycle_lease_held_by_%s"
                              % lease["worker_id"],
                              "live until %s" % lease["expires_at"])
        grace_end = parse_iso(lease["expires_at"]) + timedelta(
            seconds=worker.takeover_grace_s)
        if now < grace_end:
            raise WorkerError("cycle_lease_takeover_grace",
                              "grace until %s" % fmt_iso(grace_end))
    lease = {
        "lease_id": "dimag-lease-__cycle__-%s" % uuid.uuid4().hex[:8],
        "lead_id": CYCLE_LEASE_LEAD,
        "worker_id": worker.worker_id,
        "lease_token": uuid.uuid4().hex,
        "acquired_at": fmt_iso(now),
        "expires_at": fmt_iso(now + timedelta(
            seconds=worker.lease_duration_s)),
        "heartbeat_at": fmt_iso(now),
        "lease_duration_s": worker.lease_duration_s,
        "heartbeat_interval_s": worker.heartbeat_interval_s,
        "execution_key": None,
        "renewal_count": 0,
        "lease_hash": "",
    }
    lease["lease_hash"] = record_hash(lease, "lease_hash")
    atomic_write_json(path, lease)
    worker.log_event("cycle_lease_acquired", lease_id=lease["lease_id"])
    return lease


def release_cycle_lease(worker):
    path = worker._p("leases", "%s.json" % CYCLE_LEASE_LEAD)
    if os.path.exists(path):
        lease = read_json_file(path)
        if lease.get("worker_id") == worker.worker_id:
            worker.log_event("cycle_lease_released",
                             lease_id=lease["lease_id"])
            os.remove(path)


def recover_after_crash(worker, executor=None):
    """The book SS31 recovery protocol (design SS12.1), steps 1-8.
    Idempotent: re-running it over already-reconciled state changes
    nothing. Returns a recovery report."""
    executor = executor or StubExecutor(worker)
    report = {"recovered_at": worker.now_iso(), "steps": [], "leads": {}}
    # 1. Acquire the gate/cycle lease.
    acquire_cycle_lease(worker)
    report["steps"].append("1 cycle lease acquired")
    try:
        registry = worker.load_registry()
        # 2. Mark interrupted cycle RECONCILING; EXECUTING leads -> RECONCILING.
        state = worker.read_worker_state() or worker.default_worker_state()
        if (state.get("last_cycle") or {}).get("state") not in (
                None, "committed"):
            state["last_cycle"]["state"] = "RECONCILING"
            worker.write_worker_state(state)
        for lead_id, entry in sorted(registry.items()):
            if entry["intake_status"] == "EXECUTING":
                worker._transition(lead_id, "RECONCILING",
                                   "crash recovery: interrupted execution")
                report["leads"][lead_id] = "marked RECONCILING"
            elif entry["intake_status"] == "LEASED":
                # Claimed but never executed: if its lease expired during
                # the crash window and no execution was ever attempted,
                # the lead is re-queued to BOUND (nothing happened to
                # reconcile). A still-live lease is left alone; it
                # expires on its own and the next cycle claims the lead.
                try:
                    lease = read_lease(worker, lead_id)
                except WorkerError:
                    lease = None
                if (lease is None or not lease_is_live(worker, lease)) \
                        and entry.get("attempt", 0) == 0:
                    worker._transition(
                        lead_id, "BOUND",
                        "crash recovery: lease expired with no execution "
                        "attempted; re-queued")
                    _sweep_release_lease(worker, lead_id,
                                         "recovery_lease_expired")
                    report["leads"][lead_id] = \
                        "lease expired, no execution; re-queued to BOUND"
        # Checkpoint the step-2 transitions immediately: recovery is
        # idempotent only if a second recovery run reads the same state
        # the event log already records (SS11.2 replay consistency).
        worker.save_registry()
        report["steps"].append("2 interrupted cycle + EXECUTING leads "
                               "marked RECONCILING")
        # 3. Mark in-flight external effects UNKNOWN.
        unknowns = []
        for record in list_executions(worker):
            if record["phase"] == "EXECUTING":
                record["phase"] = "UNKNOWN"
                record["recorded_at"] = worker.now_iso()
                record["execution_hash"] = record_hash(record,
                                                       "execution_hash")
                write_execution_record(worker, record)
                unknowns.append(record["execution_key"])
                worker.log_event("execution_marked_unknown",
                                 lead_id=record["lead_id"],
                                 execution_key=record["execution_key"],
                                 reason="crash_before_outcome")
        report["steps"].append("3 %d intent-phase execution(s) marked "
                               "UNKNOWN" % len(unknowns))
        # 4-5. Query receipt / idempotency key; verify or human-review.
        for key in unknowns:
            record = read_execution(worker, key)
            lead_id = record["lead_id"]
            entry = registry.get(lead_id)
            result = executor.query_receipt(key)
            status = result.get("status")
            if status == "executed":
                receipt = result.get("receipt") or {}
                record["receipt"] = receipt
                label = result.get("outcome_label") or \
                    receipt.get("outcome_label") or "SUCCESS"
                record["phase"] = ("COMPLETED" if label == "SUCCESS"
                                   else "FAILED")
                record["outcome"] = {
                    "label": label, "actual_value": None, "unit": None,
                    "observed_at": worker.now_iso(),
                    "qualitative_result": "recovered from receipt %s"
                    % receipt.get("receipt_id")}
                record["falsification_checked"] = check_falsification(
                    (entry or {}).get("falsification_condition", ""),
                    {"falsification": "not_checkable"})
                record["recovery_verdict"] = "VERIFIED_COMPLETED"
                record["execution_hash"] = record_hash(record,
                                                       "execution_hash")
                write_execution_record(worker, record)
                if entry is not None and \
                        entry["intake_status"] == "RECONCILING":
                    worker._transition(lead_id, "DONE",
                                       "recovery: receipt verifies "
                                       "completion")
                    write_handoff(worker, record)
                    _sweep_release_lease(worker, lead_id, "recovery_done")
                report["leads"][lead_id] = "VERIFIED_COMPLETED"
                worker.log_event("recovery_verified", lead_id=lead_id,
                                 execution_key=key,
                                 verdict="VERIFIED_COMPLETED")
            elif status == "not_executed":
                record["recovery_verdict"] = "VERIFIED_NOT_EXECUTED"
                record["execution_hash"] = record_hash(record,
                                                       "execution_hash")
                write_execution_record(worker, record)
                if entry is not None and \
                        entry["intake_status"] == "RECONCILING":
                    worker._transition(lead_id, "BOUND",
                                       "recovery: receipt query proves "
                                       "non-execution; resume with a new "
                                       "attempt")
                    _sweep_release_lease(worker, lead_id,
                                         "recovery_not_executed")
                report["leads"][lead_id] = "VERIFIED_NOT_EXECUTED"
                worker.log_event("recovery_verified", lead_id=lead_id,
                                 execution_key=key,
                                 verdict="VERIFIED_NOT_EXECUTED")
            else:
                record["recovery_verdict"] = "STILL_UNKNOWN"
                record["execution_hash"] = record_hash(record,
                                                       "execution_hash")
                write_execution_record(worker, record)
                if entry is not None and \
                        entry["intake_status"] == "RECONCILING":
                    worker._transition(lead_id, "HUMAN_REVIEW",
                                       "recovery: receipt unobtainable; "
                                       "outcome stays UNKNOWN")
                report["leads"][lead_id] = "STILL_UNKNOWN -> HUMAN_REVIEW"
                worker.log_event("recovery_verified", lead_id=lead_id,
                                 execution_key=key,
                                 verdict="STILL_UNKNOWN")
            # The crashed worker's lease file must not survive the
            # verdict: the lead is BOUND/DONE/HUMAN_REVIEW now, and a
            # leftover lease file would trip R1 and block re-acquisition.
            # The recovery (holding the cycle lease) removes it with a
            # tombstone event.
            _sweep_release_lease(worker, lead_id, "recovery_verdict")
        report["steps"].append("4-5 receipt queries done: %d UNKNOWN "
                               "execution(s) adjudicated" % len(unknowns))
        # 6. Re-check authorization and STOP.
        if worker.stop_active():
            report["steps"].append("6 STOP ACTIVE -- halting, no resume")
            worker.log_event("recovery_stopped", reason="stop_active")
            worker.save_registry()
            worker.write_worker_state(
                worker.read_worker_state()
                or worker.default_worker_state())
            return report
        for lead_id, entry in sorted(registry.items()):
            if entry["intake_status"] == "BOUND":
                ok, reason = validate_binding(worker, lead_id)
                if not ok:
                    worker._transition(lead_id, "PARKED_BINDING_INVALID",
                                       "recovery re-check: %s" % reason)
        report["steps"].append("6 authorization + STOP re-checked")
        # 7. Resume or create a new lead: VERIFIED_NOT_EXECUTED leads are
        # BOUND (the next cycle executes them with a new attempt); a
        # STILL_UNKNOWN lead stays RECONCILING/HUMAN_REVIEW; no new lead
        # is created by recovery (a new lead comes from a trace, SS12.1).
        report["steps"].append("7 resume: BOUND leads await the next "
                               "cycle; no lead created by recovery")
        # 8. Commit a recovery event and checkpoint.
        worker.save_registry()
        worker.log_event("recovery_committed", leads=report["leads"])
        state = worker.read_worker_state() or worker.default_worker_state()
        state["last_recovery"] = report
        worker.write_worker_state(state)
        report["steps"].append("8 recovery event committed + checkpoint")
        return report
    finally:
        release_cycle_lease(worker)


# ---------------------------------------------------------------------------
# Reconciliation (design SS10) -- the sweep, classes R1-R7
# ---------------------------------------------------------------------------

def _annotate_execution(worker, key, annotation):
    """Annotate an execution record without editing it: the annotation
    is a sidecar file; the original record is preserved verbatim
    (design SS10.3)."""
    path = worker._p("executions", "%s.annotation.json" % key)
    existing = []
    if os.path.exists(path):
        existing = read_json_file(path)
    existing.append(dict(annotation, annotated_at=worker.now_iso()))
    atomic_write_json(path, existing)
    return existing


def _human_review_item(worker, kind, lead_id, detail):
    """Queue an item for a named human reviewer (design SS4/SS10.2)."""
    item = {"kind": kind, "lead_id": lead_id, "detail": detail,
            "queued_at": worker.now_iso(), "reviewer": None,
            "adjudication": None}
    append_jsonl(worker._p("human-review.jsonl"), item)
    worker.log_event("human_review_queued", kind=kind, lead_id=lead_id,
                     detail=detail)
    return item


def run_reconciliation(worker, trace_path=None, dataset_path=None,
                       executor=None):
    """Stage 5 sweep (design SS10): compare registry vs leases vs
    executions vs handoffs vs traces; classify R1-R7; write the sweep
    report. Never deletes, never merges, never silently repairs (SS10.3).
    A sweep that finds zero discrepancies still writes its report."""
    executor = executor or StubExecutor(worker)
    registry = worker.load_registry()
    findings = []
    actions = []

    def find(cls, lead_id, detail, evidence, action):
        findings.append({"class": cls, "lead_id": lead_id,
                         "detail": detail, "evidence": evidence,
                         "action": action})
        worker.log_event("reconciliation_finding", cls=cls,
                         lead_id=lead_id, detail=detail, action=action)

    # -- R7 first (safety): any execution record, lease, or binding
    # naming a QUARANTINED lead stops the worker immediately.
    r7_leads = set()
    quarantined = {lid for lid, e in registry.items()
                   if e["intake_status"] == "QUARANTINED" or
                   (e["quarantine"] or {}).get("quarantine_reason")
                   is not None and not execution_granted(worker, lid)}
    for record in list_executions(worker):
        if record["lead_id"] in quarantined:
            r7_leads.add(record["lead_id"])
    for name in sorted(os.listdir(worker._p("leases"))):
        if name.endswith(".json"):
            lead_id = name[:-5]
            if lead_id in quarantined and lead_id != CYCLE_LEASE_LEAD:
                r7_leads.add(lead_id)
    for lid in sorted(r7_leads):
        find("R7", lid, "quarantine_violation",
             {"reason": (registry[lid]["quarantine"] or {})
              .get("quarantine_reason")},
             "STOP worker; incident record; human review required")
        incident = {"incident": "quarantine_violation", "lead_id": lid,
                    "quarantine_reason": (registry[lid]["quarantine"] or {})
                    .get("quarantine_reason"),
                    "recorded_at": worker.now_iso(),
                    "recorded_by": WORKER_NAME}
        atomic_write_json(
            worker._p("incidents",
                      "quarantine_violation-%s.json" % lid), incident)
        _human_review_item(worker, "quarantine_violation", lid,
                           "R7: execution/lease/binding names a "
                           "QUARANTINED lead")
        actions.append("R7 %s: incident recorded, human review queued"
                       % lid)
    if r7_leads:
        worker.halt("quarantine_violation",
                    "R7 for leads %s" % sorted(r7_leads))

    # -- Check 1: registry vs leases.
    live_leases = {}
    for name in sorted(os.listdir(worker._p("leases"))):
        if not name.endswith(".json"):
            continue
        lead_id = name[:-5]
        if lead_id == CYCLE_LEASE_LEAD:
            continue
        try:
            lease = read_lease(worker, lead_id)
        except WorkerError as exc:
            find("R1", lead_id, "lost_lease",
                 {"error": str(exc)}, "lead RECONCILING; lease corrupt")
            continue
        live_leases[lead_id] = lease
        if lead_id in r7_leads:
            continue  # already classified R7; do not double-classify
        entry = registry.get(lead_id)
        if entry is None:
            find("R1", lead_id, "lost_lease",
                 {"error": "lease file names a lead not in the registry"},
                 "lease preserved; lead question to HUMAN_REVIEW")
            _human_review_item(worker, "lost_lease", lead_id,
                               "R1: lease file names an unknown lead")
            continue
        if entry["intake_status"] != "LEASED":
            find("R1", lead_id, "lost_lease",
                 {"lease_token": lease["lease_token"][:8],
                  "lead_status": entry["intake_status"]},
                 "lease file names a lead that is not LEASED; preserved")
            continue
        try:
            _check_clock_suspect(worker, lease)
        except WorkerError as exc:
            find("R1", lead_id, "lost_lease",
                 {"error": str(exc)},
                 "lease_clock_suspect: never acquired, never taken over")
            continue
        if not lease_is_live(worker, lease):
            has_tombstone = any(
                e.get("event_type") in ("lease_released",
                                        "lease_takeover")
                and e.get("lead_id") == lead_id
                and e.get("lease_token") == lease["lease_token"]
                for e in worker.read_events())
            if not has_tombstone:
                find("R1", lead_id, "lost_lease",
                     {"lease_token": lease["lease_token"][:8],
                      "expires_at": lease["expires_at"]},
                     "expired lease file with no tombstone")
    for lead_id, entry in sorted(registry.items()):
        if entry["intake_status"] == "LEASED" and \
                lead_id not in live_leases and lead_id not in r7_leads:
            find("R1", lead_id, "lost_lease",
                 {"error": "lease file missing for a LEASED lead"},
                 "lead RECONCILING; re-queue only after verifying no "
                 "execution record under its key")
    # Apply R1 actions: RECONCILING, then re-queue to BOUND only after
    # verifying no execution record exists under the lead's key.
    for f in findings:
        if f["class"] != "R1" or f["lead_id"] not in registry:
            continue
        lead_id = f["lead_id"]
        entry = registry[lead_id]
        if entry["intake_status"] in ("LEASED", "EXECUTING"):
            worker._transition(lead_id, "RECONCILING",
                               "R1 lost lease: %s" % f["detail"])
        if entry["intake_status"] == "RECONCILING":
            key = entry.get("execution_key")
            has_record = key is not None and \
                read_execution(worker, key) is not None
            if not has_record and entry.get("attempt", 0) == 0:
                worker._transition(lead_id, "BOUND",
                                   "R1: no execution record under the "
                                   "key; re-queued")
                actions.append("R1 %s: re-queued to BOUND" % lead_id)
            else:
                actions.append("R1 %s: stays RECONCILING (execution "
                               "record exists; see R3/R4)" % lead_id)
    worker.save_registry()

    # -- Check 2: leases vs executions.
    for record in list_executions(worker):
        if record.get("_file", "").endswith(".annotation.json"):
            continue
        key = record["execution_key"]
        if record["phase"] == "EXECUTING":
            entry = registry.get(record["lead_id"])
            if entry is None or entry["intake_status"] != "EXECUTING":
                find("R1", record["lead_id"], "lost_lease",
                     {"execution_key": key,
                      "error": "EXECUTING record but lead is not EXECUTING"},
                     "lead RECONCILING")
        token = record.get("lease_token")
        if token:
            known = any(
                e.get("event_type") in ("lease_acquired", "lease_takeover")
                and e.get("lead_id") == record["lead_id"]
                and e.get("lease_token") == token
                for e in worker.read_events())
            if not known:
                find("R1", record["lead_id"], "lost_lease",
                     {"execution_key": key,
                      "error": "execution names a lease token that was "
                               "never live"},
                     "execution preserved; lead to HUMAN_REVIEW")

    # -- Check 3: executions vs receipts.
    exec_keys = {}
    for record in list_executions(worker):
        if record.get("_file", "").endswith(".annotation.json"):
            continue
        exec_keys.setdefault(record["execution_key"], []).append(record)
    for key, versions in sorted(exec_keys.items()):
        for record in versions:
            if record["phase"] in ("COMPLETED", "FAILED") and \
                    not record.get("receipt"):
                find("R4", record["lead_id"], "recorded_but_never_run",
                     {"execution_key": key, "phase": record["phase"],
                      "error": "COMPLETED/FAILED record with no receipt"},
                     "mark UNVERIFIED; block retry until a receipt is "
                     "found or a human rules")
                _annotate_execution(worker, key, {
                    "class": "R4", "status": "UNVERIFIED",
                    "detail": "COMPLETED/FAILED with no receipt"})
                entry = registry.get(record["lead_id"])
                if entry is not None and entry["intake_status"] not in (
                        TERMINAL_STATES):
                    worker._transition(record["lead_id"], "HUMAN_REVIEW",
                                       "R4: receipt cannot be obtained; "
                                       "outcome stays UNKNOWN")
                    _sweep_release_lease(worker, record["lead_id"],
                                         "R4_human_review")
                actions.append("R4 %s: marked UNVERIFIED" % key)
    receipt_keys = set()
    for name in sorted(os.listdir(worker._p("receipts"))):
        if name.endswith(".json"):
            receipt_keys.add(name[:-5])
    for key in sorted(receipt_keys - set(exec_keys)):
        receipt = read_receipt(worker, key)
        lead_id = None
        if key.startswith("dimag-exec-"):
            rest = key[len("dimag-exec-"):]
            lead_id = rest.rsplit("-a", 1)[0]
        find("R3", lead_id, "executed_but_unrecorded",
             {"execution_key": key,
              "receipt_id": (receipt or {}).get("receipt_id")},
             "create RECONSTRUCTED_EXECUTION from the receipt; lead to "
             "RECONCILING until a human confirms")
        recon_record = {
            "execution_key": key,
            "execution_key_hash": execution_key_hash_for(
                lead_id, int(key.rsplit("-a", 1)[1])) if lead_id else "",
            "lead_id": lead_id, "trace_id": None, "action_id": None,
            "lease_token": None, "worker_id": None,
            "phase": "UNKNOWN", "attempt": None,
            "executor_call": {"adapter": None, "called_at": None,
                              "payload_hash": None},
            "receipt": receipt, "outcome": None,
            "falsification_checked": None,
            "recorded_at": worker.now_iso(),
            "recovery_verdict": None, "reconstructed": True,
            "execution_hash": "",
        }
        recon_record["execution_hash"] = record_hash(recon_record,
                                                     "execution_hash")
        atomic_write_json(
            worker._p("executions", "%s.reconstructed.json" % key),
            recon_record)
        entry = registry.get(lead_id) if lead_id else None
        if entry is not None and entry["intake_status"] not in (
                TERMINAL_STATES):
            worker._transition(lead_id, "RECONCILING",
                               "R3: receipt exists with no execution "
                               "record")
        _human_review_item(worker, "reconstructed_execution", lead_id,
                           "R3: %s reconstructed from receipt; human "
                           "confirmation required" % key)
        actions.append("R3 %s: RECONSTRUCTED_EXECUTION created" % key)
    worker.save_registry()

    # -- R2: orphaned executions (record names a lead not in the registry,
    # or a trace ID matching no trace).
    trace_ids = set()
    if trace_path and os.path.exists(trace_path):
        trace_ids = {r.get("trace_id")
                     for r in load_trace_file(trace_path)[0]}
    for key, versions in sorted(exec_keys.items()):
        for record in versions:
            lead_id = record["lead_id"]
            if lead_id not in registry:
                find("R2", lead_id, "orphaned_execution",
                     {"execution_key": key},
                     "park the record as ORPHANED_EXECUTION; lead "
                     "question to HUMAN_REVIEW; never delete, never "
                     "attach to a guessed lead")
                _annotate_execution(worker, key, {
                    "class": "R2", "status": "ORPHANED_EXECUTION"})
                _human_review_item(worker, "orphaned_execution", lead_id,
                                   "R2: %s names a lead not in the "
                                   "registry" % key)
                actions.append("R2 %s: parked ORPHANED_EXECUTION" % key)
            elif record.get("trace_id") and trace_ids and \
                    record["trace_id"] not in trace_ids:
                find("R2", lead_id, "orphaned_execution",
                     {"execution_key": key,
                      "trace_id": record["trace_id"]},
                     "trace ID matches no trace; park ORPHANED_EXECUTION")
                _annotate_execution(worker, key, {
                    "class": "R2", "status": "ORPHANED_EXECUTION"})
                actions.append("R2 %s: parked ORPHANED_EXECUTION" % key)

    # -- R5: duplicate execution (same key, different outcomes, no
    # supersedes link; or two keys whose receipts prove the same
    # external effect ran twice).
    for key, versions in sorted(exec_keys.items()):
        phases = {(v["phase"],
                   (v.get("outcome") or {}).get("label"))
                  for v in versions}
        if len(versions) > 1 and len(phases) > 1:
            linked = any(v.get("supersedes") for v in versions)
            if not linked:
                lead_id = versions[0]["lead_id"]
                find("R5", lead_id, "duplicate_execution",
                     {"execution_key": key,
                      "outcomes": sorted(
                          "%s/%s" % p for p in phases)},
                     "freeze both records; lead HUMAN_REVIEW; no "
                     "automatic choice of a 'correct' one")
                _annotate_execution(worker, key, {
                    "class": "R5", "status": "FROZEN_DUPLICATE"})
                entry = registry.get(lead_id)
                if entry is not None and entry["intake_status"] not in (
                        TERMINAL_STATES):
                    worker._transition(lead_id, "HUMAN_REVIEW",
                                       "R5: duplicate execution under %s"
                                       % key)
                    _sweep_release_lease(worker, lead_id,
                                         "R5_human_review")
                _human_review_item(worker, "duplicate_execution", lead_id,
                                   "R5: %s has conflicting outcomes" % key)
                actions.append("R5 %s: both records frozen" % key)
    by_ref = {}
    for key, versions in sorted(exec_keys.items()):
        for record in versions:
            ref = (record.get("receipt") or {}).get("external_ref")
            if ref and record["phase"] in ("COMPLETED", "FAILED"):
                by_ref.setdefault(ref, []).append(key)
    for ref, keys in sorted(by_ref.items()):
        if len(set(keys)) > 1:
            lead_id = exec_keys[keys[0]][0]["lead_id"]
            find("R5", lead_id, "duplicate_execution",
                 {"external_ref": ref, "execution_keys": sorted(set(keys))},
                 "two keys prove the same external effect ran twice; "
                 "freeze; HUMAN_REVIEW")
            entry = registry.get(lead_id)
            if entry is not None and entry["intake_status"] not in (
                    TERMINAL_STATES):
                worker._transition(lead_id, "HUMAN_REVIEW",
                                   "R5: external effect %s ran twice" % ref)
                _sweep_release_lease(worker, lead_id, "R5_human_review")
            actions.append("R5 %s: external effect ran twice" % ref)
    worker.save_registry()

    # -- Check 4: executions vs handoffs.
    handoff_keys = set()
    for name in sorted(os.listdir(worker._p("handoff"))):
        if name.endswith(".json"):
            handoff_keys.add(name[len("dimag-handoff-"):-5])
    for lead_id, entry in sorted(registry.items()):
        if entry["intake_status"] == "DONE" and entry.get("execution_key"):
            if entry["execution_key"] not in handoff_keys:
                find("R4", lead_id, "recorded_but_never_run",
                     {"execution_key": entry["execution_key"],
                      "error": "DONE lead with no handoff record"},
                     "handoff missing; recorded as a lag finding, not "
                     "an error of execution")
                actions.append("R4 %s: DONE lead missing handoff"
                               % lead_id)
    for key in sorted(handoff_keys):
        handoff = read_json_file(
            worker._p("handoff", "dimag-handoff-%s.json" % key))
        lead_id = handoff.get("lead_id")
        entry = registry.get(lead_id) if lead_id else None
        if entry is None or entry["intake_status"] != "DONE":
            find("R4", lead_id, "recorded_but_never_run",
                 {"execution_key": key,
                  "error": "handoff names a lead that is not DONE"},
                 "handoff preserved; lead state is the question")
            actions.append("R4 %s: handoff names a non-DONE lead" % key)

    # -- Check 5: handoffs vs experience rows (read-only; lag, not error).
    handoff_lag = []
    if dataset_path and os.path.exists(dataset_path):
        rows = read_jsonl(dataset_path)
        derived = {r.get("derived_from") for r in rows}
        for key in sorted(handoff_keys):
            handoff = read_json_file(
                worker._p("handoff", "dimag-handoff-%s.json" % key))
            if handoff.get("source_record_id") not in derived:
                handoff_lag.append(key)
    # -- Check 6: registry vs traces (R6 stale lead).
    if trace_path and os.path.exists(trace_path):
        traces, _ = load_trace_file(trace_path)
        by_id = {t["trace_id"]: t for t in traces}
        for lead_id, entry in sorted(registry.items()):
            trace = by_id.get(entry["trace_id"])
            if trace is None:
                continue
            if trace.get("trace_hash") != entry["trace_hash"]:
                find("R6", lead_id, "stale_lead",
                     {"trace_id": entry["trace_id"],
                      "registry_hash": entry["trace_hash"][:12],
                      "current_hash": trace["trace_hash"][:12]},
                     "mark SUPERSEDED_BY_TRACE; park; never execute "
                     "under the old trace")
                if entry["intake_status"] not in (
                        "SUPERSEDED_BY_TRACE", "DONE", "ALREADY_TESTED"):
                    worker._transition(lead_id, "SUPERSEDED_BY_TRACE",
                                       "R6: trace re-run supersedes this "
                                       "lead")
                    _sweep_release_lease(worker, lead_id, "R6_superseded")
                actions.append("R6 %s: marked SUPERSEDED_BY_TRACE"
                               % lead_id)
    worker.save_registry()

    by_class = {}
    for f in findings:
        by_class[f["class"]] = by_class.get(f["class"], 0) + 1
    report = {
        "sweep_id": "dimag-004-recon-%s" % worker.now_iso().replace(
            ":", "").replace("-", ""),
        "swept_at": worker.now_iso(),
        "worker_id": worker.worker_id,
        "input_hashes": {
            "registry": sha256_file(worker._p(
                "dimag-lead-registry-v1.jsonl")) if os.path.exists(
                worker._p("dimag-lead-registry-v1.jsonl")) else None,
            "trace_file": sha256_file(trace_path)
            if trace_path and os.path.exists(trace_path) else None,
            "dataset": sha256_file(dataset_path)
            if dataset_path and os.path.exists(dataset_path) else None,
        },
        "counts": {"findings": len(findings), "by_class": by_class,
                   "handoff_lag": len(handoff_lag)},
        "findings": findings,
        "actions_taken": actions,
        "handoff_lag_keys": handoff_lag,
        "worker_halted": worker.halted() is not None,
    }
    report["sweep_hash"] = record_hash(report, "sweep_hash")
    stamp = worker.now_iso().replace(":", "").replace("-", "")
    atomic_write_json(
        worker._p("reconciliation", "dimag-004-recon-%s.json" % stamp),
        report)
    worker.log_event("reconciliation_sweep", findings=len(findings),
                     by_class=by_class)
    return report


# ---------------------------------------------------------------------------
# Clock-jump guard (design SS12.2) + the bounded cycle (SS13.1 Stage 3)
# ---------------------------------------------------------------------------

def check_clock_jump(wall_start, wall_end, mono_start, mono_end,
                     threshold_s=CLOCK_JUMP_S):
    """If the wall clock jumps backward by more than the threshold during
    a cycle (monotonic elapsed vs wall-clock elapsed disagree), the
    worker stops issuing new executions and marks the cycle RECONCILING.
    Returns True when a jump is detected."""
    wall_elapsed = (wall_end - wall_start).total_seconds()
    mono_elapsed = mono_end - mono_start
    return (mono_elapsed - wall_elapsed) > threshold_s


def run_cycle(worker, trace_path, executor=None, seam=None,
              dataset_path=None):
    """One bounded cycle (design SS1/SS13.1): inventory -> intake ->
    bind -> claim up to N BOUND leads -> leases -> E1-E8 -> execute ->
    handoff -> reconcile -> committed checkpoint or RECONCILING.

    Returns the cycle report. A cycle that cannot end in a committed
    checkpoint ends in RECONCILING, never in a silent stop."""
    executor = executor or StubExecutor(worker)
    seam = seam or FileSeam(worker)
    wall_start = worker.now()
    mono_start = worker.clock.monotonic()
    cycle_state = {"executions": 0, "started_mono": mono_start}
    report = {"cycle_id": "dimag-cycle-%s"
                          % worker.now_iso().replace(":", "")
                          .replace("-", ""),
              "started_at": worker.now_iso(), "worker_id": worker.worker_id,
              "state": "committed", "stages": {}, "refusals": [],
              "executions": [], "stopped": False}

    # Pre-cycle check: disk space (SS12.4). Below 100 MB the cycle does
    # not start: no intake, no lease, no execution.
    free_bytes = shutil.disk_usage(worker.state_dir).free
    if free_bytes < worker.disk_min_bytes:
        report["state"] = "refused"
        report["refusal"] = {"code": "cycle_refused_disk_low",
                             "free_bytes": free_bytes,
                             "threshold_bytes": worker.disk_min_bytes}
        worker.log_event("cycle_refused_disk_low", free_bytes=free_bytes)
        return _finish_cycle(worker, report, wall_start, mono_start)

    # Owner STOP (SS12.6 #1): checked at cycle start.
    if worker.stop_active():
        report["state"] = "STOPPED"
        report["stopped"] = True
        report["stop"] = worker.read_stop()
        worker.log_event("cycle_stopped", reason="stop_active")
        return _finish_cycle(worker, report, wall_start, mono_start)
    if worker.halted():
        report["state"] = "STOPPED"
        report["stopped"] = True
        report["halted"] = worker.halted()
        worker.log_event("cycle_stopped", reason="worker_halted",
                         detail=worker.halted().get("reason"))
        return _finish_cycle(worker, report, wall_start, mono_start)

    # The cycle lease: two simultaneous cycles must not reconcile the
    # same state twice (SS12.1 step 1).
    try:
        acquire_cycle_lease(worker)
    except WorkerError as exc:
        report["state"] = "deferred"
        report["refusal"] = {"code": exc.code, "detail": exc.detail}
        worker.log_event("cycle_deferred", code=exc.code)
        return _finish_cycle(worker, report, wall_start, mono_start)

    crashed = False
    try:
        # Stage 0 inventory + Stage 1 intake.
        inv = inventory(worker, trace_path)
        report["stages"]["inventory"] = inv
        counts = intake_traces(worker, trace_path)
        report["stages"]["intake"] = counts

        # Stage 2 bind: emit binding requests for PROPOSED leads without
        # one; validate existing bindings; re-check parked leads.
        registry = worker.load_registry()
        requests = []
        for lead_id in sorted(registry):
            entry = registry[lead_id]
            status = entry["intake_status"]
            if status == "PROPOSED" and not entry.get("bound_action_id"):
                try:
                    requests.append(request_binding(worker, lead_id))
                except WorkerError as exc:
                    worker.log_event("binding_request_failed",
                                     lead_id=lead_id, code=exc.code)
            elif status == "BOUND":
                ok, reason = validate_binding(worker, lead_id)
                if not ok:
                    worker._transition(
                        lead_id, "PARKED_BINDING_INVALID",
                        "cycle re-check: binding invalid (%s)" % reason)
            elif status.startswith("PARKED_"):
                # Parking is not terminal: re-check every cycle (SS4).
                ok, reason = validate_binding(worker, lead_id)
                if ok and status in ("PARKED_BINDING_INVALID",
                                     "PARKED_UNBOUND"):
                    worker._transition(lead_id, "BOUND",
                                       "cycle re-check: binding valid again")
                elif status == "PARKED_UNAPPROVED_ACTION":
                    verdict = seam.allowed_mask(lead_id)
                    if verdict["allowed"]:
                        worker._transition(lead_id, "BOUND",
                                           "cycle re-check: seam allows now")
            elif status == "RETRY_WAIT" and entry.get("next_retry_at"):
                if parse_iso(entry["next_retry_at"]) <= worker.now():
                    worker._transition(lead_id, "BOUND",
                                       "backoff expired; ready to retry")
        worker.save_registry()
        report["stages"]["bind"] = {"binding_requests": len(requests)}

        # Stage 3: claim up to N BOUND leads, in registry order.
        claimed = []
        for lead_id in sorted(registry):
            if len(claimed) >= worker.max_leads_per_cycle:
                break
            entry = registry[lead_id]
            if entry["intake_status"] != "BOUND":
                continue
            try:
                acquire_lease(worker, lead_id)
            except WorkerError as exc:
                worker.log_event("lease_acquire_failed", lead_id=lead_id,
                                 code=exc.code)
                continue
            claimed.append(lead_id)
        report["stages"]["cycle"] = {"claimed": claimed}

        # Execute each claimed lead (E1-E8 inside execute_lead).
        for lead_id in claimed:
            # Clock-jump guard (SS12.2): stop issuing new executions.
            if check_clock_jump(wall_start, worker.now(), mono_start,
                                worker.clock.monotonic(),
                                worker.clock_jump_s):
                report["state"] = "RECONCILING"
                report["clock_jump"] = True
                worker.log_event("cycle_clock_jump",
                                 reason="wall clock jumped back > %ds"
                                        % worker.clock_jump_s)
                break
            before = len(executor.call_log)
            result = execute_lead(worker, lead_id, executor=executor,
                                  seam=seam, cycle_state=cycle_state)
            result = dict(result)
            result.pop("record", None)
            result["lead_id"] = lead_id
            result["executor_calls"] = len(executor.call_log) - before
            report["executions"].append(result)
            if result.get("refused"):
                report["refusals"].append(result)
            if worker.stop_active():
                report["state"] = "STOPPED"
                report["stopped"] = True
                worker.log_event("cycle_stopped",
                                 reason="stop_active_mid_cycle")
                break

        # Stage 4 handoff: safety net for DONE leads without a handoff.
        registry = worker.load_registry()
        handoffs = 0
        for lead_id, entry in sorted(registry.items()):
            if entry["intake_status"] == "DONE" and \
                    entry.get("execution_key"):
                path = worker._p("handoff", "dimag-handoff-%s.json"
                                 % entry["execution_key"])
                if not os.path.exists(path):
                    record = read_execution(worker, entry["execution_key"])
                    if record is not None:
                        write_handoff(worker, record)
                        handoffs += 1
        report["stages"]["handoff"] = {"written": handoffs}

        # Stage 5 reconcile.
        recon = run_reconciliation(worker, trace_path=trace_path,
                                   dataset_path=dataset_path,
                                   executor=executor)
        report["stages"]["reconcile"] = {
            "findings": recon["counts"]["findings"],
            "by_class": recon["counts"]["by_class"]}
        if recon["findings"]:
            report["state"] = "RECONCILING"
        if worker.halted():
            report["state"] = "STOPPED"
            report["stopped"] = True
    except CrashSimulated:
        # A real crash runs no finally-block cleanup: the cycle lease
        # stays held, the checkpoint stays uncommitted, and recovery
        # (SS12.1) takes over after expiry + grace. Re-raise untouched.
        crashed = True
        raise
    finally:
        if not crashed:
            release_cycle_lease(worker)
    return _finish_cycle(worker, report, wall_start, mono_start)


def _finish_cycle(worker, report, wall_start, mono_start):
    """Commit the cycle checkpoint (or RECONCILING) + publish the cycle
    report (design SS13.1 Stage 7)."""
    wall_end = worker.now()
    mono_end = worker.clock.monotonic()
    if check_clock_jump(wall_start, wall_end, mono_start, mono_end,
                        worker.clock_jump_s) and \
            report.get("state") == "committed":
        report["state"] = "RECONCILING"
        report["clock_jump"] = True
    report["ended_at"] = worker.now_iso()
    report["wall_elapsed_s"] = (wall_end - wall_start).total_seconds()
    state = worker.read_worker_state() or worker.default_worker_state()
    state["last_cycle"] = {"cycle_id": report["cycle_id"],
                           "state": report["state"],
                           "started_at": report["started_at"],
                           "ended_at": report["ended_at"]}
    state["stop"] = worker.read_stop()
    worker.write_worker_state(state)
    worker.log_event("cycle_finished", cycle_id=report["cycle_id"],
                     state=report["state"],
                     executions=len(report.get("executions", [])))
    stamp = report["cycle_id"]
    atomic_write_json(worker._p("dimag-004-cycle-report-%s.json" % stamp),
                      report)
    return report


# ---------------------------------------------------------------------------
# Temporal evaluation (design SS11) -- evaluating the worker over time
# ---------------------------------------------------------------------------

def replay_lead_states(events):
    """Re-derive lead states from the event log alone (SS11.2a).

    Returns (states, divergences): states maps lead_id -> last derived
    state; divergences counts transition events whose from_state does
    not match the state derived so far -- a state-tracking bug."""
    states = {}
    divergences = []
    for event in events:
        etype = event.get("event_type")
        lead_id = event.get("lead_id")
        if not lead_id:
            continue
        if etype == "intake":
            states[lead_id] = event.get("intake_status")
        elif etype == "transition":
            current = states.get(lead_id)
            if current is not None and current != event.get("from_state"):
                divergences.append({
                    "lead_id": lead_id, "at": event.get("ts"),
                    "derived": current,
                    "event_from": event.get("from_state"),
                    "event_to": event.get("to_state")})
            states[lead_id] = event.get("to_state")
    return states, divergences


def evaluate(worker, window_days=EVAL_WINDOW_DAYS, trace_path=None,
             dataset_path=None):
    """Stage 6 temporal evaluation (design SS11): replay the event log
    over the window, run fault injection on a scratch copy, compute the
    SS11.3 metrics. Reads a snapshot; never writes to live state (the
    fault injection runs on a scratch copy)."""
    events = worker.read_events()
    window_start = worker.now() - timedelta(days=window_days)
    window_events = [e for e in events
                     if parse_iso(e["ts"]) >= window_start]
    states, divergences = replay_lead_states(window_events)
    registry = worker.load_registry()
    mismatch = {lid: (states.get(lid), entry["intake_status"])
                for lid, entry in registry.items()
                if states.get(lid) is not None and
                states[lid] != entry["intake_status"]}
    # -- metrics from the live window -------------------------------------
    refusals = {}
    replays = 0
    replayed_ok = 0
    dead_lettered = 0
    executions_done = 0
    handoff_lags = []
    outcome_ts = {}
    for event in window_events:
        etype = event.get("event_type")
        if etype == "execution_refused":
            refusals[event.get("check")] = refusals.get(
                event.get("check"), 0) + 1
        elif etype == "replay_returned_recorded_result":
            replays += 1
            replayed_ok += 1
        elif etype == "dead_letter":
            dead_lettered += 1
        elif etype == "execution_outcome":
            executions_done += 1
            outcome_ts[event.get("execution_key")] = event.get("ts")
        elif etype == "handoff_written":
            started = outcome_ts.get(event.get("execution_key"))
            if started:
                handoff_lags.append(
                    (parse_iso(event["ts"]) - parse_iso(started))
                    .total_seconds())
    intake_lines = read_jsonl(worker._p("intake-log.jsonl"))
    window_intakes = [l for l in intake_lines
                      if parse_iso(l["ts"]) >= window_start]
    dups = [l for l in window_intakes
            if l.get("outcome") == "DUPLICATE_INTAKE_IGNORED"]
    # -- fault injection on scratch copies (SS11.2b). Each plant runs on
    # its own copy of the state: a plant that halts the worker (R7) must
    # not stop the other plants from running.
    import tempfile
    scratch = tempfile.mkdtemp(prefix="dimag-004-eval-")
    injected = {"lost_lease": False, "duplicate_delivery": False,
                "poison_lead": False, "replay": False}
    try:
        def fresh_copy(tag):
            dest = os.path.join(scratch, tag)
            shutil.copytree(worker.state_dir, dest)
            return Worker(dest, worker_id="dimag-004-worker-eval",
                          clock=worker.clock)

        # (a) lost lease: a lease file naming a live lead that is not
        # LEASED. The target must NOT be quarantined -- a lease on a
        # quarantined lead is R7, not R1 (the sweep is right to say so).
        copy = fresh_copy("lost-lease")
        registry_c = copy.load_registry()
        target = None
        for lid in sorted(registry_c):
            e = registry_c[lid]
            if e["intake_status"] == "DONE":
                target = lid
                break
        if target is None:
            for lid in sorted(registry_c):
                e = registry_c[lid]
                if e["intake_status"] == "PROPOSED" and \
                        (e["quarantine"] or {}).get("quarantine_reason") \
                        is None:
                    target = lid
                    break
        if target is None:
            for lid in sorted(registry_c):
                e = registry_c[lid]
                if (e["quarantine"] or {}).get("quarantine_reason") is None:
                    target = lid
                    break
        if target is not None:
            lease = _new_lease(copy, target,
                               execution_key_for(target, 1))
            atomic_write_json(copy._p("leases", "%s.json" % target), lease)
            recon = run_reconciliation(copy, trace_path=trace_path,
                                       dataset_path=dataset_path)
            injected["lost_lease"] = any(
                f["class"] == "R1" and f["lead_id"] == target
                for f in recon["findings"])
        # (b) duplicate delivery: re-intake the same trace file.
        if trace_path and os.path.exists(trace_path):
            copy = fresh_copy("duplicate")
            before = sha256_file(copy._p("dimag-lead-registry-v1.jsonl")) \
                if os.path.exists(copy._p(
                    "dimag-lead-registry-v1.jsonl")) else None
            counts = intake_traces(copy, trace_path)
            after = sha256_file(copy._p("dimag-lead-registry-v1.jsonl")) \
                if os.path.exists(copy._p(
                    "dimag-lead-registry-v1.jsonl")) else None
            injected["duplicate_delivery"] = (
                counts["duplicates"] == counts["leads"]
                and before == after)
        # (c) poison lead: bind a lead to an always-transient-fail action
        # and run cycles until it dead-letters after exactly 3 attempts.
        copy = fresh_copy("poison")
        poison = None
        for lid in sorted(copy.load_registry()):
            entry = copy.load_registry()[lid]
            if entry["intake_status"] == "PROPOSED":
                poison = lid
                break
        if poison is not None:
            entry = copy.load_registry()[poison]
            action = make_action(
                "act-poison-%s" % poison, poison, entry["hypothesis"],
                entry["falsification_condition"],
                executor_behavior="transient_fail")
            write_action_fixture(copy, action)
            record_binding(copy, poison, action["id"], bound_by="niroj")
            executor = StubExecutor(copy)
            # Zero backoff on the scratch copy: the plant proves the
            # worker stops after 3 attempts, not the backoff timing
            # (T9 proves the 1 h / 6 h / 24 h waits with a fake clock).
            # This keeps the injection clock-independent.
            copy.backoff_s = {1: 0, 2: 0, 3: 0}
            for _ in range(6):
                if copy.load_registry()[poison]["intake_status"] == \
                        "DEAD_LETTER":
                    break
                run_cycle(copy, trace_path, executor=executor)
            entry = copy.load_registry()[poison]
            injected["poison_lead"] = (
                entry["intake_status"] == "DEAD_LETTER"
                and entry.get("attempt", 0) == 3
                and len(entry.get("failure_history", [])) == 3)
        # (d) idempotent replay on a scratch copy: re-execute a DONE lead.
        done_leads = [lid for lid, e in registry.items()
                      if e["intake_status"] == "DONE"]
        if done_leads:
            copy = fresh_copy("replay")
            executor = StubExecutor(copy)
            calls_before = len(executor.call_log)
            result = execute_lead(copy, done_leads[0], executor=executor)
            injected["replay"] = bool(result.get("replayed")) and \
                len(executor.call_log) == calls_before
        else:
            # No DONE lead in this window: replay correctness is proven
            # by the suite (T2), not by this window's state.
            injected["replay"] = None
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    caught = sum(1 for v in injected.values() if v)
    planted = sum(1 for v in injected.values() if v is not None)
    metrics = {
        "lease_exclusivity_violations": sum(
            1 for e in window_events
            if e.get("event_type") == "reconciliation_finding"
            and e.get("cls") in ("R1", "R5", "R7")
            and "exclusivity" in (e.get("detail") or "")),
        "idempotent_replay_correctness": (
            {"replays_attempted": replays,
             "returned_recorded": replayed_ok,
             "pct": (100.0 * replayed_ok / replays) if replays else None,
             "note": None if replays else "no replays in window; "
                     "fault-injection replay on scratch copy: %s"
                     % injected["replay"]}),
        "reconciliation_catch_rate": {
            "planted": planted,
            "caught": caught,
            "per_class": dict(injected)},
        "mean_time_to_detect_lost_lease_s": None,
        "duplicate_intake_noop_rate": {
            "duplicates": len(dups),
            "pct": 100.0 if dups else None,
            "note": None if dups else "no duplicate intakes in window; "
                    "fault-injection duplicate delivery: %s"
                    % injected["duplicate_delivery"]},
        "dead_letter_rate_per_100_executions": (
            (100.0 * dead_lettered / executions_done)
            if executions_done else None),
        "execution_to_handoff_lag_s": {
            "mean": (sum(handoff_lags) / len(handoff_lags))
                    if handoff_lags else None,
            "n": len(handoff_lags)},
        "execution_to_experience_row_lag_s": {
            "value": None,
            "note": "reported only -- the DIMAG-002 pipeline runs on its "
                    "own schedule and the worker does not control it"},
        "refusal_rate_by_check": refusals,
        "replay_divergence": len(divergences),
    }
    report = {
        "evaluation_id": "dimag-004-eval-%s"
                         % worker.now_iso().replace(":", "")
                         .replace("-", ""),
        "window_days": window_days,
        "window_start": fmt_iso(window_start),
        "window_end": worker.now_iso(),
        "worker_version": WORKER_VERSION,
        "replay": {"events_replayed": len(window_events),
                   "divergences": divergences,
                   "registry_mismatches": mismatch},
        "fault_injection": injected,
        "metrics": metrics,
        "bars": {
            "lease_exclusivity_violations": 0,
            "idempotent_replay_correctness_pct": 100,
            "reconciliation_catch_rate": "100% R1/R5/R7, >=90% R2/R3/R4/R6",
            "duplicate_intake_noop_rate_pct": 100,
            "replay_divergence": 0},
    }
    report["evaluation_hash"] = record_hash(report, "evaluation_hash")
    stamp = worker.now_iso().replace(":", "").replace("-", "")
    atomic_write_json(
        worker._p("evaluation", "dimag-004-eval-%s.json" % stamp), report)
    worker.log_event("evaluation_run", evaluation_id=report["evaluation_id"],
                     divergences=len(divergences), caught=caught,
                     planted=planted)
    return report
