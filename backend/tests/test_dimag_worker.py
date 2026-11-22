"""DIMAG-004 acceptance tests (design SS14) -- T0 + T1-T12, plus the
Mac/ForgeOS-port additions T13-T15 (field seam + live-row hook).

Mac / ForgeOS port (22 Nov 2026): the reference test file ported into
backend/tests/. T0-T12 are the reference tests unchanged in behavior
(only the import and the trace/dataset/result paths changed). T13-T15
cover the Mac additions: ForgeOSSeam verdicts, the live-row reader,
and the action_reader hook end to end through execute_lead.

Standalone, no pytest: run `python3 tests/test_dimag_worker.py` with
backend/ on PYTHONPATH (or run under pytest from the repo root, like
test_dimag_feature_builder.py). By default, tests use a generated,
explicitly TEST-only trace/dataset fixture with the same IDs needed by the
acceptance scenarios. To run against the private local v1 corpus, set both
DIMAG004_TRACE_PATH and DIMAG004_DATASET_PATH explicitly. Every test runs
against scratch state (tempfile) with a controllable FakeClock and stub
governance seam / executor; no test sends external actions.

A version passes only if ALL tests pass. No test is weakened to make it
pass: a failing criterion is reported as failed with the evidence.
"""

import atexit
import json
import os
import shutil
import sys
import tempfile

from app.services.dimag import field_seam
from app.services.dimag import worker as wmod
from app.services.dimag.worker import (Worker, FakeClock, WorkerError, CrashSimulated,
                    StubExecutor, FileSeam, execution_key_for,
                    execution_key_hash_for, record_hash, canonical_json,
                    sha256_file, sha256_text, parse_iso)

# Optional private v1-corpus paths; tests default to synthetic TEST inputs.
TRACE_OVERRIDE = os.environ.get("DIMAG004_TRACE_PATH")
DATASET_OVERRIDE = os.environ.get("DIMAG004_DATASET_PATH")


def _write_synthetic_test_inputs():
    """Create hermetic TEST-only inputs, separate from the private corpus."""
    root = tempfile.mkdtemp(prefix="dimag-004-test-inputs-")
    trace_path = os.path.join(root, "synthetic-traces.jsonl")
    dataset_path = os.path.join(root, "synthetic-dataset.jsonl")
    quarantined = {1, 2, 3, 4, 5, 9, 13, 14}
    held = {6, 8, 17, 19, 20}
    records = []
    dataset = []
    for index in range(1, 21):
        trace_id = "dimag-trace-%06d" % index
        source_record_id = "test-source-%06d" % index
        confidence = ("UNKNOWN" if index == 7 else
                      "HYPOTHESIS" if index in held else "PROVEN")
        lead = None
        if index != 7:
            lead = {
                "lead_id": "dimag-lead-%06d" % index,
                "derived_from": trace_id,
                "hypothesis": "TEST-only hypothesis %06d" % index,
                "falsification_condition":
                    "TEST-only falsification condition %06d" % index,
                "cost": "TEST-only",
                "parent_gate": "TEST-only",
                "quarantine_inherited": {
                    "training_rights": "TEST_ONLY",
                    "label_trust": "TEST_ONLY",
                    "quarantine_reason": (
                        "TEST-only fixture quarantine"
                        if index in quarantined else None),
                },
            }
            if index == 1:
                lead["already_tested_by"] = "TEST-only fixture"
        trace = {
            "trace_version": wmod.TRACE_VERSION,
            "trace_id": trace_id,
            "source_record_id": source_record_id,
            "source_record_sha256": wmod.sha256_text(source_record_id),
            "source_domain": "TEST_SYNTHETIC",
            "combined": {
                "confidence": confidence,
                "cause_class": "TEST_SYNTHETIC",
            },
            "diagnostic_lead": lead,
        }
        trace["trace_hash"] = wmod.recompute_trace_hash(trace)
        records.append(trace)
        dataset.append({
            "record_id": "test-experience-%06d" % index,
            "derived_from": source_record_id,
            "evidence_class": "TEST",
        })
    with open(trace_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(wmod.canonical_json(row) for row in records)
                 + "\n")
    with open(dataset_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(wmod.canonical_json(row) for row in dataset)
                 + "\n")
    # Keep generated inputs for this process only.
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    return trace_path, dataset_path


if TRACE_OVERRIDE is not None or DATASET_OVERRIDE is not None:
    if not TRACE_OVERRIDE or not DATASET_OVERRIDE:
        raise ValueError(
            "set both DIMAG004_TRACE_PATH and DIMAG004_DATASET_PATH")
    TRACE_PATH, DATASET_PATH = TRACE_OVERRIDE, DATASET_OVERRIDE
else:
    TRACE_PATH, DATASET_PATH = _write_synthetic_test_inputs()

CLOCK_START = "2026-11-22T04:00:00Z"

RESULTS = []


def check(name, ok, evidence=""):
    RESULTS.append({"test": name, "passed": bool(ok), "evidence": evidence})
    print("%s %s %s" % ("PASS" if ok else "FAIL", name,
                        ("-- " + evidence) if evidence else ""))
    return ok


def require_check(name, ok, evidence=""):
    passed = check(name, ok, evidence)
    if not passed:
        raise AssertionError("Acceptance check failed: %s" % name)


def fresh_worker():
    tmp = tempfile.mkdtemp(prefix="dimag-004-test-")
    clock = FakeClock(CLOCK_START)
    worker = Worker(tmp, worker_id="dimag-004-worker-01", clock=clock)
    return tmp, clock, worker


def intake(worker):
    return wmod.intake_traces(worker, TRACE_PATH)


def bind_lead(worker, lead_id, **kwargs):
    """Bind a lead to a schematic fixture Action (design SS14)."""
    entry = worker.load_registry()[lead_id]
    action = wmod.make_action("act-%s" % lead_id, lead_id,
                              entry["hypothesis"],
                              entry["falsification_condition"], **kwargs)
    wmod.write_action_fixture(worker, action)
    return wmod.record_binding(worker, lead_id, action["id"],
                               bound_by="niroj")


def execute_bound(worker, lead_id, executor=None):
    """Acquire a lease and execute; returns the execute_lead result."""
    wmod.acquire_lease(worker, lead_id)
    return wmod.execute_lead(worker, lead_id,
                             executor=executor or StubExecutor(worker))


def plant_execution_record(worker, lead_id, key, phase, outcome_label,
                           receipt=True, lease_token="planted-token",
                           trace_id=None, external_ref=None):
    """Write an execution record directly (for reconciliation plants).
    The record is hash-valid; only its provenance is planted."""
    entry = worker.load_registry().get(lead_id) or {}
    record = {
        "execution_key": key,
        "execution_key_hash": execution_key_hash_for(
            lead_id, int(key.rsplit("-a", 1)[1])),
        "lead_id": lead_id,
        "trace_id": trace_id or entry.get("trace_id"),
        "action_id": entry.get("bound_action_id"),
        "lease_token": lease_token,
        "worker_id": "dimag-004-worker-01",
        "phase": phase,
        "attempt": int(key.rsplit("-a", 1)[1]),
        "executor_call": {"adapter": "stub-adapter",
                          "called_at": "2026-11-22T04:00:00Z",
                          "payload_hash": sha256_text("planted")},
        "receipt": ({"receipt_id": "dimag-rcpt-planted",
                     "received_at": "2026-11-22T04:00:00Z",
                     "external_ref": external_ref or ("stub-external-%s"
                                                       % key),
                     "outcome_label": outcome_label}
                    if receipt else None),
        "outcome": ({"label": outcome_label, "actual_value": None,
                     "unit": None, "observed_at": "2026-11-22T04:00:00Z",
                     "qualitative_result": "planted outcome"}
                    if phase in ("COMPLETED", "FAILED") else None),
        "falsification_checked": ({"condition": "planted",
                                   "result": "not_checkable"}
                                  if phase in ("COMPLETED", "FAILED")
                                  else None),
        "recorded_at": "2026-11-22T04:00:00Z",
        "recovery_verdict": None,
        "reconstructed": False,
        "execution_hash": "",
    }
    record["execution_hash"] = record_hash(record, "execution_hash")
    wmod.write_execution_record(worker, record)
    return record


# ---------------------------------------------------------------------------
# T0 -- smoke: the worker runs, intake works, registry is created
# ---------------------------------------------------------------------------

def test_t0():
    tmp, clock, worker = fresh_worker()
    try:
        inv = wmod.inventory(worker, TRACE_PATH)
        counts = intake(worker)
        ok = (inv["status"] == "OK" and inv["leads"] == 19
              and counts["intaked"] == 19
              and os.path.exists(os.path.join(
                  tmp, "dimag-lead-registry-v1.jsonl")))
        return require_check("T0 worker runs", ok,
                     "inventory leads=%d intaked=%d"
                     % (inv["leads"], counts["intaked"]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# T1 -- intake reproduces the worked intake (design SS3.3)
# ---------------------------------------------------------------------------

def test_t1():
    tmp, clock, worker = fresh_worker()
    try:
        counts = intake(worker)
        registry = worker.load_registry()
        by_status = {}
        for entry in registry.values():
            by_status[entry["intake_status"]] = \
                by_status.get(entry["intake_status"], 0) + 1
        expected = {"ALREADY_TESTED": 1, "QUARANTINED": 7,
                    "PROPOSED_HELD": 5, "PROPOSED": 6}
        ok = (len(registry) == 19 and by_status == expected
              and registry["dimag-lead-000001"]["intake_status"]
              == "ALREADY_TESTED"
              and {lid for lid, e in registry.items()
                   if e["intake_status"] == "QUARANTINED"}
              == {"dimag-lead-000002", "dimag-lead-000003",
                  "dimag-lead-000004", "dimag-lead-000005",
                  "dimag-lead-000009", "dimag-lead-000013",
                  "dimag-lead-000014"}
              and {lid for lid, e in registry.items()
                   if e["intake_status"] == "PROPOSED_HELD"}
              == {"dimag-lead-000006", "dimag-lead-000008",
                  "dimag-lead-000017", "dimag-lead-000019",
                  "dimag-lead-000020"}
              and {lid for lid, e in registry.items()
                   if e["intake_status"] == "PROPOSED"}
              == {"dimag-lead-000010", "dimag-lead-000011",
                  "dimag-lead-000012", "dimag-lead-000015",
                  "dimag-lead-000016", "dimag-lead-000018"})
        # Every entry's trace_hash must recompute.
        hashes_ok = all(
            wmod.recompute_trace_hash(
                next(r for r in wmod.load_trace_file(TRACE_PATH)[0]
                     if r["trace_id"] == e["trace_id"]))
            == e["trace_hash"] for e in registry.values())
        # Zero leads BOUND, zero leased, zero executed.
        zero = (counts["intaked"] == 19
                and not os.listdir(os.path.join(tmp, "leases"))
                and not os.listdir(os.path.join(tmp, "executions")))
        return require_check("T1 worked intake", ok and hashes_ok and zero,
                     "by_status=%s hashes_recompute=%s zero_bound_leased_"
                     "executed=%s" % (json.dumps(by_status, sort_keys=True),
                                       hashes_ok, zero))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# T2 -- idempotent re-execution (design SS7.2)
# ---------------------------------------------------------------------------

def test_t2():
    tmp, clock, worker = fresh_worker()
    try:
        intake(worker)
        bind_lead(worker, "dimag-lead-000010")
        executor = StubExecutor(worker)
        first = execute_bound(worker, "dimag-lead-000010",
                              executor=executor)
        calls_after_first = len(executor.call_log)
        records_after_first = sorted(os.listdir(
            os.path.join(tmp, "executions")))
        # Invoke the execution again with the same key.
        second = wmod.execute_lead(worker, "dimag-lead-000010",
                                   executor=executor)
        calls_after_second = len(executor.call_log)
        records_after_second = sorted(os.listdir(
            os.path.join(tmp, "executions")))
        ok = (first.get("completed") and second.get("replayed")
              and calls_after_first == 1 and calls_after_second == 1
              and records_after_first == records_after_second
              and second["record"]["phase"] == "COMPLETED"
              and worker.load_registry()["dimag-lead-000010"]
              ["intake_status"] == "DONE")
        return require_check("T2 idempotent re-execution", ok,
                     "calls=%d->%d records=%d->%d replayed=%s"
                     % (calls_after_first, calls_after_second,
                        len(records_after_first),
                        len(records_after_second), second.get("replayed")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# T3 -- lease exclusivity under two workers (design SS6.2/SS6.3)
# ---------------------------------------------------------------------------

def test_t3():
    tmp, clock, worker_a = fresh_worker()
    try:
        intake(worker_a)
        bind_lead(worker_a, "dimag-lead-000010")
        worker_b = Worker(tmp, worker_id="dimag-004-worker-02",
                          clock=clock)
        lease_a = wmod.acquire_lease(worker_a, "dimag-lead-000010")
        try:
            wmod.acquire_lease(worker_b, "dimag-lead-000010")
            held = "NO-ERROR"
        except WorkerError as exc:
            held = exc.code
        ok_held = held == "lease_held_by_dimag-004-worker-01"
        # Expire the first lease, take over INSIDE the 60 s grace:
        # must be refused.
        clock.advance(wmod.LEASE_DURATION_S + 10)
        try:
            wmod.takeover_lease(worker_b, "dimag-lead-000010")
            grace = "NO-ERROR"
        except WorkerError as exc:
            grace = exc.code
        ok_grace = grace == "lease_takeover_grace"
        # After the grace, takeover succeeds with a new token.
        clock.advance(wmod.TAKEOVER_GRACE_S + 10)
        lease_b = wmod.takeover_lease(worker_b, "dimag-lead-000010")
        ok_takeover = (lease_b["lease_token"] != lease_a["lease_token"]
                       and lease_b["worker_id"] == "dimag-004-worker-02")
        # An executor call presenting the old token is refused.
        executor = StubExecutor(worker_b)
        try:
            executor.call(worker_b, "dimag-lead-000010",
                          execution_key_for("dimag-lead-000010", 1),
                          lease_a["lease_token"], {})
            stale = "NO-ERROR"
        except WorkerError as exc:
            stale = exc.code
        ok_stale = stale == "exec_refused_stale_token"
        ok = ok_held and ok_grace and ok_takeover and ok_stale
        return require_check("T3 lease exclusivity", ok,
                     "held=%s grace=%s new_token=%s stale=%s"
                     % (held, grace, ok_takeover, stale))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# T4 -- expired-lease takeover + resume equivalence (design SS6.4/SS12.1)
# ---------------------------------------------------------------------------

def _crash_free_run():
    """A crash-free run of lead 000011 to COMPLETED. Returns the state
    dir + worker + executor for comparison."""
    tmp, clock, worker = fresh_worker()
    intake(worker)
    bind_lead(worker, "dimag-lead-000011")
    executor = StubExecutor(worker)
    wmod.run_cycle(worker, TRACE_PATH, executor=executor)
    return tmp, clock, worker, executor


def test_t4():
    # Crash-free reference run.
    ref_tmp, _, ref_worker, _ = _crash_free_run()
    try:
        ref_entry = ref_worker.load_registry()["dimag-lead-000011"]
        ref_done = ref_entry["intake_status"] == "DONE"
        ref_handoff = wmod.read_json_file(os.path.join(
            ref_tmp, "handoff",
            "dimag-handoff-%s.json" % ref_entry["execution_key"]))
    finally:
        pass

    # Crash run: worker A leases + writes intent, then dies.
    tmp, clock, worker_a = fresh_worker()
    try:
        intake(worker_a)
        bind_lead(worker_a, "dimag-lead-000011",
                  executor_behavior="crash_after_intent")
        executor_a = StubExecutor(worker_a)
        crashed = False
        try:
            execute_bound(worker_a, "dimag-lead-000011",
                          executor=executor_a)
        except CrashSimulated:
            crashed = True
        entry = worker_a.load_registry()["dimag-lead-000011"]
        intent = wmod.read_execution(
            worker_a, execution_key_for("dimag-lead-000011", 1))
        ok_crash = (crashed and entry["intake_status"] == "EXECUTING"
                    and intent is not None
                    and intent["phase"] == "EXECUTING")
        # Worker B takes over after expiry + grace, runs recovery; the
        # receipt fixture reports non-execution.
        clock.advance(wmod.LEASE_DURATION_S + wmod.TAKEOVER_GRACE_S + 10)
        worker_b = Worker(tmp, worker_id="dimag-004-worker-02",
                          clock=clock)
        lease_b = wmod.takeover_lease(worker_b, "dimag-lead-000011")
        executor_b = StubExecutor(worker_b)
        executor_b.attest_not_executed(
            execution_key_for("dimag-lead-000011", 1))
        verdict = wmod.reconcile_after_takeover(
            worker_b, "dimag-lead-000011", executor=executor_b)
        recovery = wmod.recover_after_crash(worker_b, executor=executor_b)
        entry_b = worker_b.load_registry()["dimag-lead-000011"]
        rec_a1 = wmod.read_execution(
            worker_b, execution_key_for("dimag-lead-000011", 1))
        ok_recovery = (verdict == "VERIFIED_NOT_EXECUTED"
                       and entry_b["intake_status"] == "BOUND"
                       and rec_a1["phase"] == "UNKNOWN"
                       and rec_a1["recovery_verdict"]
                       == "VERIFIED_NOT_EXECUTED")
        # Resume: the next cycle executes attempt 2 to COMPLETED. The
        # crash was a one-off process death, not a permanently-crashing
        # adapter, so the fixture behavior flips to succeed for the
        # resumed attempt.
        action = wmod.read_action(worker_b, "act-dimag-lead-000011")
        action["executor_behavior"] = "succeed"
        action["record_hash"] = record_hash(action, "record_hash")
        wmod.write_action_fixture(worker_b, action)
        wmod.run_cycle(worker_b, TRACE_PATH, executor=executor_b)
        entry_b = worker_b.load_registry(force=True)["dimag-lead-000011"]
        ok_resume = (entry_b["intake_status"] == "DONE"
                     and entry_b["attempt"] == 2
                     and entry_b["execution_key"]
                     == execution_key_for("dimag-lead-000011", 2))
        # Resume equivalence: same DONE lead, same outcome, same handoff
        # payload (excluding the attempt-2 key); attempt 1's key is
        # never re-used.
        handoff_b = wmod.read_json_file(os.path.join(
            tmp, "handoff",
            "dimag-handoff-%s.json" % entry_b["execution_key"]))
        ok_equiv = (ref_done and entry_b["intake_status"] == "DONE"
                    and handoff_b["outcome"]["label"]
                    == ref_handoff["outcome"]["label"]
                    and handoff_b["outcome"]["qualitative_result"]
                    == ref_handoff["outcome"]["qualitative_result"])
        ok = ok_crash and ok_recovery and ok_resume and ok_equiv
        return require_check("T4 takeover + resume equivalence", ok,
                     "crashed=%s recovery=%s/%s resumed_a2=%s equiv=%s"
                     % (ok_crash, verdict,
                        rec_a1["recovery_verdict"] if rec_a1 else None,
                        ok_resume, ok_equiv))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(ref_tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# T5 -- quarantined-lead refusal, three gates (design SS8.3)
# ---------------------------------------------------------------------------

QUARANTINED_LEADS = ["dimag-lead-000001", "dimag-lead-000002",
                     "dimag-lead-000003", "dimag-lead-000004",
                     "dimag-lead-000005", "dimag-lead-000009",
                     "dimag-lead-000013", "dimag-lead-000014"]


def test_t5():
    tmp, clock, worker = fresh_worker()
    try:
        intake(worker)
        executor = StubExecutor(worker)
        failures = []
        for lead_id in QUARANTINED_LEADS:
            # (a) a binding request is rejected.
            try:
                wmod.request_binding(worker, lead_id)
                failures.append("%s: binding request NOT refused" % lead_id)
            except WorkerError as exc:
                if exc.code != "binding_quarantine_refused":
                    failures.append("%s: binding request wrong code %s"
                                    % (lead_id, exc.code))
            # (b) a direct lease attempt is refused.
            try:
                wmod.acquire_lease(worker, lead_id)
                failures.append("%s: lease NOT refused" % lead_id)
            except WorkerError as exc:
                if exc.code != "lease_refused_quarantined":
                    failures.append("%s: lease wrong code %s"
                                    % (lead_id, exc.code))
            # (c) a forced execution past a test-only binding is refused
            # at check E5, naming the quarantine reason. The binding +
            # lease are planted directly by the test (never through the
            # worker's binding path, which refuses quarantined leads).
            entry = worker.load_registry()[lead_id]
            action = wmod.make_action("act-forced-%s" % lead_id, lead_id,
                                      entry["hypothesis"],
                                      entry["falsification_condition"])
            wmod.write_action_fixture(worker, action)
            binding = {
                "binding_id": "dimag-bind-%s-test" % lead_id,
                "lead_id": lead_id, "action_id": action["id"],
                "bound_at": worker.now_iso(), "bound_by": "test-only",
                "binding_basis": "TEST ONLY: forced binding",
                "policy_result_at_binding": "ALLOW",
                "approval_record": None,
                "scope_grant": action["scope_grant_expires_at"],
                "binding_hash": "",
            }
            binding["binding_hash"] = record_hash(binding, "binding_hash")
            wmod.atomic_write_json(
                os.path.join(tmp, "bindings",
                             "%s.json" % binding["binding_id"]), binding)
            entry["bound_action_id"] = action["id"]
            entry["bound_at"] = binding["bound_at"]
            entry["bound_by"] = "test-only"
            entry["intake_status"] = "LEASED"
            worker._registry_dirty = True
            worker.save_registry()
            lease = wmod._new_lease(
                worker, lead_id, execution_key_for(lead_id, 1))
            wmod.atomic_write_json(
                os.path.join(tmp, "leases", "%s.json" % lead_id), lease)
            result = wmod.execute_lead(worker, lead_id, executor=executor)
            if not (result.get("refused")
                    and result.get("check") == "E5"
                    and result.get("reason") == "exec_refused_quarantined"
                    and "quarantine_reason" in result.get("detail", "")):
                failures.append("%s: forced execution not refused at E5: "
                                "%s" % (lead_id, result))
            # Restore the registry entry to QUARANTINED for the next lead.
            entry = worker.load_registry(force=True)[lead_id]
            entry["intake_status"] = "QUARANTINED"
            entry["bound_action_id"] = None
            entry["bound_at"] = None
            entry["bound_by"] = None
            worker._registry_dirty = True
            worker.save_registry()
            for path in (os.path.join(tmp, "leases",
                                      "%s.json" % lead_id),
                         os.path.join(tmp, "bindings",
                                      "%s.json" % binding["binding_id"])):
                if os.path.exists(path):
                    os.remove(path)
        no_executions = not os.listdir(os.path.join(tmp, "executions"))
        no_calls = len(executor.call_log) == 0
        ok = not failures and no_executions and no_calls
        return require_check("T5 quarantined-lead refusal", ok,
                     "failures=%s executions_created=%s executor_calls=%d"
                     % (failures, not no_executions,
                        len(executor.call_log)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# T6 -- unapproved-action refusal (design SS8.4) + E2 binding-invalid
# ---------------------------------------------------------------------------

def test_t6():
    tmp, clock, worker = fresh_worker()
    try:
        intake(worker)
        executor = StubExecutor(worker)
        # No approval: refused at E3, parked UNAPPROVED_ACTION.
        bind_lead(worker, "dimag-lead-000012",
                  policy_result="REQUIRE_APPROVAL")
        result = execute_bound(worker, "dimag-lead-000012",
                               executor=executor)
        entry = worker.load_registry()["dimag-lead-000012"]
        ok_refused = (result.get("refused")
                      and result.get("check") == "E3"
                      and result.get("reason") == "exec_refused_not_allowed"
                      and entry["intake_status"] == "PARKED_UNAPPROVED_ACTION")
        # Record an approval: execution proceeds.
        action = wmod.read_action(worker, "act-dimag-lead-000012")
        action["approved_at"] = worker.now_iso()
        action["approved_by"] = "niroj"
        action["status"] = "APPROVED"
        action["record_hash"] = record_hash(action, "record_hash")
        wmod.write_action_fixture(worker, action)
        report = wmod.run_cycle(worker, TRACE_PATH, executor=executor)
        entry = worker.load_registry(force=True)["dimag-lead-000012"]
        ok_approved = entry["intake_status"] == "DONE"
        # Revoke the approval on a second lead: refused again.
        bind_lead(worker, "dimag-lead-000015",
                  policy_result="REQUIRE_APPROVAL")
        action2 = wmod.read_action(worker, "act-dimag-lead-000015")
        action2["approved_at"] = worker.now_iso()
        action2["approved_by"] = "niroj"
        action2["status"] = "APPROVED"
        action2["record_hash"] = record_hash(action2, "record_hash")
        wmod.write_action_fixture(worker, action2)
        action2["approved_at"] = None
        action2["approved_by"] = None
        action2["status"] = "PROPOSED"
        action2["record_hash"] = record_hash(action2, "record_hash")
        wmod.write_action_fixture(worker, action2)
        result2 = execute_bound(worker, "dimag-lead-000015",
                                executor=executor)
        ok_revoked = (result2.get("refused")
                      and result2.get("check") == "E3"
                      and result2.get("reason")
                      == "exec_refused_not_allowed")
        # E2: a cancelled Action invalidates the binding. The lease is
        # acquired first (binding valid at lease time); the Action is
        # cancelled after, so the E2 refusal comes from execute_lead.
        bind_lead(worker, "dimag-lead-000016")
        wmod.acquire_lease(worker, "dimag-lead-000016")
        action3 = wmod.read_action(worker, "act-dimag-lead-000016")
        action3["status"] = "CANCELLED"
        action3["record_hash"] = record_hash(action3, "record_hash")
        wmod.write_action_fixture(worker, action3)
        result3 = wmod.execute_lead(worker, "dimag-lead-000016",
                                    executor=executor)
        ok_e2 = (result3.get("refused") and result3.get("check") == "E2"
                 and result3.get("reason")
                 == "exec_refused_binding_invalid")
        ok = ok_refused and ok_approved and ok_revoked and ok_e2
        return require_check("T6 unapproved-action refusal", ok,
                     "refused=%s approved_executes=%s revoked_refused=%s "
                     "E2_binding_invalid=%s"
                     % (ok_refused, ok_approved, ok_revoked, ok_e2))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# T7 -- reconciliation finds a planted discrepancy, one per class (SS10)
# ---------------------------------------------------------------------------

def test_t7():
    tmp, clock, worker = fresh_worker()
    try:
        intake(worker)
        executor = StubExecutor(worker)
        # R1 plant: lead 000010 bound + leased; lease file deleted with
        # no tombstone.
        bind_lead(worker, "dimag-lead-000010")
        lease10 = wmod.acquire_lease(worker, "dimag-lead-000010")
        os.remove(os.path.join(tmp, "leases", "dimag-lead-000010.json"))
        # R2 plant: an execution record naming a lead not in the registry.
        plant_execution_record(
            worker, "dimag-lead-999999",
            execution_key_for("dimag-lead-999999", 1), "COMPLETED",
            "SUCCESS", lease_token=None,
            trace_id="dimag-trace-999999")
        # R3 plant: a receipt with no execution record.
        receipt = {"receipt_id": "dimag-rcpt-planted-r3",
                   "received_at": worker.now_iso(),
                   "external_ref": "stub-external-r3",
                   "outcome_label": "SUCCESS"}
        wmod.atomic_write_json(
            os.path.join(tmp, "receipts",
                         "%s.json" % execution_key_for("dimag-lead-000015",
                                                       1)),
            receipt)
        # R4 plant: a COMPLETED record with no receipt. The record uses
        # the lead's real lease token (from a live lease event) so
        # check 2 does not also flag it.
        bind_lead(worker, "dimag-lead-000016")
        lease16 = wmod.acquire_lease(worker, "dimag-lead-000016")
        plant_execution_record(
            worker, "dimag-lead-000016",
            execution_key_for("dimag-lead-000016", 1), "COMPLETED",
            "SUCCESS", receipt=False,
            lease_token=lease16["lease_token"])
        # R5 plant: two records, one key, different outcomes (v1
        # COMPLETED + v2 FAILED, no supersedes link). Both carry
        # receipts with distinct external refs, and the lead's real
        # lease token.
        bind_lead(worker, "dimag-lead-000018")
        lease18 = wmod.acquire_lease(worker, "dimag-lead-000018")
        key18 = execution_key_for("dimag-lead-000018", 1)
        rec_v1 = plant_execution_record(
            worker, "dimag-lead-000018", key18, "COMPLETED", "SUCCESS",
            lease_token=lease18["lease_token"],
            external_ref="stub-external-r5-v1")
        # v2 is built from the v1 dict and written ONLY as a version
        # file -- writing it through plant_execution_record would
        # overwrite the base file with the FAILED record.
        rec_v2 = dict(rec_v1)
        rec_v2["phase"] = "FAILED"
        rec_v2["outcome"] = {"label": "FAILURE", "actual_value": None,
                             "unit": None,
                             "observed_at": "2026-11-22T04:00:00Z",
                             "qualitative_result": "planted outcome"}
        rec_v2["receipt"] = {"receipt_id": "dimag-rcpt-planted-r5-v2",
                             "received_at": "2026-11-22T04:00:00Z",
                             "external_ref": "stub-external-r5-v2",
                             "outcome_label": "FAILURE"}
        rec_v2["execution_hash"] = record_hash(rec_v2, "execution_hash")
        wmod.write_execution_version(worker, rec_v2, version=2)
        # R6 plant: a trace re-run with a new hash for trace 000011.
        traces, _ = wmod.load_trace_file(TRACE_PATH)
        trace11 = next(t for t in traces
                       if t["trace_id"] == "dimag-trace-000011")
        trace11["diagnostic_lead"]["hypothesis"] = \
            trace11["diagnostic_lead"]["hypothesis"] + " (re-traced)"
        trace11["trace_hash"] = wmod.recompute_trace_hash(trace11)
        retrace_path = os.path.join(tmp, "retraced.jsonl")
        with open(retrace_path, "w", encoding="utf-8") as fh:
            for t in traces:
                fh.write(canonical_json(t) + "\n")
        # R7 plant: a lease naming a quarantined lead.
        lease_q = wmod._new_lease(worker, "dimag-lead-000002",
                                  execution_key_for("dimag-lead-000002", 1))
        wmod.atomic_write_json(
            os.path.join(tmp, "leases", "dimag-lead-000002.json"), lease_q)

        planted_files = {
            os.path.join(tmp, "executions",
                         "%s.json" % execution_key_for("dimag-lead-999999",
                                                       1)),
            os.path.join(tmp, "receipts",
                         "%s.json" % execution_key_for("dimag-lead-000015",
                                                       1)),
            os.path.join(tmp, "executions",
                         "%s.json" % execution_key_for("dimag-lead-000016",
                                                       1)),
            os.path.join(tmp, "executions", "%s.json" % key18),
            os.path.join(tmp, "executions", "%s.v2.json" % key18),
            os.path.join(tmp, "leases", "dimag-lead-000002.json"),
        }
        recon = wmod.run_reconciliation(worker, trace_path=retrace_path,
                                        dataset_path=DATASET_PATH,
                                        executor=executor)
        by_class = {}
        for f in recon["findings"]:
            by_class.setdefault(f["class"], []).append(f["lead_id"])
        expected = {"R1": ["dimag-lead-000010"],
                    "R2": ["dimag-lead-999999"],
                    "R3": ["dimag-lead-000015"],
                    "R4": ["dimag-lead-000016"],
                    "R5": ["dimag-lead-000018"],
                    "R6": ["dimag-lead-000011"],
                    "R7": ["dimag-lead-000002"]}
        ok_classes = by_class == expected
        # Nothing deleted, merged, or silently repaired.
        ok_preserved = all(os.path.exists(p) for p in planted_files)
        # R7 halted the worker.
        ok_halt = worker.halted() is not None and \
            worker.halted()["reason"] == "quarantine_violation"
        ok = ok_classes and ok_preserved and ok_halt
        return require_check("T7 reconciliation finds all plants", ok,
                     "by_class=%s preserved=%s halted=%s"
                     % (json.dumps(by_class, sort_keys=True),
                        ok_preserved, ok_halt))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# T8 -- crash-recovery resume equivalence (design SS12.1)
# ---------------------------------------------------------------------------

def _bind_three(worker):
    for lead_id in ("dimag-lead-000010", "dimag-lead-000011",
                    "dimag-lead-000012"):
        bind_lead(worker, lead_id)


def test_t8():
    # Clean run: three bound leads to DONE.
    clean_tmp, clean_clock, clean_worker = fresh_worker()
    try:
        intake(clean_worker)
        _bind_three(clean_worker)
        clean_executor = StubExecutor(clean_worker)
        wmod.run_cycle(clean_worker, TRACE_PATH, executor=clean_executor)
        clean_registry = clean_worker.load_registry(force=True)
        clean_done = {lid for lid, e in clean_registry.items()
                      if e["intake_status"] == "DONE"}
    finally:
        pass

    tmp, clock, worker = fresh_worker()
    try:
        intake(worker)
        # Lead 000011's action crashes after the intent-phase write.
        bind_lead(worker, "dimag-lead-000010")
        bind_lead(worker, "dimag-lead-000011",
                  executor_behavior="crash_after_intent")
        bind_lead(worker, "dimag-lead-000012")
        executor = StubExecutor(worker)
        crashed = False
        try:
            wmod.run_cycle(worker, TRACE_PATH, executor=executor)
        except CrashSimulated:
            crashed = True
        mid = worker.load_registry(force=True)
        ok_crash = (crashed
                    and mid["dimag-lead-000010"]["intake_status"] == "DONE"
                    and mid["dimag-lead-000011"]["intake_status"]
                    == "EXECUTING"
                    # The third lead was claimed (lease acquired) before
                    # the crash, so it is LEASED -- not BOUND -- when the
                    # worker dies mid-cycle. Recovery re-queues it.
                    and mid["dimag-lead-000012"]["intake_status"]
                    == "LEASED")
        # Recovery after expiry + grace; the receipt fixture reports
        # non-execution for the crashed attempt.
        clock.advance(wmod.LEASE_DURATION_S + wmod.TAKEOVER_GRACE_S + 10)
        worker_b = Worker(tmp, worker_id="dimag-004-worker-02",
                          clock=clock)
        executor_b = StubExecutor(worker_b)
        executor_b.attest_not_executed(
            execution_key_for("dimag-lead-000011", 1))
        recovery = wmod.recover_after_crash(worker_b, executor=executor_b)
        # Resume: the next cycle finishes leads 000011 (attempt 2) and
        # 000012. The crash was a one-off process death, so the fixture
        # behavior flips to succeed for the resumed attempt.
        action = wmod.read_action(worker_b, "act-dimag-lead-000011")
        action["executor_behavior"] = "succeed"
        action["record_hash"] = record_hash(action, "record_hash")
        wmod.write_action_fixture(worker_b, action)
        wmod.run_cycle(worker_b, TRACE_PATH, executor=executor_b)
        final = worker_b.load_registry(force=True)
        crash_done = {lid for lid, e in final.items()
                      if e["intake_status"] == "DONE"}
        # Equivalence: same DONE leads, same completed outcomes, same
        # handoff outcome payloads -- except the crash + recovery events
        # and lead 000011's attempt-2 key (its attempt-1 record is
        # preserved as UNKNOWN / VERIFIED_NOT_EXECUTED, SS12.1 step 3).
        def outcome_map(w, reg):
            out = {}
            for lid, e in reg.items():
                if e["intake_status"] == "DONE" and e.get("execution_key"):
                    rec = wmod.read_execution(w, e["execution_key"])
                    out[lid] = (rec["outcome"]["label"],
                                rec["outcome"]["qualitative_result"])
            return out
        ok_equiv = (crash_done == clean_done
                    and outcome_map(worker_b, final)
                    == outcome_map(clean_worker, clean_registry)
                    and final["dimag-lead-000011"]["attempt"] == 2)
        rec_a1 = wmod.read_execution(
            worker_b, execution_key_for("dimag-lead-000011", 1))
        ok_a1 = (rec_a1["phase"] == "UNKNOWN"
                 and rec_a1["recovery_verdict"] == "VERIFIED_NOT_EXECUTED")
        ok = ok_crash and ok_equiv and ok_a1
        return require_check("T8 crash-recovery resume equivalence", ok,
                     "crashed=%s equiv=%s a1_preserved=%s done=%s"
                     % (ok_crash, ok_equiv, ok_a1, sorted(crash_done)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(clean_tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# T9 -- poison lead stops, never infinite retry (design SS12.3)
# ---------------------------------------------------------------------------

def test_t9():
    tmp, clock, worker = fresh_worker()
    try:
        intake(worker)
        bind_lead(worker, "dimag-lead-000010",
                  executor_behavior="transient_fail")
        executor = StubExecutor(worker)
        backoffs = []
        for _ in range(8):
            entry = worker.load_registry()["dimag-lead-000010"]
            if entry["intake_status"] == "DEAD_LETTER":
                break
            if entry["intake_status"] == "RETRY_WAIT":
                backoffs.append(entry.get("next_retry_at"))
                nxt = parse_iso(entry["next_retry_at"])
                clock.advance((nxt - clock.now()).total_seconds() + 1)
            wmod.run_cycle(worker, TRACE_PATH, executor=executor)
        entry = worker.load_registry(force=True)["dimag-lead-000010"]
        # Backoff waits recorded: attempt 1 -> 1 h, attempt 2 -> 6 h.
        # (Attempt 3 dead-letters with no further wait.)
        waits = []
        if len(backoffs) >= 2:
            t0 = parse_iso("2026-11-22T04:00:00Z")
            waits = [(parse_iso(b) - t0).total_seconds()
                     for b in backoffs]
        ok = (entry["intake_status"] == "DEAD_LETTER"
              and entry.get("attempt") == 3
              and len(entry.get("failure_history", [])) == 3
              and len(executor.call_log) == 3
              and len(backoffs) == 2
              and abs(waits[0] - 3600) < 5
              and abs(waits[1] - (3600 + 21600)) < 10)
        # No fourth attempt from any further cycle.
        calls_before = len(executor.call_log)
        wmod.run_cycle(worker, TRACE_PATH, executor=executor)
        ok = ok and len(executor.call_log) == calls_before
        return require_check("T9 poison lead stops", ok,
                     "attempts=%d calls=%d backoffs=%s dead_letter=%s"
                     % (entry.get("attempt"), len(executor.call_log),
                        backoffs,
                        entry["intake_status"] == "DEAD_LETTER"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# T10 -- duplicate-intake no-op (design SS7.4)
# ---------------------------------------------------------------------------

def test_t10():
    tmp, clock, worker = fresh_worker()
    try:
        first = intake(worker)
        registry_path = os.path.join(tmp, "dimag-lead-registry-v1.jsonl")
        sha_before = sha256_file(registry_path)
        leases_before = os.listdir(os.path.join(tmp, "leases"))
        execs_before = os.listdir(os.path.join(tmp, "executions"))
        second = intake(worker)
        sha_after = sha256_file(registry_path)
        ok = (second["duplicates"] == 19
              and second["intaked"] == 0
              and sha_before == sha_after
              and os.listdir(os.path.join(tmp, "leases")) == leases_before
              and os.listdir(os.path.join(tmp, "executions")) == execs_before)
        lines = wmod.read_jsonl(os.path.join(tmp, "intake-log.jsonl"))
        dups = [l for l in lines
                if l.get("outcome") == "DUPLICATE_INTAKE_IGNORED"]
        ok = ok and len(dups) == 19
        return require_check("T10 duplicate-intake no-op", ok,
                     "duplicates=%d registry_identical=%s dup_log_lines=%d"
                     % (second["duplicates"], sha_before == sha_after,
                        len(dups)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# T11 -- no-relabel + no-trace-edit, incl. a read-only run (design SS15)
# ---------------------------------------------------------------------------

def test_t11():
    tmp, clock, worker = fresh_worker()
    trace_copy = os.path.join(tmp, "traces-copy.jsonl")
    dataset_copy = os.path.join(tmp, "dataset-copy.jsonl")
    shutil.copy(TRACE_PATH, trace_copy)
    shutil.copy(DATASET_PATH, dataset_copy)
    try:
        trace_sha_before = sha256_file(trace_copy)
        dataset_sha_before = sha256_file(dataset_copy)
        traces_before, _ = wmod.load_trace_file(trace_copy)
        hashes_before = {t["trace_id"]: t["trace_hash"]
                         for t in traces_before}
        # Full run: intake + cycle + reconcile + evaluate.
        intake(worker)
        executor = StubExecutor(worker)
        wmod.run_cycle(worker, trace_copy, executor=executor,
                       dataset_path=dataset_copy)
        wmod.run_reconciliation(worker, trace_path=trace_copy,
                                dataset_path=dataset_copy)
        wmod.evaluate(worker, trace_path=trace_copy,
                      dataset_path=dataset_copy)
        trace_sha_after = sha256_file(trace_copy)
        dataset_sha_after = sha256_file(dataset_copy)
        traces_after, _ = wmod.load_trace_file(trace_copy)
        hashes_ok = all(
            wmod.recompute_trace_hash(t) == hashes_before[t["trace_id"]]
            for t in traces_after)
        ok_first = (trace_sha_before == trace_sha_after
                    and dataset_sha_before == dataset_sha_after
                    and hashes_ok)
        # Second full run with write permission removed from the trace
        # file and the dataset file: it must still succeed.
        os.chmod(trace_copy, 0o444)
        os.chmod(dataset_copy, 0o444)
        try:
            worker2 = Worker(os.path.join(tmp, "state2"),
                             worker_id="dimag-004-worker-01", clock=clock)
            intake(worker2)
            wmod.run_cycle(worker2, trace_copy, executor=StubExecutor(worker2),
                           dataset_path=dataset_copy)
            wmod.run_reconciliation(worker2, trace_path=trace_copy,
                                    dataset_path=dataset_copy)
            ok_second = True
        except Exception as exc:  # noqa: BLE001 - the failure is the evidence
            ok_second = False
            print("  read-only run failed: %s" % exc)
        finally:
            os.chmod(trace_copy, 0o644)
            os.chmod(dataset_copy, 0o644)
        ok = ok_first and ok_second and \
            sha256_file(trace_copy) == trace_sha_before and \
            sha256_file(dataset_copy) == dataset_sha_before
        return require_check("T11 no-relabel + no-trace-edit", ok,
                     "trace_unchanged=%s dataset_unchanged=%s "
                     "hashes_recompute=%s read_only_run_ok=%s"
                     % (trace_sha_before == trace_sha_after,
                        dataset_sha_before == dataset_sha_after,
                        hashes_ok, ok_second))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# T12 -- temporal-evaluation harness works (design SS11)
# ---------------------------------------------------------------------------

def test_t12():
    tmp, clock, worker = fresh_worker()
    try:
        intake(worker)
        _bind_three(worker)
        executor = StubExecutor(worker)
        wmod.run_cycle(worker, TRACE_PATH, executor=executor)
        # One idempotent replay in the window.
        done = [lid for lid, e in worker.load_registry().items()
                if e["intake_status"] == "DONE"]
        replayed = wmod.execute_lead(worker, done[0], executor=executor)
        # One duplicate delivery in the window.
        intake(worker)
        ev = wmod.evaluate(worker, window_days=365, trace_path=TRACE_PATH,
                           dataset_path=DATASET_PATH)
        metrics = ev["metrics"]
        required = ["lease_exclusivity_violations",
                    "idempotent_replay_correctness",
                    "reconciliation_catch_rate",
                    "mean_time_to_detect_lost_lease_s",
                    "duplicate_intake_noop_rate",
                    "dead_letter_rate_per_100_executions",
                    "execution_to_handoff_lag_s",
                    "execution_to_experience_row_lag_s",
                    "refusal_rate_by_check", "replay_divergence"]
        ok_metrics = all(k in metrics for k in required)
        injected = ev["fault_injection"]
        ok_plants = (injected.get("lost_lease")
                     and injected.get("duplicate_delivery")
                     and injected.get("poison_lead"))
        ok = (metrics["replay_divergence"] == 0
              and not ev["replay"]["registry_mismatches"]
              and ok_metrics and ok_plants
              and replayed.get("replayed"))
        return require_check("T12 temporal evaluation", ok,
                     "divergences=%d mismatches=%s metrics=%s plants=%s"
                     % (metrics["replay_divergence"],
                        ev["replay"]["registry_mismatches"],
                        ok_metrics, json.dumps(injected, sort_keys=True)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Mac-port additions -- T13-T15: the field seam + the live-row hook.
# These cover the Mac additions only; T0-T12 above are the reference
# tests unchanged in behavior.
# ---------------------------------------------------------------------------

def _fake_live_row(lead_id, entry, **overrides):
    """A duck-typed live ForgeOS Action row for one lead (a dict with
    the same attributes as a models.Action row)."""
    row = {
        "id": "act-%s" % lead_id,
        "decision_id": "dimag-decision-%s" % lead_id,
        "action_type": "diagnostic-lead-execution",
        "objective": "Execute the diagnostic lead's hypothesis as an "
                     "action: %s" % entry["hypothesis"],
        "parameters_json": {
            "lead_id": lead_id,
            "hypothesis": entry["hypothesis"],
            "falsification_condition": entry["falsification_condition"],
        },
        "status": "APPROVED",
        "policy_result": "ALLOW",
        "policy_reason": "live verdict: ALLOW",
        "approved_at": None,
        "execution_result": None,
        "execution_error": None,
        "verification_state": "UNVERIFIED",
        "adapter_name": "stub-adapter",
    }
    row.update(overrides)
    return row


def _bind_via_hook(worker, lead_id, hook):
    """Bind a lead to a live-row action served by the hook. The hook
    reads the CURRENT row on every call, so later mutations of the row
    are what the seam and the E2/E7 checks see -- the live-read
    property the design requires."""
    worker.action_reader = hook
    return wmod.record_binding(worker, lead_id, "act-%s" % lead_id,
                               bound_by="niroj")


def test_t13():
    """T13 -- ForgeOSSeam verdicts (field mode).

    One bound lead, one live row, mutated between verdict checks: the
    seam must return the FileSeam reason vocabulary for every SS8.1
    condition, and must re-read the row live (a mutation after binding
    changes the next verdict)."""
    tmp, clock, worker = fresh_worker()
    try:
        intake(worker)
        lead_id = "dimag-lead-000010"
        entry = worker.load_registry()[lead_id]
        row = _fake_live_row(lead_id, entry)
        cfg = {"open_flags": set(), "dnc": set(), "grants": {},
               "stop": False}

        def hook(w, action_id):
            return field_seam.action_dict_from_row(
                row, open_flags=cfg["open_flags"],
                do_not_contact_ids=cfg["dnc"],
                scope_grants=cfg["grants"],
                adapter_receipt_fn=lambda name: True)

        _bind_via_hook(worker, lead_id, hook)
        seam = field_seam.ForgeOSSeam(
            worker, stop_active_fn=lambda: cfg["stop"])

        def verdict():
            return seam.allowed_mask(lead_id)

        results = {}
        results["allow_ok"] = verdict()
        row["policy_result"] = "REQUIRE_APPROVAL"
        row["approved_at"] = None
        results["approval_missing"] = verdict()
        row["approved_at"] = "2026-11-22T03:00:00Z"
        results["approval_ok"] = verdict()
        row["policy_result"] = "BLOCK"
        row["approved_at"] = None
        results["policy_block"] = verdict()
        row["policy_result"] = "ALLOW"
        cfg["stop"] = True
        results["stop_active"] = verdict()
        cfg["stop"] = False
        row["parameters_json"]["operation"] = "SEND_EMAIL"
        results["flags_closed"] = verdict()
        cfg["open_flags"] = {"FORGE_BOT_RESPONSE_SEND_ENABLED"}
        results["flags_open"] = verdict()
        cfg["open_flags"] = set()
        del row["parameters_json"]["operation"]
        row["parameters_json"]["contact_entity_id"] = 77
        cfg["dnc"] = {77}
        results["do_not_contact"] = verdict()
        cfg["dnc"] = set()
        del row["parameters_json"]["contact_entity_id"]
        cfg["grants"] = {"act-%s" % lead_id: "2026-11-21T00:00:00Z"}
        results["grant_expired"] = verdict()
        cfg["grants"] = {"act-%s" % lead_id: "2027-01-01T00:00:00Z"}
        results["grant_ok"] = verdict()
        expected = {
            "allow_ok": (True, "ok"),
            "approval_missing": (False, "approval_missing"),
            "approval_ok": (True, "ok"),
            "policy_block": (False, "policy_BLOCK"),
            "stop_active": (False, "stop_active"),
            "flags_closed": (False, "gate_flags_closed"),
            "flags_open": (True, "ok"),
            "do_not_contact": (False, "do_not_contact"),
            "grant_expired": (False, "scope_grant_expired"),
            "grant_ok": (True, "ok"),
        }
        ok = all((results[k]["allowed"], results[k]["reason"]) == v
                 for k, v in expected.items())
        return require_check("T13 field seam verdicts", ok,
                     json.dumps({k: (v["allowed"], v["reason"])
                                 for k, v in results.items()},
                                sort_keys=True))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_t14():
    """T14 -- the live-row reader (field_seam.action_dict_from_row).

    A fake live row (parameters_json as a JSON string, approved_at as a
    naive datetime) must convert to the worker's EXACT action dict:
    all ACTION_FIELDS keys present, none extra, parameters parsed,
    approved_at as ISO Z, record_hash reproducing, fixture extras set
    for field mode."""
    from datetime import datetime
    row = {
        "id": 42,
        "decision_id": 7,
        "action_type": "diagnostic-lead-execution",
        "objective": "Execute the hypothesis",
        "parameters_json": '{"lead_id": "dimag-lead-000010", '
                           '"hypothesis": "h", '
                           '"falsification_condition": "f", '
                           '"operation": "SEND_EMAIL", '
                           '"contact_entity_id": 77}',
        "status": "APPROVED",
        "policy_result": "ALLOW",
        "policy_reason": "live verdict",
        "approved_at": datetime(2026, 11, 22, 3, 0, 0),
        "execution_result": None,
        "execution_error": None,
        "verification_state": "UNVERIFIED",
        "adapter_name": "stub-adapter",
    }
    action = field_seam.action_dict_from_row(
        row, open_flags={"FORGE_BOT_RESPONSE_SEND_ENABLED"},
        do_not_contact_ids={77},
        scope_grants={42: "2027-01-01T00:00:00Z"},
        adapter_receipt_fn=lambda name: True)
    key_errors = wmod._check_keys(action, wmod.ACTION_FIELDS,
                                  "field action")
    hash_ok = (wmod.record_hash(action, "record_hash")
               == action["record_hash"])
    ok = (not key_errors and hash_ok
          and set(action.keys()) == set(wmod.ACTION_FIELDS)
          and action["parameters_json"]["hypothesis"] == "h"
          and action["approved_at"] == "2026-11-22T03:00:00Z"
          and action["fixture"] is False
          and action["schematic"] is False
          and action["approved_by"] is None
          and action["gate_flags_open"] is True
          and action["target_in_do_not_contact"] is True
          and action["scope_grant_expires_at"] == "2027-01-01T00:00:00Z"
          and action["adapter_receipt"] is True
          and action["executor_behavior"] is None
          and action["expected_outcome"] is None)
    # Default adapter_receipt is False (fail closed, design SS7.3).
    action2 = field_seam.action_dict_from_row(row)
    ok = ok and action2["adapter_receipt"] is False
    # A JSON string that is not an object degrades to {} (never a crash).
    row_bad = dict(row, parameters_json="not json{")
    action3 = field_seam.action_dict_from_row(row_bad)
    ok = ok and action3["parameters_json"] == {}
    return require_check("T14 live-row reader", ok,
                 "key_errors=%s hash_ok=%s gate_flags_open=%s dnc=%s "
                 "receipt_default=%s" % (key_errors, hash_ok,
                                         action["gate_flags_open"],
                                         action["target_in_do_not_contact"],
                                         action2["adapter_receipt"]))


def test_t15():
    """T15 -- the action_reader hook end to end through execute_lead.

    Three bound leads, one worker, one hook dispatching on action_id:
    (1) an ALLOW live row with a receipt adapter executes to DONE
    through the ForgeOSSeam; (2) a BLOCK live row is refused at E3
    through the FileSeam (the hook flows through it too); (3) an ALLOW
    live row with no receipt adapter is refused at E7."""
    tmp, clock, worker = fresh_worker()
    try:
        intake(worker)
        registry = worker.load_registry()
        rows = {}
        for lead_id, policy, receipt in (
                ("dimag-lead-000010", "ALLOW", True),
                ("dimag-lead-000011", "BLOCK", True),
                ("dimag-lead-000012", "ALLOW", False)):
            entry = registry[lead_id]
            rows["act-%s" % lead_id] = _fake_live_row(
                lead_id, entry, policy_result=policy)
            rows["act-%s" % lead_id]["_receipt"] = receipt

        def hook(w, action_id):
            row = rows[action_id]
            return field_seam.action_dict_from_row(
                row, adapter_receipt_fn=lambda name: row["_receipt"])

        worker.action_reader = hook
        for lead_id in ("dimag-lead-000010", "dimag-lead-000011",
                        "dimag-lead-000012"):
            wmod.record_binding(worker, lead_id, "act-%s" % lead_id,
                                bound_by="niroj")
        seam = field_seam.ForgeOSSeam(
            worker, stop_active_fn=lambda: False)
        wmod.acquire_lease(worker, "dimag-lead-000010")
        done = wmod.execute_lead(worker, "dimag-lead-000010",
                                 executor=StubExecutor(worker), seam=seam)
        wmod.acquire_lease(worker, "dimag-lead-000011")
        blocked = wmod.execute_lead(worker, "dimag-lead-000011",
                                    executor=StubExecutor(worker))
        wmod.acquire_lease(worker, "dimag-lead-000012")
        no_receipt = wmod.execute_lead(worker, "dimag-lead-000012",
                                       executor=StubExecutor(worker))
        registry = worker.load_registry()
        ok = (done.get("completed") is True
              and registry["dimag-lead-000010"]["intake_status"] == "DONE"
              and os.path.exists(os.path.join(
                  tmp, "handoff",
                  "dimag-handoff-%s.json" % done["execution_key"]))
              and blocked.get("refused")
              and blocked.get("check") == "E3"
              and blocked.get("reason") == "exec_refused_not_allowed"
              and registry["dimag-lead-000011"]["intake_status"]
              == "PARKED_UNAPPROVED_ACTION"
              and no_receipt.get("refused")
              and no_receipt.get("check") == "E7"
              and no_receipt.get("reason")
              == "exec_refused_no_receipt_adapter"
              and registry["dimag-lead-000012"]["intake_status"]
              == "PARKED_NO_RECEIPT_ADAPTER")
        return require_check("T15 hook end to end", ok,
                     "done=%s blocked=%s no_receipt=%s"
                     % (done.get("completed"),
                        blocked.get("reason"),
                        no_receipt.get("reason")))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


TESTS = [("T0 worker runs", test_t0),
         ("T1 worked intake", test_t1),
         ("T2 idempotent re-execution", test_t2),
         ("T3 lease exclusivity", test_t3),
         ("T4 takeover + resume equivalence", test_t4),
         ("T5 quarantined-lead refusal", test_t5),
         ("T6 unapproved-action refusal", test_t6),
         ("T7 reconciliation finds all plants", test_t7),
         ("T8 crash-recovery resume equivalence", test_t8),
         ("T9 poison lead stops", test_t9),
         ("T10 duplicate-intake no-op", test_t10),
         ("T11 no-relabel + no-trace-edit", test_t11),
         ("T12 temporal evaluation", test_t12),
         ("T13 field seam verdicts", test_t13),
         ("T14 live-row reader", test_t14),
         ("T15 hook end to end", test_t15)]


def main():
    passed = 0
    for name, fn in TESTS:
        result_count = len(RESULTS)
        try:
            fn()
            if (len(RESULTS) == result_count + 1
                    and RESULTS[-1]["test"] == name
                    and RESULTS[-1]["passed"]):
                passed += 1
        except Exception as exc:  # noqa: BLE001 - a crash is a failure
            import traceback
            traceback.print_exc()
            if (len(RESULTS) == result_count or RESULTS[-1]["passed"]
                    or RESULTS[-1]["test"] != name):
                check(name, False, "EXCEPTION %s: %s"
                      % (type(exc).__name__, exc))
    total = len(TESTS)
    print("\n%d/%d acceptance tests passing" % (passed, total))
    # Mac port: results go to the temp dir, never into the repo (the
    # reference wrote them next to the worker directory).
    results_path = os.path.join(
        tempfile.gettempdir(), "dimag-004-test-results-v1.json")
    with open(results_path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(
            {"worker_version": wmod.WORKER_VERSION,
             "tests_run": total, "tests_passed": passed,
             "ok": passed == total, "results": RESULTS},
            sort_keys=True, indent=2) + "\n")
    print("results: %s" % results_path)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
