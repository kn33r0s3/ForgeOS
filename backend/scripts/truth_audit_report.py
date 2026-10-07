from __future__ import annotations
import json
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / 'storage' / 'forge.db'
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
report = {'database': str(DB), 'integrity': con.execute('pragma integrity_check').fetchone()[0], 'tables': {}, 'anomalies': [], 'coverage': {}}
for row in con.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%' order by name"):
    name = row['name']
    report['tables'][name] = con.execute(f'select count(*) from "{name}"').fetchone()[0]

fk = list(con.execute('pragma foreign_key_check'))
if fk: report['anomalies'].append({'kind':'foreign_key_violations','count':len(fk)})
for table, column in [('signals','content_fingerprint'), ('signals','canonical_url'), ('opportunities','identity_key'), ('actions','id'), ('integration_deliveries','idempotency_key')]:
    columns = {r[1] for r in con.execute(f'pragma table_info("{table}")')}
    if column not in columns:
        continue
    extra = ' and is_duplicate_of is null' if table == 'signals' else ''
    dup = con.execute(f'''select "{column}", count(*) n from "{table}" where "{column}" is not null and trim(cast("{column}" as text)) <> '' {extra} group by "{column}" having n > 1''').fetchall()
    if dup:
        report['anomalies'].append({'kind':'duplicate_key','table':table,'column':column,'groups':len(dup)})
running = con.execute("select count(*) from cycle_runs where status='RUNNING'").fetchone()[0]
if running: report['anomalies'].append({'kind':'running_cycles','count':running})
for table, urlcol in [('signals','source_url'),('evidence','source_url'),('claims','source_url')]:
    try:
        total = con.execute(f'select count(*) from "{table}"').fetchone()[0]
        with_url = con.execute(f'''select count(*) from "{table}" where "{urlcol}" is not null and trim("{urlcol}") <> '' ''').fetchone()[0]
        report['coverage'][table] = {'total':total,'with_source_url':with_url,'ratio':round(with_url/total,4) if total else None}
    except sqlite3.OperationalError:
        pass
for table, statuscol in [('actions','status'),('outcomes','status'),('experiments','status'),('integration_deliveries','status')]:
    try:
        report['coverage'][table+'_statuses'] = dict(con.execute(f'''select "{statuscol}", count(*) from "{table}" group by "{statuscol}"''').fetchall())
    except sqlite3.OperationalError: pass
print(json.dumps(report, indent=2, default=str))
con.close()
