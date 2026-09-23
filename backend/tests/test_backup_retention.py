from pathlib import Path

from scripts import backup_retention


def test_plan_legacy_keeps_two_newest_and_never_selects_live_db(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_retention, "STORAGE", tmp_path)
    live = tmp_path / "forge.db"
    live.write_text("live")
    snapshots = []
    for index in range(4):
        path = tmp_path / f"forgeos_pre_{index}.db"
        path.write_text(str(index))
        path.touch()
        snapshots.append(path)
    kept, archived = backup_retention.plan_legacy(2)
    assert len(kept) == 2
    assert len(archived) == 2
    assert live not in kept + archived


def test_archive_legacy_snapshots_moves_older_files_and_keeps_live_db(tmp_path, monkeypatch):
    from app.services import backup

    live = tmp_path / "forge.db"
    live.write_text("live")
    monkeypatch.setattr(backup, "_db_path", lambda: live)
    snapshots = []
    for index in range(4):
        path = tmp_path / f"forgeos_pre_{index}.db"
        path.write_text(str(index))
        path.touch()
        snapshots.append(path)
    result = backup.archive_legacy_snapshots(keep=2)
    assert live.read_text() == "live"
    assert len(result["kept"]) == 2
    assert len(result["archived"]) == 2
    assert len(list(tmp_path.glob("forgeos_pre_*.db"))) == 2
    assert len(list((tmp_path / "backups" / "legacy").glob("forgeos_pre_*.db"))) == 2
