"""DIMAG-004 runner -- deterministic CLI (design SS13.1).

Pipeline (each stage writes only its own output; no stage mutates its
input; the trace file and the dataset file are read-only throughout):

  Stage 0  INVENTORY   Record trace file path + sha256 + version.
  Stage 1  INTAKE      Extract leads read-only; validate I1-I8; write
                       the registry + intake log. Duplicates are no-ops.
  Stage 2  BIND        Emit binding requests for PROPOSED leads; validate
                       existing bindings against the live Action row.
  Stage 3  CYCLE       Bounded cycle: claim up to N BOUND leads, acquire
                       leases, run the E1-E8 checklist, execute through
                       the governance seam, write intent + outcome records.
  Stage 4  HANDOFF     Write handoff records for DONE leads (DIMAG-002
                       pipeline input). The worker never writes the
                       dataset file.
  Stage 5  RECONCILE   Sweep: registry vs leases vs executions vs
                       handoffs vs traces; classify R1-R7.
  Stage 6  EVALUATE    Temporal evaluation: replay the event log, fault
                       injection on a scratch copy, SS11.3 metrics.
  Stage 7  PUBLISH     The cycle report (leads intaked/leased/executed/
                       refused/parked/dead-lettered, reconciliation
                       findings by class, quarantine count, STOP state).

Mac / ForgeOS port (22 Nov 2026): the reference runner ported into
backend/app/services/dimag/. Run from the ForgeOS repo root as:
  python -m backend.app.services.dimag.runner [options] [command]
Usage:
  python -m backend.app.services.dimag.runner [--trace PATH]
                    [--dataset PATH] [--state-dir DIR] [--field]
                    [inventory|intake|bind|cycle|reconcile|evaluate|
                     recover|full]
Defaults: the v1 trace file staged at
~/hami/dimag-004-worker/dimag-backward-traces-v1.jsonl, the v1 dataset
at ~/hami/dimag-002/dimag-experience-dataset-v1.jsonl, state in
~/hami/dimag-004-worker/. --field wires the live ForgeOS database
(field_seam.field_wiring: live Action rows, live STOP, live
DoNotContact rows); without it the runner works in file mode against
schematic fixture Action rows, exactly like the reference.
"""

import argparse
import json
import os
import sys

from . import field_seam
from . import worker as worker_mod

TRACE_DEFAULT = os.path.expanduser(
    "~/hami/dimag-004-worker/dimag-backward-traces-v1.jsonl")
DATASET_DEFAULT = os.path.expanduser(
    "~/hami/dimag-002/dimag-experience-dataset-v1.jsonl")
STATE_DEFAULT = os.path.expanduser("~/hami/dimag-004-worker")


def _counts_line(counts):
    by_status = counts.get("by_status", {})
    return ("intaked=%d duplicates=%d rejected=%d no_lead=%d superseded=%d "
            "by_status=%s" % (counts.get("intaked", 0),
                              counts.get("duplicates", 0),
                              counts.get("rejected", 0),
                              counts.get("no_lead", 0),
                              counts.get("superseded", 0),
                              json.dumps(by_status, sort_keys=True)))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="DIMAG-004 durable intelligence worker (v1)")
    parser.add_argument("--trace", default=TRACE_DEFAULT,
                        help="DIMAG-003 trace file (read-only)")
    parser.add_argument("--dataset", default=DATASET_DEFAULT,
                        help="DIMAG-002 dataset file (read-only)")
    parser.add_argument("--state-dir", default=STATE_DEFAULT,
                        help="worker state directory")
    parser.add_argument("--field", action="store_true",
                        help="field mode: read live ForgeOS rows "
                        "(Action, STOP, DoNotContact) instead of "
                        "schematic fixtures")
    parser.add_argument("--worker-id", default="dimag-004-worker-01",
                        help="worker identity for this process")
    parser.add_argument("command", nargs="?", default="full",
                        choices=["inventory", "intake", "bind", "cycle",
                                 "reconcile", "evaluate", "recover",
                                 "full"],
                        help="pipeline stage to run")
    args = parser.parse_args(argv)

    w = worker_mod.Worker(args.state_dir, worker_id=args.worker_id)
    if not args.field:
        return _dispatch(args, w, None)
    # Field mode: live ForgeOS rows. The session is only ever READ by
    # this wiring (field_seam.field_wiring); the worker never writes a
    # ForgeOS row.
    from app.database import SessionLocal  # noqa: PLC0415 -- lazy: DB only in field mode
    with SessionLocal() as db:
        reader, seam = field_seam.field_wiring(db, w)
        w.action_reader = reader
        return _dispatch(args, w, seam)


def _dispatch(args, w, seam):
    cmd = args.command

    if cmd in ("inventory", "full"):
        inv = worker_mod.inventory(w, args.trace)
        print("inventory: %s leads=%s sha=%s"
              % (inv["status"], inv["leads"],
                 (inv.get("trace_file_sha256") or "")[:12]))
        if cmd == "inventory":
            return 0

    if cmd in ("intake", "full"):
        counts = worker_mod.intake_traces(w, args.trace)
        print("intake: %s" % _counts_line(counts))
        if cmd == "intake":
            return 0

    if cmd == "bind":
        registry = w.load_registry()
        made = 0
        for lead_id in sorted(registry):
            entry = registry[lead_id]
            if entry["intake_status"] == "PROPOSED" and \
                    not entry.get("bound_action_id"):
                try:
                    worker_mod.request_binding(w, lead_id)
                    made += 1
                except worker_mod.WorkerError as exc:
                    print("binding request refused for %s: %s"
                          % (lead_id, exc.code))
        print("bind: %d binding request(s) emitted" % made)
        return 0

    if cmd in ("cycle", "full"):
        report = worker_mod.run_cycle(w, args.trace,
                                      dataset_path=args.dataset,
                                      seam=seam)
        print("cycle %s: state=%s executions=%d refusals=%d "
              "reconciliation_findings=%d"
              % (report["cycle_id"], report["state"],
                 len(report.get("executions", [])),
                 len(report.get("refusals", [])),
                 report.get("stages", {}).get("reconcile", {})
                 .get("findings", 0)))
        for ex in report.get("executions", []):
            print("  %s: %s" % (ex.get("lead_id"),
                                {k: v for k, v in ex.items()
                                 if k not in ("lead_id",)}))
        if cmd == "cycle":
            return 0

    if cmd in ("reconcile", "full"):
        recon = worker_mod.run_reconciliation(
            w, trace_path=args.trace, dataset_path=args.dataset)
        print("reconcile: %d finding(s) %s; worker_halted=%s"
              % (recon["counts"]["findings"],
                 json.dumps(recon["counts"]["by_class"], sort_keys=True),
                 recon["worker_halted"]))
        for f in recon["findings"]:
            print("  %s %s: %s" % (f["class"], f["lead_id"], f["detail"]))
        if cmd == "reconcile":
            return 0

    if cmd in ("evaluate", "full"):
        ev = worker_mod.evaluate(w, trace_path=args.trace,
                                 dataset_path=args.dataset)
        print("evaluate: replay divergences=%d, fault injection %d/%d "
              "caught %s"
              % (ev["metrics"]["replay_divergence"],
                 ev["metrics"]["reconciliation_catch_rate"]["caught"],
                 ev["metrics"]["reconciliation_catch_rate"]["planted"],
                 json.dumps(ev["fault_injection"], sort_keys=True)))
        if cmd == "evaluate":
            return 0

    if cmd == "recover":
        report = worker_mod.recover_after_crash(w)
        print("recover: %s" % "; ".join(report["steps"]))
        for lead_id, verdict in sorted(report["leads"].items()):
            print("  %s: %s" % (lead_id, verdict))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
