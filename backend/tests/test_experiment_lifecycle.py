import sqlite3
import tempfile

from sqlalchemy import create_engine

from app.migrations import run_migrations


def test_run_migrations_rebuilds_legacy_experiments_table_without_losing_rows():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        database_path = tmp.name

    with sqlite3.connect(database_path) as conn:
        conn.execute("CREATE TABLE opportunities (id INTEGER PRIMARY KEY)")
        conn.execute(
            """
            CREATE TABLE experiments (
                id INTEGER PRIMARY KEY,
                opportunity_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planned',
                created_at TEXT
            )
            """
        )
        conn.execute("INSERT INTO opportunities (id) VALUES (1)")
        conn.execute(
            "INSERT INTO experiments (opportunity_id, action, status, created_at) VALUES (?, ?, ?, ?)",
            (1, "research", "planned", "2024-01-01T00:00:00Z"),
        )
        conn.execute(
            "INSERT INTO experiments (opportunity_id, action, status, created_at) VALUES (?, ?, ?, ?)",
            (1, "outreach", "completed", "2024-01-02T00:00:00Z"),
        )
        conn.execute(
            """
            CREATE TABLE claims (
                id INTEGER PRIMARY KEY,
                experiment_id INTEGER,
                FOREIGN KEY(experiment_id) REFERENCES experiments (id)
            )
            """
        )
        conn.commit()

    engine = create_engine(f"sqlite:///{database_path}")
    run_migrations(engine)

    with sqlite3.connect(database_path) as probe:
        pragma = probe.execute("PRAGMA table_info(experiments)").fetchall()
        columns = {row[1]: row[3] for row in pragma}
        records = probe.execute(
            "SELECT opportunity_id, action, status FROM experiments ORDER BY id"
        ).fetchall()
        claims_sql = probe.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'claims'"
        ).fetchone()[0]
        probe.execute("PRAGMA foreign_keys=ON")
        probe.execute("INSERT INTO claims (experiment_id) VALUES (1)")

    assert columns["opportunity_id"] == 0, "legacy Experiments table should be rebuilt to allow NULL opportunity_id"
    assert records == [
        (1, "research", "planned"),
        (1, "outreach", "completed"),
    ]
    assert "experiments__old" not in claims_sql
    assert "REFERENCES experiments" in claims_sql


def test_run_migrations_repairs_foreign_keys_left_on_experiments_old():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        database_path = tmp.name

    with sqlite3.connect(database_path) as conn:
        conn.execute("CREATE TABLE opportunities (id INTEGER PRIMARY KEY)")
        conn.execute(
            """
            CREATE TABLE experiments (
                id INTEGER PRIMARY KEY,
                opportunity_id INTEGER,
                action TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'planned',
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE claims (
                id INTEGER PRIMARY KEY,
                experiment_id INTEGER,
                FOREIGN KEY(experiment_id) REFERENCES "experiments__old" (id)
            )
            """
        )
        conn.execute("INSERT INTO experiments (id, opportunity_id, action) VALUES (1, 1, 'research')")
        conn.commit()

    engine = create_engine(f"sqlite:///{database_path}")
    applied = run_migrations(engine)

    with sqlite3.connect(database_path) as probe:
        claims_sql = probe.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'claims'"
        ).fetchone()[0]
        probe.execute("PRAGMA foreign_keys=ON")
        probe.execute("INSERT INTO claims (experiment_id) VALUES (1)")

    assert any("experiments__old" in item for item in applied)
    assert "experiments__old" not in claims_sql
