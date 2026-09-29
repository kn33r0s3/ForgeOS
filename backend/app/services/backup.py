"""Safe, consistent SQLite snapshots and scheduler logging."""

import gzip
import json
import logging
import os
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("forgeos.backup")
_DEFAULT_STORAGE = Path(__file__).resolve().parent.parent.parent.parent / "storage"
BACKUPS_DIR = _DEFAULT_STORAGE / "backups"
SCHEDULER_LOG = _DEFAULT_STORAGE / "scheduler.log"


def _db_path() -> Path:
    from app.config import settings
    raw = settings.DATABASE_URL
    if raw.startswith("sqlite:///"):
        return Path(raw.replace("sqlite:///", "", 1))
    return _DEFAULT_STORAGE / "forge.db"


def _validate_keep(keep: int) -> int:
    try:
        keep = int(keep)
    except (TypeError, ValueError) as exc:
        raise ValueError("keep must be an integer >= 1") from exc
    if keep < 1:
        raise ValueError("keep must be >= 1")
    return keep


def safe_backup(db_path: Path | None = None, keep: int = 10) -> Path | str:
    keep = _validate_keep(keep)
    src = (db_path or _db_path()).resolve()
    if not src.exists():
        return f"no database at {src} to back up"
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    tmp_plain = BACKUPS_DIR / f"forge_{stamp}.db.tmp"
    final_gz = BACKUPS_DIR / f"forge_{stamp}.db.gz"
    try:
        con = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30)
        try:
            con.execute("VACUUM INTO ?", (str(tmp_plain),))
        finally:
            con.close()
        with tmp_plain.open("rb") as fi, gzip.open(final_gz, "wb", compresslevel=6) as fo:
            shutil.copyfileobj(fi, fo)
        _verify_snapshot(final_gz)
        tmp_plain.unlink(missing_ok=True)
        _prune(keep)
        log.info("backup written: %s", final_gz)
        return final_gz
    except Exception:
        tmp_plain.unlink(missing_ok=True)
        final_gz.unlink(missing_ok=True)
        raise


def _verify_snapshot(path: Path) -> None:
    with gzip.open(path, "rb") as source:
        raw = source.read()
    disk = sqlite3.connect(":memory:")
    try:
        disk.deserialize(raw)
        row = disk.execute("PRAGMA integrity_check").fetchone()
        if not row or row[0] != "ok":
            raise sqlite3.DatabaseError(f"backup integrity check failed: {row}")
    finally:
        disk.close()


def _prune(keep: int) -> None:
    snaps = sorted(BACKUPS_DIR.glob("forge_*.db.gz"), key=lambda p: p.stat().st_mtime_ns)
    for old in snaps[:-keep]:
        try:
            old.unlink(missing_ok=True)
        except OSError:
            log.warning("Could not prune backup %s", old, exc_info=True)



def archive_legacy_snapshots(keep: int = 2) -> dict[str, list[str]]:
    """Keep the newest legacy pre-change DBs on the main volume and move older
    ones into backups/legacy. The live forge.db is never selected."""
    keep = _validate_keep(keep)
    storage = _db_path().resolve().parent
    archive_dir = storage / "backups" / "legacy"
    candidates = sorted(
        storage.glob("forgeos_pre_*.db"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    kept = candidates[:keep]
    archived: list[Path] = []
    if candidates[keep:]:
        archive_dir.mkdir(parents=True, exist_ok=True)
    for source in candidates[keep:]:
        destination = archive_dir / source.name
        if destination.exists():
            # A prior retention pass already archived this immutable snapshot.
            source.unlink(missing_ok=True)
        else:
            shutil.move(str(source), destination)
        checksum = source.with_suffix(".sha256")
        if checksum.exists():
            checksum_destination = archive_dir / checksum.name
            if checksum_destination.exists():
                checksum.unlink(missing_ok=True)
            else:
                shutil.move(str(checksum), checksum_destination)
        archived.append(destination)
    return {
        "kept": [str(path) for path in kept],
        "archived": [str(path) for path in archived],
    }

def append_scheduler_log(event: str, status: str, record: dict, duration_ms: int) -> None:
    line = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, "status": status,
            "duration_ms": duration_ms, "detail": record.get("forge_cycle", {}).get("cycle_id")}
    if os.getenv("VERCEL"):
        log.info("Scheduler event: %s", json.dumps(line, default=str))
        return
    try:
        SCHEDULER_LOG.parent.mkdir(parents=True, exist_ok=True)
        with SCHEDULER_LOG.open("a") as f:
            f.write(json.dumps(line, default=str) + "\n")
    except Exception:
        log.exception("Could not write scheduler log")
