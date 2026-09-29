"""The recovery drill must prove a snapshot restores to an equal database."""

import gzip
import sqlite3

import pytest

from app.services import backup
from scripts import recovery_verify


def _make_db(path, signals: int = 3) -> None:
    con = sqlite3.connect(path)
    try:
        con.execute("create table signals (id integer primary key, content text)")
        con.execute("create table signal_entities (id integer primary key)")
        con.execute("create table integration_deliveries (id integer primary key)")
        for index in range(signals):
            con.execute("insert into signals (content) values (?)", (f"signal-{index}",))
            con.execute("insert into signal_entities default values")
        con.commit()
    finally:
        con.close()


def test_verify_recovery_matches_live_counts_without_a_fixed_number(tmp_path):
    db = tmp_path / "forge.db"
    _make_db(db, signals=5)

    report = recovery_verify.verify_recovery(db_path=db, workdir=tmp_path / "drill")

    assert report["integrity"] == "ok"
    assert report["foreign_key_violations"] == 0
    assert report["stale_tables"] == []
    assert report["row_counts"]["signals"] == 5
    assert report["row_counts"]["signal_entities"] == 5
    assert report["rows_total"] == 10
    assert report["canonical_database_modified"] is False
    assert report["snapshot_bytes"] > 0


def test_verify_recovery_grows_with_real_data(tmp_path):
    first = tmp_path / "first" / "forge.db"
    second = tmp_path / "second" / "forge.db"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    _make_db(first, signals=2)
    _make_db(second, signals=7)

    small = recovery_verify.verify_recovery(db_path=first, workdir=tmp_path / "a")
    large = recovery_verify.verify_recovery(db_path=second, workdir=tmp_path / "b")

    assert small["row_counts"]["signals"] == 2
    assert large["row_counts"]["signals"] == 7


def test_verify_recovery_rejects_a_snapshot_that_lost_rows(tmp_path, monkeypatch):
    db = tmp_path / "forge.db"
    _make_db(db, signals=4)
    truncated = tmp_path / "truncated.db"
    _make_db(truncated, signals=1)

    def lossy_backup(source, keep=1):
        target = tmp_path / "lossy" / "forge_lossy.db.gz"
        target.parent.mkdir(parents=True, exist_ok=True)
        with truncated.open("rb") as raw, gzip.open(target, "wb") as packed:
            packed.write(raw.read())
        return target

    monkeypatch.setattr(backup, "safe_backup", lossy_backup)

    with pytest.raises(recovery_verify.RecoveryVerificationError) as excinfo:
        recovery_verify.verify_recovery(db_path=db, workdir=tmp_path / "drill")

    message = str(excinfo.value)
    assert "row counts differ" in message
    assert "signals" in message


def test_verify_recovery_rejects_a_missing_database(tmp_path):
    with pytest.raises(recovery_verify.RecoveryVerificationError):
        recovery_verify.verify_recovery(db_path=tmp_path / "absent.db", workdir=tmp_path / "drill")


def test_drill_never_prunes_the_canonical_backups_and_restores_the_directory(tmp_path, monkeypatch):
    """A drill with no workdir must keep the operator's real snapshots intact."""
    db = tmp_path / "forge.db"
    _make_db(db, signals=3)
    real_backups = tmp_path / "backups"
    real_backups.mkdir()
    existing = real_backups / "forge_20260901T000000000000Z.db.gz"
    existing.write_bytes(b"an operator recovery point")
    monkeypatch.setattr(backup, "BACKUPS_DIR", real_backups)

    recovery_verify.verify_recovery(db_path=db)

    assert existing.exists()
    assert existing.read_bytes() == b"an operator recovery point"
    assert backup.BACKUPS_DIR == real_backups
