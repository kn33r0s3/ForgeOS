# ForgeOS P0 — Database Integrity Investigation

**Mode:** Read-only investigation. No schema, data, migration, VACUUM, reset, drop, or repair operation was performed.

**Only permitted database modification performed:** one byte-for-byte copy of the active database file for backup.

## Final classification

> **SCHEMA MISMATCH**

This database is **not currently supported by SQLite diagnostics as physically corrupted**. The original database passes `PRAGMA integrity_check`, `PRAGMA quick_check`, and `PRAGMA foreign_key_check`. There is, however, one confirmed model/database schema mismatch:

- `backend/app/models.py` expects `evidence_relationships.judgment_id`.
- The active SQLite table `evidence_relationships` does not contain `judgment_id`.
- `backend/app/migrations.py` does not list `evidence_relationships.judgment_id` in `EXPECTED_COLUMNS`.
- The previously reported columns `experiments.option_id`, `decisions.chosen_option_id`, and `decisions.option_space_status` are present.

The database also contains historical log evidence of `sqlite3.OperationalError: disk I/O error`, first seen in the archived daily-cycle log at `2026-09-12T09:53:58.594186+00:00`. That historical runtime/storage incident is not proof of current physical corruption; the current read-only SQLite checks are clean.

**Severity:** High for future evidence/judgment relationship writes and migration correctness; moderate for current operation because the tested read endpoints and current populated paths continue to work. The missing column should not be added until repair approval is given.

## 1. Exact active database identity

| Item | Result |
|---|---|
| Active native database | `/home/ubuntu/work/storage/forge.db` |
| Filename | `forge.db` |
| File size | `32,702,464` bytes |
| Modification time | `2026-09-14 06:04:09 UTC` |
| SQLite library version | `3.45.1` |
| Journal mode | `wal` |
| Synchronous mode | `2` (`FULL`) |
| Foreign-key enforcement setting | `0` for the diagnostic connection; `foreign_key_check` still returned no violations |
| Page count | `7,984` |
| Page size | `4,096` bytes |
| Schema version | `233` |
| User version | `0` |

### Which processes use which database

- Native backend default: `backend/app/config.py` resolves to the project-level `storage/forge.db`.
- `start.sh`: sets `DATABASE_URL=sqlite:///../storage/forge.db` while running from `backend/`, resolving to the same `/home/ubuntu/work/storage/forge.db`.
- Docker backend and worker: use `/app/storage/forge.db` inside the container, with host `./storage` mounted at `/app/storage`; therefore they use the host file `/home/ubuntu/work/storage/forge.db` when run from this project directory.
- Tests: `backend/tests/conftest.py` defaults to `sqlite:///:memory:` and individual tests use temporary SQLite files. Tests do not use the production/project database by default.
- No second ForgeOS production SQLite copy was found. Other `.db` files under `/home/ubuntu` belong to browser/package tooling, not ForgeOS.
- A timestamped backup now exists beside the original; it is not an active runtime database.

## 2. Raw backup verification

| Item | Result |
|---|---|
| Backup path | `/home/ubuntu/work/storage/forgeos_pre_repair_20260914_070700.db` |
| Original size | `32,702,464` bytes |
| Backup size | `32,702,464` bytes |
| Original SHA-256 | `cc99bf0160d4e84282a9ea40c960bf1c56f91f3e3a45b819868859d4b3281ebf` |
| Backup SHA-256 | `cc99bf0160d4e84282a9ea40c960bf1c56f91f3e3a45b819868859d4b3281ebf` |
| Byte-for-byte result | **MATCH** |

At diagnostic time, `forge.db-wal` existed but was `0` bytes. The backup is an exact copy of the active main database file; no database write or checkpoint was performed during this investigation.

## 3. Exact SQLite diagnostics against the original

The diagnostics used a read-only SQLite URI (`mode=ro`). Exact results:

```text
PRAGMA integrity_check;
{"integrity_check": "ok"}

PRAGMA foreign_key_check;
(no rows)

PRAGMA quick_check;
{"quick_check": "ok"}

PRAGMA journal_mode;
{"journal_mode": "wal"}

PRAGMA synchronous;
{"synchronous": 2}
```

These results do **not** support the classification `ACTUAL SQLITE CORRUPTION`.

## 4. Actual schema inventory

The database contains **50 tables**, **135 indexes**, **0 triggers**, and **0 views** according to `sqlite_master`. The application table names discovered are:

`actions`, `autonomy_policies`, `belief_experiments`, `beliefs`, `causal_knowledge`, `claims`, `confidence_events`, `customer_events`, `cycle_runs`, `decisions`, `distribution_channels`, `earning_offers`, `evidence`, `evidence_relationships`, `experiments`, `forecasters`, `goals`, `integration_deliveries`, `intelligence_cache_entries`, `judgment_comparisons`, `judgments`, `knowledge`, `learning_events`, `lessons`, `media_analyses`, `opportunities`, `opportunity_events`, `options`, `outcomes`, `patterns`, `predictions`, `products`, `rare_signal_assessments`, `rare_signal_events`, `research_questions`, `research_task_events`, `research_task_steps`, `research_tasks`, `revenue_sources`, `scenario_predictions`, `scenarios`, `signals`, `source_usage_events`, `sources`, `strategies`, `tool_usage_events`, `worker_tasks`, `world_claims`, `world_ideas`, and `world_source_documents`.

There are no database triggers or views. The complete `sqlite_master` output, every `PRAGMA table_info(table_name)`, and every `PRAGMA foreign_key_list(table_name)` result are preserved in [the raw diagnostics artifact](</home/ubuntu/work/P0_DATABASE_RAW_DIAGNOSTICS.txt>).

## 5. Expected schema comparison

The comparison used the current SQLAlchemy model metadata and `backend/app/migrations.py` without invoking migrations.

| Comparison | Result |
|---|---|
| Model tables missing from DB | None |
| Model columns missing from DB | `evidence_relationships.judgment_id` only |
| Unexpected DB columns relative to models | None reported |
| Migration `EXPECTED_COLUMNS` still missing | None among listed migration columns |
| `experiments.option_id` | Present |
| `decisions.chosen_option_id` | Present |
| `decisions.option_space_status` | Present |

### Confirmed mismatch

Current model excerpt:

```python
class EvidenceRelationship(Base):
    ...
    judgment_id = Column(Integer, ForeignKey("judgments.id"), nullable=True, index=True)
```

Actual database columns for `evidence_relationships`:

```text
id, evidence_id, claim_id, opportunity_id, decision_id,
experiment_id, outcome_id, relation_type, relation_key, created_at
```

`judgment_id` is absent. The migration registry covers many historical additions but does not include this table/column. This is a **migration coverage/schema mismatch**, not physical SQLite corruption.

## 6. Major table counts

Counts from the original database:

| Table/entity | Count |
|---|---:|
| signals | 11,847 |
| evidence | 17,815 |
| patterns | 7 |
| beliefs | 7 |
| opportunities | 8 |
| decisions | 8 |
| actions | 0 |
| experiments | 0 |
| outcomes | 0 |
| cycle_runs | 300 |
| goals | 0 |
| strategies | 0 |
| products | 0 |
| learning_events | 0 |
| lessons | 0 |
| revenue_sources | 4 |
| earning_offers | 0 |
| research_questions | 30 |
| research_tasks | 75 |
| worker_tasks | 445 |
| knowledge | 14 |
| predictions | 247 |
| claims | 0 |
| judgments | 0 |
| options | 0 |
| customer_events | 0 |
| distribution_channels | 0 |
| actual REAL outcomes | 0 |
| actual REAL revenue | `$0.00` |

Cycle status counts: `COMPLETED = 284`, `FAILED = 16`, with no running cycle at audit time.

The counts match the previous integration audit. No count drift was observed.

## 7. Relationship integrity

SQLite’s native `PRAGMA foreign_key_check` returned **no rows**. Additional read-only relationship checks using the actual column names found:

| Relationship | Total linked references | Valid | Orphaned/invalid |
|---|---:|---:|---:|
| evidence → signal | 17,815 | 17,815 | 0 |
| evidence → belief | 15,772 | 15,772 | 0 |
| evidence → opportunity FK | 0 | 0 | 0 |
| belief → pattern | 7 | 7 | 0 |
| decision → opportunity | 8 | 8 | 0 |
| action → decision | 0 | 0 | 0 |
| action → experiment | 0 | 0 | 0 |
| outcome → experiment | 0 | 0 | 0 |
| outcome → action | 0 | 0 | 0 |
| learning event → experiment | 0 | 0 | 0 |
| earning offer → opportunity | Not modeled | Not modeled | Not applicable |

Denormalized provenance IDs were also checked:

- Pattern origin signal IDs: 663 total, 663 valid, 0 orphaned.
- Belief supporting signal IDs: 663 total, 663 valid, 0 orphaned.
- Opportunity problem-evidence signal IDs: 6 total, 6 valid, 0 orphaned.
- Opportunity willingness-evidence IDs: 0 total, 0 orphaned.

Two opportunities have no `problem_evidence_signal_ids`. That is an evidence-completeness issue to review, not a broken foreign key; their opportunity records may still contain other inferred/estimated fields.

## 8. Duplicate records

No rows were deleted. The database does not enforce uniqueness for all content-level duplicates.

| Duplicate check | Groups | Excess rows | Interpretation |
|---|---:|---:|---|
| signals by `(content, source)` | 84 | 11,731 | Expected historical/duplicate ingestion pattern; `is_duplicate_of` and quality/provenance fields exist |
| signals by `content_fingerprint` | 0 | 0 | No duplicate non-empty fingerprints |
| evidence by `(content, signal_id, direction)` | 2,555 | 13,754 | Evidence is not uniquely constrained at this content tuple |
| opportunities by `identity_key` | 0 | 0 | No duplicate identity keys |
| opportunities by `(problem, target_customer, solution)` | 1 | 5 | Suspicious semantic duplicates; identity key rules are not identical to this tuple |
| decisions by `(opportunity_id, title)` | 0 | 0 | No duplicate groups |
| cycle runs by timestamps/status | 0 | 0 | No exact duplicate groups |
| earning offers by workspace/pathway/title/skill/customer | 0 | 0 | No duplicate groups |

These are data-quality/uniqueness observations, not proof of physical corruption. The signal duplication is consistent with the runtime truth audit’s large historical/duplicate signal population.

## 9. Impossible-state checks

| Check | Result |
|---|---:|
| Actual REAL outcome rows | 0 |
| Actual REAL revenue | `$0.00` |
| Positive experiment revenue | 0 rows / `$0.00` |
| Positive experiment without an outcome | 0 |
| Learning event without its experiment parent | 0 |
| Decision without opportunity | 0 |
| Outcome without action or experiment parent | 0 |
| Completed cycle without summary | 0 |
| Failed cycle records | 16 historical records |

No actual revenue exists without a real outcome. No executed action exists while the action table is empty. No learning event exists without measured activity. The 16 failed cycles are historical operational failures, not impossible states.

## 10. Relevant backend errors

The current `logs/backend.log`, `logs/worker.log`, and `storage/scheduler.log` do not provide a newer compact database error stream. The archived `logs/daily_cycle_log.jsonl` contains the first matching database incident at:

```text
2026-09-12T09:53:58.594186+00:00
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) disk I/O error
```

The same record includes a subsequent session-state failure:

```text
sqlalchemy.exc.InvalidRequestError:
This session is in 'prepared' state; no further SQL can be emitted within this transaction.
```

The exact first database error is therefore **`sqlite3.OperationalError: disk I/O error`**, not “database corrupted.” The current SQLite file passes integrity checks. The likely categories for that historical event are a transient filesystem/volume/WAL/locking problem or an application transaction failure; the available logs do not prove which one.

## 11. Git and migration findings

The extracted project directory is not a Git working tree (`.git` is absent), so commit history cannot be inspected. There is no recoverable Git history in this archive.

Available migration evidence:

- `backend/app/database.py` calls `Base.metadata.create_all()` and then `run_migrations(engine)` at backend startup.
- `backend/app/migrations.py` applies additive `ALTER TABLE ... ADD COLUMN` changes listed in `EXPECTED_COLUMNS`.
- `fix_schema.py` is a one-shot additive repair script for the previously known option columns.
- `verification/migration-proof.txt` reports a prior integrity check of `ok`, 11,847 signals, and 48 tables at that verification point.
- `backend/app/models.py` is newer than `backend/app/migrations.py` by file timestamp in this extracted project, and the model contains `EvidenceRelationship.judgment_id` while the migration registry does not.

This supports a **partially applied/uncaptured schema evolution** explanation for the one missing column.

## 12. Docker/native database conclusion

There is one ForgeOS host database for native and Docker execution:

```text
Native: /home/ubuntu/work/storage/forge.db
Docker: /app/storage/forge.db -> host mount /home/ubuntu/work/storage/forge.db
```

Tests are intentionally isolated in memory or temporary files. No stale second ForgeOS database was found. The result is **not** `MULTIPLE DATABASE / WRONG DATABASE`.

## 13. Exact root cause assessment

The evidence supports two separate issues:

1. **Current structural issue:** a schema mismatch caused by `evidence_relationships.judgment_id` being added to SQLAlchemy models without being present in the database or migration registry. This is the primary P0 finding.
2. **Historical runtime incident:** a `disk I/O error` occurred during a daily cycle on 2026-09-12, followed by a SQLAlchemy session state error. Current SQLite checks are clean, so this should be investigated as a storage/transaction incident, not labeled physical corruption.

The previous phrase “DATABASE IS CORRUPTED” is not supported by the current `integrity_check`, `quick_check`, or `foreign_key_check` results. The more precise statement is: **ForgeOS has a schema/migration mismatch and a historical disk-I/O incident; the active SQLite file is structurally readable and passes integrity diagnostics.**

## 14. Safest repair plan — not implemented

1. Preserve the verified byte-for-byte backup and do not modify the original until approval.
2. Before any write, stop every backend/worker process and capture a second operational backup strategy appropriate for WAL mode.
3. Add one explicit additive migration for `evidence_relationships.judgment_id` with its foreign key/index, after confirming the target deployment’s SQLAlchemy model version.
4. Run the migration only on a copy or after an approved maintenance window, then run `integrity_check`, `quick_check`, `foreign_key_check`, schema comparison, and the full backend test suite.
5. Investigate the historical disk-I/O incident separately: filesystem free space and write permissions, WAL/shm behavior, concurrent writers, backup/scheduler operations, and transaction rollback handling. Do not infer a cause from the error alone.
6. Add a migration test that compares every model column, including `evidence_relationships.judgment_id`, against a database created from the current schema.
7. Add a read-only startup diagnostic that reports schema mismatch explicitly instead of allowing a later write path to fail ambiguously.
8. Do not delete duplicates, orphan-like records, historical failed cycles, or evidence rows as part of this repair.

**No repair was implemented.**

## Evidence artifacts

- [Verified pre-repair database backup](</home/ubuntu/work/storage/forgeos_pre_repair_20260914_070700.db>)
- [Complete raw SQLite diagnostics](</home/ubuntu/work/P0_DATABASE_RAW_DIAGNOSTICS.txt>)
- [Model/migration schema comparison](</home/ubuntu/work/P0_DATABASE_SCHEMA_COMPARE.txt>)
- [Relationship/duplicate/impossible-state checks](</home/ubuntu/work/P0_DATABASE_DATA_INTEGRITY.txt>)
