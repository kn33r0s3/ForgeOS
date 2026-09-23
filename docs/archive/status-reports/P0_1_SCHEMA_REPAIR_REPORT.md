# ForgeOS P0.1 — Surgical Schema Repair + Regression Validation

**Status:** Completed successfully.

**Repair scope:** Only the confirmed `evidence_relationships.judgment_id` schema mismatch was repaired. No frontend redesign, architecture redesign, economic logic change, provider change, table drop, reset, historical deletion, or broad schema synchronization was performed.

## 1. Exact root cause

The current SQLAlchemy model defined:

```python
judgment_id = Column(
    Integer,
    ForeignKey("judgments.id"),
    nullable=True,
    index=True,
)
```

The active SQLite database table `evidence_relationships` did not contain this column. The existing migration registry also omitted this table/column. Application code already reads and writes `judgment_id` through `evidence_graph.py` and `multi_judge.py`.

The table contained **0 rows**, and the `judgments` table also contained **0 rows**, so no existing record required a backfill or invented judgment ID.

The previously suspected columns were verified as already present and were not recreated:

- `experiments.option_id`
- `decisions.chosen_option_id`
- `decisions.option_space_status`

## 2. Exact schema change

Only these two DDL operations were applied:

```sql
ALTER TABLE evidence_relationships
ADD COLUMN judgment_id INTEGER REFERENCES judgments(id);

CREATE INDEX ix_evidence_relationships_judgment_id
ON evidence_relationships (judgment_id);
```

The column is nullable, has no default, and references `judgments.id`, exactly matching the SQLAlchemy model semantics. Existing rows remain untouched.

## 3. Migration/change method

The project’s existing lightweight migration mechanism was used. `backend/app/migrations.py` was updated to:

1. Add `evidence_relationships.judgment_id` to the existing `EXPECTED_COLUMNS` registry.
2. Add the single required model index through a narrowly scoped `EXPECTED_INDEXES` entry.

No new migration framework was introduced. No broad model-to-database synchronizer was run.

## 4. Safety backup

A second backup was created immediately before the repair:

[Download the pre-schema-repair backup](</home/ubuntu/work/storage/forgeos_pre_schema_repair_20260914_071522.db>)

```text
Backup path:
/home/ubuntu/work/storage/forgeos_pre_schema_repair_20260914_071522.db

Backup size:
32,702,464 bytes

SHA-256 before repair:
cc99bf0160d4e84282a9ea40c960bf1c56f91f3e3a45b819868859d4b3281ebf

SHA-256 of backup:
cc99bf0160d4e84282a9ea40c960bf1c56f91f3e3a45b819868859d4b3281ebf
```

The hashes matched exactly before modification.

## 5. Before/after schema verification

| Check | Before | After |
|---|---:|---:|
| `evidence_relationships` rows | 0 | 0 |
| Primary-key rows | 0 | 0 |
| `judgment_id` column | Missing | Present |
| `judgment_id` nullable | N/A | Yes |
| `judgment_id` target | N/A | `judgments.id` |
| `ix_evidence_relationships_judgment_id` | Missing | Present |
| Table set | 50 tables | Same 50 tables |
| Other table count changes | None | None |

The full table/index/schema evidence is preserved in the earlier raw diagnostic artifacts and the post-repair verification output.

## 6. SQLite integrity results

Immediately after the repair and again after API activity:

```text
PRAGMA integrity_check;
('ok',)

PRAGMA quick_check;
('ok',)

PRAGMA foreign_key_check;
(no rows)
```

The database remained readable and structurally valid.

## 7. Before/after table counts

No count decreased, and the important counts remain unchanged:

| Table/entity | Before baseline | After validation |
|---|---:|---:|
| signals | 11,847 | 11,847 |
| evidence | 17,815 | 17,815 |
| patterns | 7 | 7 |
| beliefs | 7 | 7 |
| opportunities | 8 | 8 |
| decisions | 8 | 8 |
| cycle_runs | 300 | 300 |
| actions | 0 | 0 |
| experiments | 0 | 0 |
| outcomes | 0 | 0 |
| learning_events | 0 | 0 |
| products | 0 | 0 |
| goals | 0 | 0 |
| strategies | 0 | 0 |
| earning_offers | 0 | 0 |
| actual REAL outcomes | 0 | 0 |
| actual REAL revenue | `$0.00` | `$0.00` |

No fake records were created during validation.

## 8. ORM verification

The repaired ORM was loaded from the backend working directory using the active database configuration:

```text
ORM_IMPORT_OK
EVIDENCE_RELATIONSHIP_ROWS 0
JUDGMENT_ROWS 0
EVIDENCE_ROWS_SAMPLE 1
JUDGMENT_ID_NULLABLE True
JUDGMENT_FK_TARGET ['judgments.id']
```

The SQLAlchemy model imported successfully, queried `evidence_relationships`, queried `judgments`, and queried related evidence.

## 9. Backend API regression results

The repaired backend was started with the real FastAPI application and existing installed runtime dependencies. All required non-mutating API checks returned valid JSON and HTTP 200:

| API surface | Status |
|---|---:|
| `/health` | 200 |
| `/stats` | 200 |
| `/observer/stats` | 200 |
| `/observer/signals?limit=8` | 200 |
| `/forge/money/dashboard` | 200 |
| `/forge/execution/recommend` | 200 |
| `/forge/beliefs` | 200 |
| `/forge/execution/actions` | 200 |
| `/forge/goals` | 200 |
| `/forge/autonomy/policy` | 200 |
| `/forge/money/revenue-breakdown` | 200 |
| `/forge/execution/actions/blocked` | 200 |
| `/forge/runtime` | 200 |
| `/opportunities` | 200 |
| `/earn/offers?workspace_key=regression-test-key` | 200 |
| `/orchestrate/flow` | 200 |
| `/products/pipeline` | 200 |
| `/openapi.json` | 200 |

OpenAPI verification confirmed that the required route definitions for `/analyze`, `/opportunities`, `/earn/offers`, `/orchestrate/flow`, `/products/pipeline`, `/forge/beliefs`, and `/forge/money/dashboard` remain present.

The first `/earn` test used a deliberately short test key and correctly returned validation status 422. It was rerun with a valid 16-character key and returned 200. No application defect was involved.

`POST /analyze` was not executed because it legitimately creates Signal, Opportunity, and Decision records; the route was verified non-mutatively through the OpenAPI contract to preserve the no-fabricated-data requirement.

## 10. Frontend regression results

The existing frontend production build completed successfully:

- Next.js build: successful
- TypeScript validation: successful
- Static page generation: successful
- 13/13 page data generation: successful

Valid frontend routes returned HTTP 200:

| Route | Status |
|---|---:|
| `/` | 200 |
| `/opportunities` | 200 |
| `/execution` | 200 |
| `/revenue` | 200 |
| `/knowledge` | 200 |
| `/flow` | 200 |
| `/earn` | 200 |
| `/products` | 200 |
| `/world` | 200 |
| `/analyze` | 200 |

`/system-flow` remains HTTP 404, as required. No invalid alias was created. The existing navigation points to `/flow`.

## 11. `/earn` verification

The `/earn` feature remains separate from the canonical Opportunity/Experiment/Action/Outcome loop.

Browser verification confirmed:

```text
keys: ["forgeos-nepal-workspace-key"]
offers: null
queue: null
workspaceKeyPresent: true
```

The page loaded successfully, preserved its local-first behavior, initialized a browser workspace key, retained the existing “saves offline” behavior, and did not create canonical economic records. Backend synchronization returned HTTP 200 for a valid workspace key. The `earning_offers` database count remained 0.

## 12. Actual files changed

### Application source

- `backend/app/migrations.py`
  - Added the confirmed `evidence_relationships.judgment_id` migration entry.
  - Added the single required `ix_evidence_relationships_judgment_id` index migration entry.

### Database

- `/home/ubuntu/work/storage/forge.db`
  - Added only the confirmed column and index through the existing migration mechanism.

### Backup created

- `/home/ubuntu/work/storage/forgeos_pre_schema_repair_20260914_071522.db`

### Not changed

- Frontend source files
- Backend models
- API routes
- Economic logic
- AI/provider architecture
- Existing historical records
- Existing unrelated schema

The failed normal startup attempt temporarily created `backend/.env`, `frontend/.env.local`, and a partial `backend/.venv`; these temporary artifacts were removed. No dependency lock or requirements file was changed.

## 13. Git status

The project archive does not contain a `.git` directory, so no Git commit was created. There is no repository history available in this extracted working directory.

Suggested commit title if this project is later placed under version control:

```text
fix: reconcile evidence relationship schema
```

## 14. Remaining known problems

1. `start.sh` lacks its executable bit, so `./start.sh` returns permission denied. Invoking `bash start.sh` reaches native setup.
2. The normal startup script’s dependency installation is currently blocked by a package hash mismatch in the locked requirements file. The dependency lock was not changed. This did not block validation with the already-installed runtime dependencies.
3. A historical `sqlite3.OperationalError: disk I/O error` remains in `logs/daily_cycle_log.jsonl` from 2026-09-12. Current integrity checks are clean; the historical filesystem/transaction cause remains unresolved.
4. The existing Next build reports optional SWC binary warnings but still compiles, type-checks, generates pages, and completes successfully.
5. The database is in WAL mode. Any future backup procedure should account for WAL sidecars and should be performed during an approved maintenance window.
6. `/system-flow` is intentionally not defined; `/flow` is the canonical route.

## 15. Recommended next P0/P1 task

**P0:** Investigate and harden the normal startup/deployment path without changing database semantics:

- resolve the dependency hash mismatch through an approved dependency-lock review;
- restore the executable bit on `start.sh` in the repository workflow;
- investigate the historical disk-I/O incident, including filesystem capacity, permissions, WAL/shm handling, concurrent writers, and transaction rollback behavior;
- add a migration regression test that compares every current ORM column, including `evidence_relationships.judgment_id`, against a fresh and existing database.

**P1:** Add a non-mutating startup schema diagnostic that reports model/database mismatches before a feature write path encounters them. Do not merge `/earn` into the canonical economic loop yet.

## Conclusion

The surgical repair is complete. The active database remains intact, all integrity checks pass, historical counts are unchanged, ORM access works, required backend APIs return valid responses, the frontend builds and routes load, `/earn` remains separate and intact, and actual revenue remains `$0.00`.
