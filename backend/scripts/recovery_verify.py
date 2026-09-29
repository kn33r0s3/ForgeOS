"""Recovery drill for the canonical SQLite database.

Proves the whole backup/restore path still works against the live file:

  1. take a consistent, read-only snapshot through ``backup.safe_backup``
     (VACUUM INTO + gzip; the canonical file is never written),
  2. restore the snapshot into a temporary plain database,
  3. prove the restored copy is structurally sound — ``integrity_check``,
     no foreign-key violations, no leftover ``*_old`` / ``*_new`` tables
     from an interrupted column rebuild,
  4. prove no data was lost: every table in the live file has exactly the
     same row count in the restored copy.

The canonical database is opened read-only and the snapshot is written to a
private temporary directory (never storage/backups, whose retention policy
would delete the operator's real recovery points). A mismatch names the
failing table instead of comparing against a hard-coded number, so the drill
stays valid as real data grows. Run it while no writer is active (the
scheduler and the worker both write): a concurrent write changes the live
counts.
"""

from __future__ import annotations

import gzip
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

if __package__ in (None, ""):  # allow `python scripts/recovery_verify.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import backup  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_DB = ROOT / "storage" / "forge.db"
_READ_ONLY_TIMEOUT_SECONDS = 30


class RecoveryVerificationError(RuntimeError):
    """The snapshot did not restore to an equal, structurally sound database."""


def _connect_read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(
        f"file:{path}?mode=ro", uri=True, timeout=_READ_ONLY_TIMEOUT_SECONDS
    )


def _table_names(con: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in con.execute(
            "select name from sqlite_master where type='table' "
            "and name not like 'sqlite_%' order by name"
        )
    ]


def _row_counts(con: sqlite3.Connection) -> dict[str, int]:
    return {
        name: con.execute(f'select count(*) from "{name}"').fetchone()[0]
        for name in _table_names(con)
    }


def _stale_rebuild_tables(names: list[str]) -> list[str]:
    """Leftovers an interrupted SQLite column rebuild would leave behind."""
    return sorted(
        name
        for name in names
        if name.endswith("__old") or name.endswith("_old") or name.endswith("_new")
    )


def verify_recovery(db_path: Path | None = None, workdir: Path | None = None) -> dict:
    """Run the drill and return the observed evidence. Raises on any mismatch."""
    source = Path(db_path or CANONICAL_DB).resolve()
    if not source.exists():
        raise RecoveryVerificationError(f"no database to verify at {source}")

    scratch_context = None
    if workdir is None:
        # The drill's snapshot must never land in storage/backups: safe_backup
        # prunes to `keep`, so writing there with keep=1 would delete the
        # operator's real recovery points.
        scratch_context = tempfile.TemporaryDirectory(prefix="forgeos-recovery-")
        scratch = Path(scratch_context.name)
    else:
        scratch = Path(workdir)
    scratch.mkdir(parents=True, exist_ok=True)
    original_backups_dir = backup.BACKUPS_DIR
    backup.BACKUPS_DIR = scratch / "backups"
    try:
        live = _connect_read_only(source)
        try:
            live_counts = _row_counts(live)
        finally:
            live.close()

        snapshot = Path(backup.safe_backup(source, keep=1))
        restored_path = scratch / "restored.db"
        with gzip.open(snapshot, "rb") as source_file, restored_path.open("wb") as destination:
            shutil.copyfileobj(source_file, destination)

        restored = sqlite3.connect(restored_path)
        try:
            integrity = restored.execute("pragma integrity_check").fetchone()[0]
            if integrity != "ok":
                raise RecoveryVerificationError(f"integrity_check failed: {integrity}")
            violations = list(restored.execute("pragma foreign_key_check"))
            if violations:
                raise RecoveryVerificationError(
                    f"{len(violations)} foreign-key violations in the restored copy"
                )
            restored_names = _table_names(restored)
            stale = _stale_rebuild_tables(restored_names)
            if stale:
                raise RecoveryVerificationError(
                    f"stale rebuild tables in the restored copy: {', '.join(stale)}"
                )
            restored_counts = _row_counts(restored)
        finally:
            restored.close()

        missing = sorted(set(live_counts) - set(restored_counts))
        if missing:
            raise RecoveryVerificationError(
                f"tables missing from the restored copy: {', '.join(missing)}"
            )
        mismatched = {
            name: (live_counts[name], restored_counts[name])
            for name in sorted(live_counts)
            if live_counts[name] != restored_counts[name]
        }
        if mismatched:
            detail = ", ".join(
                f"{name}: live={live_count} restored={restored_count}"
                for name, (live_count, restored_count) in mismatched.items()
            )
            raise RecoveryVerificationError(
                f"row counts differ between live and restored ({detail}); "
                "re-run while no writer is active"
            )

        return {
            "database": str(source),
            "snapshot": str(snapshot),
            "snapshot_bytes": snapshot.stat().st_size,
            "integrity": integrity,
            "foreign_key_violations": 0,
            "stale_tables": stale,
            "tables": len(restored_counts),
            "row_counts": restored_counts,
            "rows_total": sum(restored_counts.values()),
            "canonical_database_modified": False,
        }
    finally:
        backup.BACKUPS_DIR = original_backups_dir
        if scratch_context is not None:
            scratch_context.cleanup()


def main() -> None:
    try:
        report = verify_recovery()
    except RecoveryVerificationError as exc:
        print(f"recovery=FAIL {exc}")
        raise SystemExit(1) from exc
    print(f"backup=pass ({report['snapshot']} {report['snapshot_bytes']} bytes)")
    print(f"restore=pass ({report['tables']} tables, {report['rows_total']} rows)")
    print("integrity=pass")
    print("foreign_keys=pass")
    print(f"stale_rebuild_tables={len(report['stale_tables'])}")
    print("row_counts_match=pass")
    for name in ("signals", "evidence", "cycle_runs"):
        if name in report["row_counts"]:
            print(f"{name}={report['row_counts'][name]}")
    print("canonical_database_modified=no")


if __name__ == "__main__":
    main()
