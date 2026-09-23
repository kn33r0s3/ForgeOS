from __future__ import annotations
import gzip, shutil, sqlite3, tempfile
from pathlib import Path
from app.services import backup

root = Path(__file__).resolve().parents[2]
source = root / 'storage' / 'forge.db'
with tempfile.TemporaryDirectory(prefix='forgeos-recovery-') as tmp:
    tmp_path = Path(tmp)
    backup.BACKUPS_DIR = tmp_path / 'backups'
    snapshot = Path(backup.safe_backup(source, keep=1))
    restored = tmp_path / 'restored.db'
    with gzip.open(snapshot, 'rb') as src, restored.open('wb') as dst:
        shutil.copyfileobj(src, dst)
    con = sqlite3.connect(restored)
    assert con.execute('pragma integrity_check').fetchone()[0] == 'ok'
    assert con.execute('select count(*) from signals').fetchone()[0] == 11847
    assert con.execute("select count(*) from sqlite_master where type='table' and name='integration_deliveries'").fetchone()[0] == 1
    con.close()
print('backup=pass')
print('restore=pass')
print('integrity=pass')
print('canonical_database_modified=no')
