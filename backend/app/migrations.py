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

# table -> [(column_name, DDL type + default), ...]
# Add future new columns here as Forge grows.
EXPECTED_COLUMNS = {
    "signals": [
        ("signal_type", "VARCHAR DEFAULT 'problem'"),
        ("importance_score", "FLOAT DEFAULT 0.0"),
        ("processed", "BOOLEAN DEFAULT 0"),
        ("tags", "TEXT"),
        ("reliability_score", "FLOAT DEFAULT 50.0"),
        ("freshness_score", "FLOAT DEFAULT 100.0"),
        ("quality_score", "FLOAT"),
        ("quality_flags", "TEXT"),
        ("is_duplicate_of", "INTEGER"),
        ("canonical_url", "VARCHAR"),
        ("external_id", "VARCHAR"),
        ("title", "TEXT"),
        ("published_at", "DATETIME"),
        ("retrieved_at", "DATETIME"),
        ("content_fingerprint", "VARCHAR"),
        ("source_type", "VARCHAR"),
        ("provenance", "TEXT"),
        ("collection_status", "VARCHAR DEFAULT 'observed'"),
        ("supersedes_signal_id", "INTEGER"),
    ],
    "patterns": [
        ("origin_signal_ids", "TEXT"),
        ("last_seen", "DATETIME"),
    ],
    "sources": [
        ("url", "VARCHAR"),
    ],
    "opportunities": [
        ("goal_id", "INTEGER"),
        ("customer_segment", "TEXT"),
        ("economic_consequence", "TEXT"),
        ("offer", "TEXT"),
        ("acquisition_path", "TEXT"),
        ("estimated_price", "FLOAT"),
        ("estimated_revenue", "FLOAT"),
        ("problem_evidence_signal_ids", "TEXT"),
        ("willingness_evidence_ids", "TEXT"),
        ("market_confidence", "FLOAT DEFAULT 0.0"),
        ("revenue_confidence", "FLOAT DEFAULT 0.0"),
        ("implementation_difficulty", "FLOAT"),
        ("acquisition_difficulty", "FLOAT"),
        ("uncertainty", "FLOAT DEFAULT 100.0"),
        ("competition_evidence", "TEXT"),
        ("expected_value", "FLOAT"),
        ("status", "VARCHAR DEFAULT 'identified'"),
        ("owner_priority", "FLOAT DEFAULT 50.0"),
        ("updated_at", "DATETIME"),
        ("monetization_model", "VARCHAR"),
        ("time_to_first_revenue_days", "FLOAT"),
        ("estimated_revenue_30d", "FLOAT"),
        ("estimated_revenue_90d", "FLOAT"),
        ("estimated_effort_hours", "FLOAT"),
        ("estimated_startup_cost", "FLOAT"),
        ("revenue_source_id", "INTEGER"),
        ("economic_evidence_summary", "TEXT"),
        ("identity_key", "VARCHAR"),
    ],
    "experiments": [
        ("hypothesis", "TEXT"),
        ("expected_result", "TEXT"),
        ("revenue", "FLOAT"),
        ("conversions", "INTEGER"),
        ("confidence_change", "FLOAT"),
        ("strategy_id", "INTEGER"),
        ("option_id", "INTEGER"),
        ("action_type", "VARCHAR"),
        ("status", "VARCHAR DEFAULT 'planned'"),
        ("execution_mode", "VARCHAR"),
        ("requires_owner_approval", "BOOLEAN DEFAULT 0"),
        ("approved_at", "DATETIME"),
        ("started_at", "DATETIME"),
        ("completed_at", "DATETIME"),
        ("costs", "FLOAT"),
        ("required_inputs", "TEXT"),
        ("estimated_cost", "FLOAT"),
        ("risk_score", "FLOAT"),
        ("policy_decision", "VARCHAR"),
        ("policy_reason", "TEXT"),
        ("attempt_number", "INTEGER DEFAULT 1"),
        # v2.0 domain isolation & fail-closed execution safety
        ("domain", "VARCHAR DEFAULT 'revenue'"),
        ("execution_allowed", "BOOLEAN DEFAULT 0"),
        ("data_scope", "VARCHAR DEFAULT 'REAL'"),
    ],
    "decisions": [
        ("chosen_option_id", "INTEGER"),
        ("option_space_status", "VARCHAR"),
        ("constraints", "JSON"),
        ("title", "VARCHAR"),
        ("rationale", "TEXT"),
        ("alternatives_considered", "TEXT"),
        ("expected_outcome", "TEXT"),
        ("expected_cost", "FLOAT"),
        ("expected_value", "FLOAT"),
        ("risk_notes", "TEXT"),
        ("confidence_at_decision", "FLOAT"),
        ("status", "VARCHAR DEFAULT 'proposed'"),
        ("decided_at", "DATETIME"),
        ("goal_id", "INTEGER"),
        ("opportunity_id", "INTEGER"),
        ("strategy_id", "INTEGER"),
        ("belief_id", "INTEGER"),
    ],
    "beliefs": [
        ("pattern_id", "INTEGER"),
    ],
    "confidence_events": [
        ("reason", "VARCHAR"),
        ("evidence_signal_ids", "TEXT"),
        ("experiment_id", "INTEGER"),
        ("scenario_prediction_id", "INTEGER"),
    ],
    "evidence": [
        ("scenario_prediction_id", "INTEGER"),
        ("opportunity_id", "INTEGER"),
        ("provenance_hash", "VARCHAR"),
        ("confidence", "FLOAT"),
        ("source", "VARCHAR"),
        ("content", "TEXT"),
        ("direction", "VARCHAR"),
        ("canonical_url", "VARCHAR"),
        ("external_id", "VARCHAR"),
        ("title", "TEXT"),
        ("published_at", "DATETIME"),
        ("retrieved_at", "DATETIME"),
        ("content_fingerprint", "VARCHAR"),
        ("provenance", "TEXT"),
        ("collection_status", "VARCHAR DEFAULT 'collected'"),
    ],
    "evidence_relationships": [
        ("judgment_id", "INTEGER REFERENCES judgments(id)"),
    ],
    "worker_tasks": [
        ("evidence", "JSON"),
        ("dependencies", "JSON"),
        ("worker_id", "VARCHAR"),
        ("role", "VARCHAR"),
    ],
    "research_tasks": [
        ("claim_id", "INTEGER"),
        ("objective", "TEXT"),
        ("plan", "JSON"),
        ("tools_used", "JSON"),
        ("evidence_ids", "TEXT"),
        ("claims", "JSON"),
        ("judgments", "JSON"),
        ("contradictions", "JSON"),
        ("remaining_questions", "JSON"),
        ("results", "JSON"),
        ("errors", "JSON"),
        ("current_step", "VARCHAR"),
        ("attempts", "INTEGER DEFAULT 0"),
        ("max_attempts", "INTEGER DEFAULT 3"),
        ("started_at", "DATETIME"),
        ("updated_at", "DATETIME"),
        ("completed_at", "DATETIME"),
    ],
    "research_questions": [
        ("source_claim_id", "INTEGER"),
        ("source_rare_signal_id", "INTEGER"),
    ],
    "rare_signal_assessments": [
        ("geographic_spread", "FLOAT DEFAULT 0.0"),
        ("language_spread", "FLOAT DEFAULT 0.0"),
        ("research_question_id", "INTEGER"),
    ],
    "outcomes": [
        ("product_id", "INTEGER"),
        ("data_scope", "VARCHAR DEFAULT 'REAL'"),
    ],
    "learning_events": [
        ("product_id", "INTEGER"),
        ("data_scope", "VARCHAR DEFAULT 'REAL'"),
    ],
    "lessons": [("data_scope", "VARCHAR DEFAULT 'REAL'")],
    "products": [("data_scope", "VARCHAR DEFAULT 'REAL'")],
    "distribution_channels": [("data_scope", "VARCHAR DEFAULT 'REAL'")],
    "customer_events": [("data_scope", "VARCHAR DEFAULT 'REAL'")],
    "earning_offers": [
        ("next_actions_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("outcome_note", "TEXT"),
    ],
}

# This is intentionally narrow: the current model defines one missing indexed
# column on an existing table. The lightweight column migration above cannot
# recreate indexes on an already-existing SQLite table, so keep the one
# required index explicit rather than introducing a broad schema synchronizer.
EXPECTED_INDEXES = {
    "evidence_relationships": [
        ("ix_evidence_relationships_judgment_id", "judgment_id"),
    ],
}


def run_migrations(engine: Engine) -> list[str]:
    """
    Inspect the live database and add any missing columns listed in
    EXPECTED_COLUMNS. Returns the list of ALTER TABLE statements that
    were actually run (empty list if the schema was already current).
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    applied: list[str] = []

    for table, columns in EXPECTED_COLUMNS.items():
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
