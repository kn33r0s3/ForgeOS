import gzip
import sqlite3
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_safe_backup_returns_existing_gzip_and_validates_keep(tmp_path):
    from app.services import backup
    src = tmp_path / "source.db"
    con = sqlite3.connect(src)
    con.execute("create table t(x integer)")
    con.execute("insert into t values (7)")
    con.commit(); con.close()
    backup.BACKUPS_DIR = tmp_path / "backups"
    result = backup.safe_backup(src, keep=1)
    assert isinstance(result, Path)
    assert result.exists() and result.suffix == ".gz"
    with gzip.open(result, "rb") as f:
        restored = tmp_path / "restored.db"
        restored.write_bytes(f.read())
    chk = sqlite3.connect(restored)
    assert chk.execute("pragma integrity_check").fetchone()[0] == "ok"
    assert chk.execute("select x from t").fetchone() == (7,)
    chk.close()
    with pytest.raises(ValueError):
        backup.safe_backup(src, keep=0)


def test_scheduler_uses_canonical_run_once_and_next_tick_survives(monkeypatch):
    from app.services import cycle_scheduler
    calls = []
    def fake():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("first")
        return {"forge_cycle": {}, "autonomy_cycle": {}}
    monkeypatch.setattr(cycle_scheduler.run_daily_cycle, "run_once", fake)
    s = cycle_scheduler.CycleScheduler(interval_seconds=10, backup_interval_seconds=None, max_run_seconds=2)
    s._tick(); s._tick()
    assert len(calls) == 2


def test_scheduler_timeout_is_truthful_and_blocks_overlap(monkeypatch):
    from app.services import cycle_scheduler
    entered = threading.Event()
    release = threading.Event()
    calls = []
    def slow():
        calls.append(1); entered.set(); release.wait(2)
        return {"forge_cycle": {}, "autonomy_cycle": {}}
    monkeypatch.setattr(cycle_scheduler.run_daily_cycle, "run_once", slow)
    s = cycle_scheduler.CycleScheduler(interval_seconds=10, backup_interval_seconds=None, max_run_seconds=1)
    start = time.monotonic(); s._tick(); elapsed = time.monotonic() - start
    assert entered.is_set() and elapsed < 1.8
    assert calls == [1]
    release.set()
