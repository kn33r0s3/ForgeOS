"""
Lightweight, dependency-free schema migrations.

Forge deliberately doesn't pull in Alembic for v0.1 — one extra
dependency and a migrations/ directory would be overkill for a single
SQLite file on a local laptop. Instead: on startup, check which
columns actually exist on each table and ALTER TABLE ADD COLUMN for
anything the current models.py expects but the on-disk database
doesn't have yet. Existing rows are untouched; new columns get their
default value.

This only ever ADDS columns — it never drops or renames anything, so
it's safe to run on every startup. If Forge later needs real schema
migrations (column renames, data backfills, Postgres), swap this for
Alembic; nothing outside database.py needs to change.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.schema import CreateTable
from sqlalchemy.dialects import sqlite

# table -> [(column_name, DDL type + default), ...]
# Build the manifest from the live SQLAlchemy metadata so older SQLite files
# get every column the current ORM expects. This keeps the migration path in
# sync with models.py without having to maintain a stale hand-written list.
def _sql_type_for(column) -> str:
    """Map SQLAlchemy column types to SQLite-friendly DDL fragments."""
    from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text

    if isinstance(column.type, JSON):
        return "JSON"
    if isinstance(column.type, Boolean):
        return "BOOLEAN"
    if isinstance(column.type, DateTime):
        return "DATETIME"
    if isinstance(column.type, Float):
        return "FLOAT"
    if isinstance(column.type, Integer):
        return "INTEGER"
    if isinstance(column.type, Text):
        return "TEXT"
    if isinstance(column.type, String):
        return "VARCHAR"
    return "TEXT"


def _default_sql_for(column) -> str:
    """Return SQLite DEFAULT syntax for a column, if a literal default exists."""
    default = getattr(column, "default", None)
    if default is not None:
        default_value = getattr(default, "arg", None)
        if default_value is not None and not callable(default_value):
            if isinstance(default_value, bool):
                return f"DEFAULT {int(default_value)}"
            if isinstance(default_value, str):
                escaped = default_value.replace("'", "''")
                return f"DEFAULT '{escaped}'"
            if isinstance(default_value, (int, float)):
                return f"DEFAULT {default_value}"
    server_default = getattr(column, "server_default", None)
    if server_default is not None:
        text = getattr(server_default, "text", None)
        if text is not None:
            return f"DEFAULT {text}"
    return ""


def _build_expected_columns() -> dict[str, list[tuple[str, str]]]:
    from app.database import Base

    expected: dict[str, list[tuple[str, str]]] = {}
    for table in Base.metadata.sorted_tables:
        column_entries: list[tuple[str, str]] = []
        for column in table.columns:
            if column.primary_key:
                continue
            column_type = _sql_type_for(column)
            default_sql = _default_sql_for(column)
            ddl = column_type if not default_sql else f"{column_type} {default_sql}"
            column_entries.append((column.name, ddl))
        if column_entries:
            expected[table.name] = column_entries
    return expected


EXPECTED_COLUMNS = _build_expected_columns()

# Column additions are safe on existing SQLite files, but they do not create
# indexes declared on the ORM model. Keep the small set of indexes for newly
# added query paths explicit rather than pretending create_all repairs them.
EXPECTED_INDEXES = {
    "evidence_relationships": [
        ("ix_evidence_relationships_judgment_id", "judgment_id"),
        ("ix_evidence_relationships_network_connection_id", "network_connection_id"),
    ],
    "evidence": [
        ("ix_evidence_subject_id", "subject_id"),
    ],
    "network_connections": [
        ("ix_network_connections_relation_id", "relation_id"),
        ("ix_network_connections_relation_type", "relation_type"),
        ("ix_network_connections_epistemic_state", "epistemic_state"),
    ],
}

# SQLite ALTER TABLE cannot add a UNIQUE constraint in place. These nullable
# idempotency columns are added first, then guarded by unique indexes; existing
# rows keep NULL and all history/data remains intact.
EXPECTED_UNIQUE_INDEXES = {
    "entities": [("uq_entities_identity_key", "identity_key")],
    "relations": [("uq_relations_idempotency_key", "idempotency_key")],
    "events": [("uq_events_idempotency_key", "idempotency_key")],
}


def _repair_stale_experiment_references(engine: Engine) -> int:
    """Point foreign keys back at experiments after a rename-based rebuild."""
    if engine.dialect.name != "sqlite":
        return 0
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT type, name, sql FROM sqlite_master WHERE sql LIKE '%experiments__old%'")
        ).fetchall()
        if not rows:
            return 0
        conn.execute(text("PRAGMA writable_schema=ON"))
        for _row_type, name, sql in rows:
            fixed = sql.replace('"experiments__old"', "experiments").replace(
                "experiments__old", "experiments"
            )
            conn.execute(
                text("UPDATE sqlite_master SET sql = :sql WHERE name = :name"),
                {"sql": fixed, "name": name},
            )
        conn.execute(text("PRAGMA writable_schema=RESET"))
    return len(rows)


def _backfill_network_connection_semantics(engine: Engine) -> int:
    """Copy legacy relation meaning onto its canonical connection row."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "network_connections" not in tables or "relations" not in tables:
        return 0
    columns = {column["name"] for column in inspector.get_columns("network_connections")}
    required = {
        "relation_id", "relation_type", "epistemic_state", "direction",
        "valid_from", "valid_until", "observed_at", "created_at",
    }
    if not required <= columns:
        return 0

    statements = (
        "UPDATE network_connections SET relation_type = ("
        "SELECT relation_type FROM relations WHERE relations.id = network_connections.relation_id) "
        "WHERE relation_id IS NOT NULL AND relation_type = 'possible_match' "
        "AND EXISTS (SELECT 1 FROM relations WHERE relations.id = network_connections.relation_id)",
        "UPDATE network_connections SET epistemic_state = ("
        "SELECT truth_state FROM relations WHERE relations.id = network_connections.relation_id) "
        "WHERE relation_id IS NOT NULL AND epistemic_state = 'hypothesized' "
        "AND EXISTS (SELECT 1 FROM relations WHERE relations.id = network_connections.relation_id)",
        "UPDATE network_connections SET direction = ("
        "SELECT direction FROM relations WHERE relations.id = network_connections.relation_id) "
        "WHERE relation_id IS NOT NULL AND direction = 'directed' "
        "AND EXISTS (SELECT 1 FROM relations WHERE relations.id = network_connections.relation_id)",
        "UPDATE network_connections SET valid_from = ("
        "SELECT valid_from FROM relations WHERE relations.id = network_connections.relation_id) "
        "WHERE valid_from IS NULL AND relation_id IS NOT NULL",
        "UPDATE network_connections SET valid_until = ("
        "SELECT valid_to FROM relations WHERE relations.id = network_connections.relation_id) "
        "WHERE valid_until IS NULL AND relation_id IS NOT NULL",
        "UPDATE network_connections SET observed_at = created_at WHERE observed_at IS NULL",
    )
    changed = 0
    with engine.begin() as conn:
        for statement in statements:
            changed += conn.execute(text(statement)).rowcount or 0
    return changed


def run_migrations(engine: Engine) -> list[str]:
    """
    Inspect the live database and add any missing columns listed in
    EXPECTED_COLUMNS. Returns the list of ALTER TABLE statements that
    were actually run (empty list if the schema was already current).
    """
    from app import models  # noqa: F401 — register tables before reading metadata

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    applied: list[str] = []

    for table, columns in _build_expected_columns().items():
        if table not in existing_tables:
            # Table doesn't exist yet — Base.metadata.create_all() (run
            # right before this) will have created it fresh with every
            # column already defined in models.py, so there's nothing
            # to migrate here.
            continue

        existing_columns = {col["name"] for col in inspector.get_columns(table)}

        for column_name, ddl in columns:
            if column_name in existing_columns:
                continue
            statement = f"ALTER TABLE {table} ADD COLUMN {column_name} {ddl}"
            with engine.begin() as conn:
                conn.execute(text(statement))
            applied.append(statement)

    if "experiments" in existing_tables:
        columns = inspector.get_columns("experiments")
        opportunity_id_col = next((c for c in columns if c["name"] == "opportunity_id"), None)
        if opportunity_id_col and opportunity_id_col.get("nullable") is False:
            from app import models

            stale_temp_tables = ["experiments__old", "experiments__new"]
            with engine.begin() as conn:
                for temp_table in stale_temp_tables:
                    if temp_table in inspector.get_table_names():
                        conn.execute(text(f"DROP TABLE {temp_table}"))

            temp_name = "experiments__new"
            create_sql = str(CreateTable(models.Experiment.__table__).compile(dialect=sqlite.dialect()))
            create_new_sql = create_sql.replace("experiments", temp_name)
            insert_columns = [column.name for column in models.Experiment.__table__.columns]
            quoted_columns = ", ".join(f'"{name}"' for name in insert_columns)
            # Copy into a new table, then drop the old one. Renaming
            # `experiments` first rewrites every child foreign key to the
            # temporary name, and those references survive the drop.
            insert_sql = (
                f"INSERT INTO {temp_name} ({quoted_columns}) "
                f"SELECT {quoted_columns} FROM experiments"
            )
            with engine.begin() as conn:
                conn.execute(text("PRAGMA foreign_keys=OFF"))
                conn.execute(text(create_new_sql))
                conn.execute(text(insert_sql))
                conn.execute(text("DROP TABLE experiments"))
                conn.execute(text(f"ALTER TABLE {temp_name} RENAME TO experiments"))
            applied.append("rebuild experiments table to allow nullable opportunity_id")

    if "opportunities" in existing_tables:
        columns = inspect(engine).get_columns("opportunities")
        nullable_fields = {"target_customer", "solution", "business_model"}
        needs_rebuild = any(
            column["name"] in nullable_fields and column.get("nullable") is False
            for column in columns
        )
        if needs_rebuild:
            from app import models

            temp_name = "opportunities__new"
            create_sql = str(CreateTable(models.Opportunity.__table__).compile(dialect=sqlite.dialect()))
            create_new_sql = create_sql.replace("opportunities", temp_name)
            insert_columns = [column.name for column in models.Opportunity.__table__.columns]
            quoted_columns = ", ".join(f'"{name}"' for name in insert_columns)
            insert_sql = (
                f"INSERT INTO {temp_name} ({quoted_columns}) "
                f"SELECT {quoted_columns} FROM opportunities"
            )
            with engine.begin() as conn:
                conn.execute(text("PRAGMA foreign_keys=OFF"))
                conn.execute(text(create_new_sql))
                conn.execute(text(insert_sql))
                conn.execute(text("DROP TABLE opportunities"))
                conn.execute(text(f"ALTER TABLE {temp_name} RENAME TO opportunities"))
            applied.append("rebuild opportunities table to allow unknown hypothesis fields")

    repaired = _repair_stale_experiment_references(engine)
    if repaired:
        applied.append(f"rewrote {repaired} schema objects still referencing experiments__old")

    backfilled_connections = _backfill_network_connection_semantics(engine)
    if backfilled_connections:
        applied.append(
            f"copied legacy relation semantics onto {backfilled_connections} network connection fields"
        )

    inspector = inspect(engine)
    for table, indexes in EXPECTED_INDEXES.items():
        if table not in inspector.get_table_names():
            continue
        existing_indexes = {index["name"] for index in inspector.get_indexes(table)}
        for index_name, column_name in indexes:
            if index_name in existing_indexes:
                continue
            statement = f"CREATE INDEX {index_name} ON {table} ({column_name})"
            with engine.begin() as conn:
                conn.execute(text(statement))
            applied.append(statement)

    inspector = inspect(engine)
    for table, indexes in EXPECTED_UNIQUE_INDEXES.items():
        if table not in inspector.get_table_names():
            continue
        existing_indexes = {index["name"] for index in inspector.get_indexes(table)}
        existing_unique_columns = {
            tuple(constraint["column_names"])
            for constraint in inspector.get_unique_constraints(table)
        }
        for index_name, column_name in indexes:
            if index_name in existing_indexes or (column_name,) in existing_unique_columns:
                continue
            statement = f"CREATE UNIQUE INDEX {index_name} ON {table} ({column_name})"
            with engine.begin() as conn:
                conn.execute(text(statement))
            applied.append(statement)

    # Phase 1 provenance backfill (idempotent)
    if "signals" in existing_tables:
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE signals SET source_type = 'seed' "
                "WHERE source = 'seed' AND (source_type IS NULL OR source_type = 'manual')"
            ))
            conn.execute(text(
                "UPDATE signals SET source_type = 'external' "
                "WHERE source IN ('github', 'reddit', 'rss', 'news', 'arxiv', 'web') AND (source_type IS NULL OR source_type = 'manual')"
            ))
            conn.execute(text(
                "UPDATE signals SET source_type = 'manual' "
                "WHERE source = 'manual' AND (source_type IS NULL OR source_type = 'manual')"
            ))
            conn.execute(text(
                "UPDATE signals SET source_type = 'synthetic' "
                "WHERE source = 'synthetic' AND (source_type IS NULL OR source_type = 'manual')"
            ))

    return applied
