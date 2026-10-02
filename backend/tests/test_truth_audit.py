"""Truth-audit metrics must distinguish data volume from reality validation."""

from datetime import datetime, timedelta, timezone

from app import models
from app.services import truth_audit


def test_snapshot_labels_raw_and_real_metrics_separately(db):
    db.add_all([
        models.Signal(source="rss", content="historical", collection_status="observed", is_duplicate_of=None),
        models.Signal(source="manual", content="human input", collection_status="collected", is_duplicate_of=None),
        models.Signal(source="rss", content="duplicate", collection_status="observed", is_duplicate_of=1),
    ])
    db.commit()

    metrics = truth_audit.snapshot(db)
    labels = metrics["epistemic_labels"]

    assert labels["raw_signals"] == 3
    assert labels["historical_or_observed_signals"] == 2
    assert labels["currently_collected_signals"] == 1
    assert labels["duplicate_signals"] == 1
    assert labels["verified_claims"] == 0
    assert labels["human_validated_problems"] == 0
    assert labels["real_experiments"] == 0
    assert labels["actual_outcomes"] == 0
    assert labels["reality_learning_events"] == 0
    assert labels["actual_revenue"] == 0.0
    assert metrics["interpretation"]["evidence_is_not_verified_truth"] is True
    assert metrics["provenance"]["canonical_signals"] == 2
    assert metrics["signal_quality"]["canonical_average"] is not None
    assert metrics["operations"]["running_cycles"] == 0
    assert metrics["operations"]["pending_actions"] == 0


def test_stale_running_cycles_are_failed_without_deletion(db):
    stale = models.CycleRun(
        started_at=datetime.now(timezone.utc) - timedelta(hours=3),
        status="RUNNING",
    )
    current = models.CycleRun(
        started_at=datetime.now(timezone.utc),
        status="RUNNING",
    )
    db.add_all([stale, current])
    db.commit()

    changed = truth_audit.reconcile_stale_cycles(db)

    assert changed == 1
    db.refresh(stale)
    db.refresh(current)
    assert stale.status == "FAILED"
    assert stale.ended_at is not None
    assert "stale RUNNING record reconciled" in stale.error
    assert current.status == "RUNNING"
    assert db.query(models.CycleRun).count() == 2
