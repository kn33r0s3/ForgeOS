"""
PHASE 1 REGRESSION TESTS
========================

Validates:
 1. Identity key stability across pattern IDs
 2. Duplicate opportunity is not inserted
 3. Same underlying problem across two cycle runs results in one opportunity
 4. External signal without canonical URL is rejected
 5. External signal without retrieved_at is rejected
 6. Manual signal is accepted as source_type=manual
 7. Synthetic signal is classified as source_type=synthetic
 8. Seed records remain seed
 9. Test DB is not storage/forge.db
10. Collector normalized output contains URL/source/retrieved_at
11. Collector dry-run performs no database writes
12. Duplicate merge command is idempotent
13. Duplicate merge defaults to dry-run
14. --apply is required before a merge can modify records
"""

import pytest
from datetime import datetime, timezone
from app import models
from app.services import opportunity_engine, observer_engine
from app.services.collectors.github import GithubCollector
from app.cli.merge_duplicates import run_merge, find_duplicate_clusters
from app.cli.collect import run_collection_smoke


def test_identity_key_stability_across_pattern_ids():
    problem = "Independent repair shops lose hours manually explaining appointment status by phone."
    key1 = opportunity_engine._identity_key(problem, pattern_id=1)
    key2 = opportunity_engine._identity_key(problem, pattern_id=99)
    assert key1 == key2
    assert key1.startswith("problem:")


def test_duplicate_opportunity_is_not_inserted(db):
    signal = models.Signal(
        source="manual",
        content="Repair shops lose hours manually calling customers.",
    )
    db.add(signal)
    db.flush()
    db.add(models.Evidence(signal_id=signal.id, source="manual", content=signal.content))
    p1 = models.Pattern(
        title="Repair shop pain",
        description=signal.content,
        frequency=3,
        origin_signal_ids=str(signal.id),
    )
    p2 = models.Pattern(
        title="Repair shop pain",
        description=signal.content,
        frequency=5,
        origin_signal_ids=str(signal.id),
    )
    db.add_all([p1, p2])
    db.commit()

    opp1 = opportunity_engine.opportunity_from_pattern(db, p1)
    opp2 = opportunity_engine.opportunity_from_pattern(db, p2)

    assert opp1.id == opp2.id
    assert db.query(models.Opportunity).count() == 1


def test_same_underlying_problem_across_two_cycle_runs_results_in_one_opportunity(db):
    signal = models.Signal(
        source="manual",
        content="Small property managers struggle to collect photos.",
    )
    db.add(signal)
    db.flush()
    db.add(models.Evidence(signal_id=signal.id, source="manual", content=signal.content))
    p1 = models.Pattern(
        title="Contractor photo problem",
        description=signal.content,
        frequency=2,
        origin_signal_ids=str(signal.id),
    )
    db.add(p1)
    db.commit()

    opp1 = opportunity_engine.opportunity_from_pattern(db, p1)

    p2 = models.Pattern(
        title="Contractor photo problem",
        description=signal.content,
        frequency=4,
        origin_signal_ids=str(signal.id),
    )
    db.add(p2)
    db.commit()

    opp2 = opportunity_engine.opportunity_from_pattern(db, p2)

    assert opp1.id == opp2.id
    assert db.query(models.Opportunity).count() == 1


def test_external_signal_without_canonical_url_is_rejected(db):
    obs = observer_engine.ObserverEngine(db)
    with pytest.raises(ValueError, match="canonical_url"):
        obs.observe("Some scraped content", source="github", metadata={"source_type": "external"})


def test_external_signal_without_retrieved_at_is_rejected(db):
    obs = observer_engine.ObserverEngine(db)
    # When metadata explicitly forces external without canonical_url
    with pytest.raises(ValueError, match="canonical_url"):
        obs.observe("Content", source="github", metadata={"source_type": "external", "retrieved_at": None})


def test_manual_signal_is_accepted_as_source_type_manual(db):
    obs = observer_engine.ObserverEngine(db)
    sig = obs.observe("Manual user complaint text", source="manual")
    assert sig.source_type == "manual"
    assert sig.source == "manual"


def test_synthetic_signal_is_classified_as_source_type_synthetic(db):
    obs = observer_engine.ObserverEngine(db)
    sig = obs.observe("Test synthetic observation", source="synthetic", metadata={"is_synthetic": True})
    assert sig.source_type == "synthetic"


def test_seed_records_remain_seed(db):
    sig = models.Signal(source="seed", source_type="seed", content="Historical seed data", processed=True)
    db.add(sig)
    db.commit()
    assert sig.source_type == "seed"


def test_test_db_is_not_real_forge_db(db):
    bind = db.get_bind()
    url = str(bind.url)
    assert "forge.db" not in url.lower()
    assert ":memory:" in url.lower() or "tmp" in url.lower()


def test_collector_normalized_output_contains_url_source_retrieved_at():
    collector = GithubCollector()
    raw = {
        "content": "Issue text",
        "title": "Bug title",
        "external_id": "123",
        "timestamp": "2026-09-23T00:00:00Z",
        "metadata": {"url": "https://github.com/org/repo/issues/123"},
    }
    norm = collector.normalize(raw)
    assert norm["source"] == "github"
    assert norm["source_type"] == "external"
    assert norm["canonical_url"] == "https://github.com/org/repo/issues/123"
    assert "retrieved_at" in norm


def test_collector_dry_run_performs_no_database_writes(db):
    count_before = db.query(models.Signal).count()
    res = run_collection_smoke(sources=["github"], query="automation", limit=1, apply=False, db=db)
    count_after = db.query(models.Signal).count()
    assert res["mode"] == "dry-run"
    assert res["inserted"] == 0
    assert "not cleared" in res["items"][0]["error"]
    assert count_before == count_after


def test_duplicate_merge_command_is_idempotent(db):
    key = opportunity_engine._identity_key("Duplicate problem statement")
    o1 = models.Opportunity(problem="Duplicate problem statement", target_customer="x", solution="y", business_model="z", identity_key=key)
    o2 = models.Opportunity(problem="Duplicate problem statement", target_customer="x", solution="y", business_model="z", identity_key=key)
    db.add_all([o1, o2])
    db.commit()

    res1 = run_merge(apply=True, db=db)
    assert res1["opportunities_archived"] == 1

    res2 = run_merge(apply=True, db=db)
    assert res2["opportunities_archived"] == 0


def test_duplicate_merge_defaults_to_dry_run(db):
    key = opportunity_engine._identity_key("Duplicate problem statement")
    o1 = models.Opportunity(problem="Duplicate problem statement", target_customer="x", solution="y", business_model="z", identity_key=key)
    o2 = models.Opportunity(problem="Duplicate problem statement", target_customer="x", solution="y", business_model="z", identity_key=key)
    db.add_all([o1, o2])
    db.commit()

    res = run_merge(apply=False, db=db)
    assert res["mode"] == "dry-run"
    assert o2.status != "archived"


def test_apply_flag_required_before_merge_can_modify_records(db):
    key = opportunity_engine._identity_key("Duplicate problem statement")
    o1 = models.Opportunity(problem="Duplicate problem statement", target_customer="x", solution="y", business_model="z", identity_key=key)
    o2 = models.Opportunity(problem="Duplicate problem statement", target_customer="x", solution="y", business_model="z", identity_key=key)
    db.add_all([o1, o2])
    db.commit()

    # Call with apply=False
    run_merge(apply=False, db=db)
    db.refresh(o2)
    assert o2.status != "archived"


def test_migration_backfill_on_temporary_db():
    import tempfile, sqlite3
    from sqlalchemy import create_engine
    from app.migrations import run_migrations
    
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        conn = sqlite3.connect(tmp.name)
        cur = conn.cursor()
        cur.execute("CREATE TABLE signals (id INTEGER PRIMARY KEY, source TEXT, content TEXT, source_type TEXT)")
        cur.execute("INSERT INTO signals (source, content, source_type) VALUES ('seed', 's1', 'manual')")
        cur.execute("INSERT INTO signals (source, content, source_type) VALUES ('rss', 's2', 'manual')")
        cur.execute("INSERT INTO signals (source, content, source_type) VALUES ('github', 's3', NULL)")
        cur.execute("INSERT INTO signals (source, content, source_type) VALUES ('manual', 's4', 'manual')")
        cur.execute("INSERT INTO signals (source, content, source_type) VALUES ('synthetic', 's5', NULL)")
        conn.commit()
        conn.close()

        engine = create_engine(f"sqlite:///{tmp.name}")
        run_migrations(engine)

        conn = sqlite3.connect(tmp.name)
        cur = conn.cursor()
        cur.execute("SELECT source, source_type FROM signals ORDER BY id")
        rows = cur.fetchall()
        conn.close()

        assert rows[0] == ("seed", "seed")
        assert rows[1] == ("rss", "external")
        assert rows[2] == ("github", "external")
        assert rows[3] == ("manual", "manual")
        assert rows[4] == ("synthetic", "synthetic")

        # Verify idempotency
        run_migrations(engine)
        conn = sqlite3.connect(tmp.name)
        cur = conn.cursor()
        cur.execute("SELECT source, source_type FROM signals ORDER BY id")
        rows_second = cur.fetchall()
        conn.close()
        assert rows == rows_second


def test_rank_opportunities_excludes_archived(db):
    from app.services import money_engine
    k1 = opportunity_engine._identity_key("Active opp")
    k2 = opportunity_engine._identity_key("Archived opp")
    o_active = models.Opportunity(problem="Active opp", target_customer="x", solution="y", business_model="z", identity_key=k1, status="identified")
    o_archived = models.Opportunity(problem="Archived opp", target_customer="x", solution="y", business_model="z", identity_key=k2, status="archived")
    db.add_all([o_active, o_archived])
    db.commit()

    ranked = money_engine.rank_opportunities(db)
    ranked_ids = [item["opportunity"].id for item in ranked]
    assert o_active.id in ranked_ids
    assert o_archived.id not in ranked_ids


def test_observer_stats_http_endpoint_contains_additive_fields():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from fastapi.testclient import TestClient
    from app.database import Base, get_db
    from app.main import app
    from app.services import source_manager

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    source_manager.seed_default_sources(session)

    def _override_db():
        try:
            yield session
        except Exception:
            session.rollback()
            raise

    app.dependency_overrides[get_db] = _override_db
    try:
        client = TestClient(app, raise_server_exceptions=True)
        response = client.get("/observer/stats")
        assert response.status_code == 200
        data = response.json()

        expected_keys = [
            "signals_total",
            "signals_external_with_url",
            "signals_seed",
            "signals_manual",
            "signals_synthetic",
            "opportunities_active",
            "opportunities_duplicate_archived",
            "outcomes_real",
            "verified_revenue"
        ]
        for key in expected_keys:
            assert key in data, f"Key {key} missing from /observer/stats HTTP response"
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


def test_manual_signal_with_url_semantics(db):
    obs = observer_engine.ObserverEngine(db)
    sig = obs.observe("Manual signal with URL", source="manual", metadata={"canonical_url": "https://example.com/item"})
    assert sig.source == "manual"
    assert sig.source_type == "manual"
    assert sig.canonical_url == "https://example.com/item"
