"""
HISTORICAL DUPLICATE MAINTENANCE COMMAND
=========================================

Generic, idempotent maintenance command to identify duplicate opportunity clusters
and merge them into a single canonical opportunity without deleting rows.

Usage:
    python -m app.cli.merge_duplicates [--dry-run | --apply]

Default behavior is ALWAYS --dry-run.
--apply must be passed explicitly to mutate the database.
"""

import json
import argparse
from typing import Dict, List
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from app import models
from app.services.opportunity_engine import _identity_key, _append_signal_id


def find_duplicate_clusters(db: Session) -> Dict[str, List[models.Opportunity]]:
    """Group all non-archived opportunities by their normalized problem key."""
    all_opps = (
        db.query(models.Opportunity)
        .filter(models.Opportunity.status != "archived")
        .order_by(models.Opportunity.id.asc())
        .all()
    )
    clusters: Dict[str, List[models.Opportunity]] = {}
    for opp in all_opps:
        key = _identity_key(opp.problem)
        clusters.setdefault(key, []).append(opp)
    
    # Filter to only clusters with > 1 opportunity
    return {k: v for k, v in clusters.items() if len(v) > 1}


def run_merge(apply: bool = False, db: Session | None = None) -> dict:
    close_db = False
    if db is None:
        init_db()
        db = SessionLocal()
        close_db = True

    try:
        clusters = find_duplicate_clusters(db)
        summary = {
            "mode": "apply" if apply else "dry-run",
            "clusters_found": len(clusters),
            "opportunities_archived": 0,
            "decisions_repointed": 0,
            "experiments_repointed": 0,
            "evidence_repointed": 0,
            "details": [],
        }

        for key, opp_list in clusters.items():
            # Lowest ID is chosen as canonical
            canonical = opp_list[0]
            duplicates = opp_list[1:]

            cluster_detail = {
                "identity_key": key,
                "problem": canonical.problem[:100],
                "canonical_id": canonical.id,
                "duplicate_ids": [d.id for d in duplicates],
                "decisions_to_repoint": 0,
                "experiments_to_repoint": 0,
                "evidence_to_repoint": 0,
            }

            for dup in duplicates:
                dec_count = db.query(models.Decision).filter_by(opportunity_id=dup.id).count()
                exp_count = db.query(models.Experiment).filter_by(opportunity_id=dup.id).count()
                ev_count = db.query(models.Evidence).filter_by(opportunity_id=dup.id).count()

                cluster_detail["decisions_to_repoint"] += dec_count
                cluster_detail["experiments_to_repoint"] += exp_count
                cluster_detail["evidence_to_repoint"] += ev_count

                if apply:
                    # 1. Re-point Decisions
                    db.query(models.Decision).filter_by(opportunity_id=dup.id).update(
                        {"opportunity_id": canonical.id}, synchronize_session=False
                    )
                    # 2. Re-point Experiments
                    db.query(models.Experiment).filter_by(opportunity_id=dup.id).update(
                        {"opportunity_id": canonical.id}, synchronize_session=False
                    )
                    # 3. Re-point Evidence
                    db.query(models.Evidence).filter_by(opportunity_id=dup.id).update(
                        {"opportunity_id": canonical.id}, synchronize_session=False
                    )

                    # 4. Append supporting signal IDs to canonical
                    if dup.problem_evidence_signal_ids:
                        for sig_id in dup.problem_evidence_signal_ids.split(","):
                            if sig_id.strip().isdigit():
                                canonical.problem_evidence_signal_ids = _append_signal_id(
                                    canonical.problem_evidence_signal_ids, int(sig_id.strip())
                                )

                    # 5. Archive duplicate row without deletion
                    dup.status = "archived"
                    dup.no_meaningful_change = True
                    dup.identity_key = key
                    dup.economic_evidence_summary = (
                        f"Archived duplicate of canonical opportunity #{canonical.id}."
                    )

                    # Record OpportunityEvent audit row
                    event_key = f"archived_duplicate:{dup.id}->{canonical.id}"
                    dup_event = models.OpportunityEvent(
                        opportunity_id=dup.id,
                        event_type="archived_duplicate",
                        event_key=event_key,
                        details=json.dumps({"canonical_opportunity_id": canonical.id}),
                    )
                    db.add(dup_event)

                    summary["opportunities_archived"] += 1
                    summary["decisions_repointed"] += dec_count
                    summary["experiments_repointed"] += exp_count
                    summary["evidence_repointed"] += ev_count

            summary["details"].append(cluster_detail)

        if apply:
            db.commit()

        return summary
    finally:
        if close_db:
            db.close()


def main():
    parser = argparse.ArgumentParser(description="ForgeOS Duplicate Opportunity Merger")
    parser.add_argument(
        "--apply",
        action="store_true",
        default=False,
        help="Execute the merge in the database. Defaults to --dry-run (False) if omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run in dry-run mode without modifying the database (default).",
    )
    args = parser.parse_args()

    # If --apply was set explicitly, dry-run is False
    is_apply = args.apply

    result = run_merge(apply=is_apply)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
