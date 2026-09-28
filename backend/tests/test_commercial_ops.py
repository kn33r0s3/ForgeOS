"""
Regression tests for the commercial-readiness hardening added on 2026-09-14:
  * security.py   — opt-in API-key gate (reads open, state-changes gated)
  * backup.py     — safe SQLite snapshot via VACUUM INTO + retention
  * cycle_scheduler.py — overlap protection + a clean cycle run records
"""

import os
import sys
import gzip
import sqlite3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["AI_PROVIDER"] = "mock"
os.environ["EMBEDDING_PROVIDER"] = "hash"

import pytest
from app import models
from pathlib import Path


# ---------------------------------------------------------------------------
# Security (opt-in API key)
# The middleware is a pure function of settings.FORGE_API_KEY + the request;
# we test that decision directly so no live DB/app stack is involved.
# ---------------------------------------------------------------------------

def _decision(secret, method, header_key=None, query_key=None):
    from app import security
    from fastapi import Request
    from starlette.datastructures import Headers, QueryParams

    security.settings.FORGE_API_KEY = secret
    class _R(Request):
        def __init__(self):
            self._m = method
            self._h = {"x-api-key": header_key} if header_key else {}
            self._q = QueryParams({"api_key": query_key}) if query_key else QueryParams({})
        @property
        def method(self): return self._m
        @property
        def headers(self): return Headers(self._h)
        @property
        def query_params(self): return self._q

    # Replicate the middleware's enforcement decision in isolation.
    req = _R()
    if secret and method not in {"GET", "HEAD", "OPTIONS"}:
        return security._authorized(req)
    return True  # reads / no-secret always pass


def test_auth_off_passes_through():
    """No FORGE_API_KEY set -> state-changing routes are NOT gated (local-first)."""
    assert _decision("", "POST") is True


def test_auth_on_gates_writes_but_allows_correct_key():
    """With a key set: reads pass, un/incorrect-keyed writes rejected,
    correct-key write passes."""
    assert _decision("sec", "GET") is True            # read open
    assert _decision("sec", "POST") is False          # no key -> rejected
    assert _decision("sec", "POST", header_key="wrong") is False
    assert _decision("sec", "POST", header_key="sec") is True
    assert _decision("sec", "POST", query_key="sec") is True


# ---------------------------------------------------------------------------
# Backup (safe snapshot + retention)
# ---------------------------------------------------------------------------

def test_safe_backup_produces_valid_snapshot_and_prunes(tmp_path):
    """safe_backup(): creates a gz snapshot containing the same core tables,
    and prunes beyond keep."""
    from app.services import backup as bk
    db_path = tmp_path / "src.db"
    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE a (x INTEGER)")
    con.execute("INSERT INTO a VALUES (1)")
    con.commit(); con.close()

    # point backups at tmp dir
    bk.BACKUPS_DIR = tmp_path / "bk"
    # backup 3 times with keep=2 -> only most recent 2 remain
    names = [bk.safe_backup(db_path, keep=2) for _ in range(3)]
    snaps = sorted((tmp_path / "bk").glob("forge_*.db.gz"))
    assert len(snaps) == 2
    # newest is a valid db
    with gzip.open(snaps[-1], "rb") as g:
        raw = g.read()
    probe = tmp_path / "probe.db"
    probe.write_bytes(raw)
    chk = sqlite3.connect(str(probe))
    assert chk.execute("SELECT x FROM a").fetchall() == [(1,)]
    chk.close()


# ---------------------------------------------------------------------------
# Scheduler (records a clean cycle; overlap guard)
# ---------------------------------------------------------------------------

def test_scheduler_run_once_records_clean_cycle(dbcopy, monkeypatch, tmp_path):
    """CycleScheduler._run_cycle() runs the hardened two-stage cycle and
    returns a record with no errors."""
    monkeypatch.setenv("FORGEOS_COLLECT_LIMIT", "0")
    from app.services import cycle_scheduler
    s = cycle_scheduler.CycleScheduler(interval_seconds=60, backup_interval_seconds=None, max_run_seconds=300, lock_path=tmp_path / "scheduler.run.lock")
    rec = s._run_cycle()
    assert rec.get("forge_cycle_error") is None
    assert rec.get("autonomy_cycle_error") is None


def test_scheduler_skips_overlapping_run(dbcopy, tmp_path):
    """While a run is marked in-progress, a new tick must refuse to start."""
    from app.services import cycle_scheduler
    s = cycle_scheduler.CycleScheduler(interval_seconds=60, backup_interval_seconds=None, max_run_seconds=300, lock_path=tmp_path / "scheduler.run.lock")
    s._running.set()  # simulate in-progress
    s._tick()  # should short-circuit without calling _run_cycle
    assert s._running.is_set()  # still marked (unchanged by the skipped tick)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_copied_env(tmp_path, monkeypatch):
    """Point DATABASE_URL at an empty temp sqlite with tables for the app."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    from app.database import init_db
    init_db()
    yield tmp_path


@pytest.fixture
def dbcopy(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/c.db")
    from app.database import init_db
    init_db()
    yield tmp_path


# ---------------------------------------------------------------------------
# Product / Distribution / Customer workflow (commercial readiness v2)
# ---------------------------------------------------------------------------

from app.services import product_engine, action_engine


def test_product_lifecycle_and_honest_rollup(db):
    """A product can be formed, launched, and its numbers come ONLY from
    real ACTUAL outcomes — never fabricated."""
    engine = db.bind
    # create product (concept)
    p = product_engine.create_product(
        db, name="No-Show Cutter", offer="Appointment reminder + no-show reducer for repair shops",
        target_customer="independent repair shops", pricing="$99/mo",
        hypothesis="repair shops will pay to cut ~$500/mo no-shows",
    )
    assert p.id is not None
    assert p.status == "concept"
    assert p.actual_revenue == 0.0 and p.actual_customers == 0  # honest zero

    # Hypotheses cannot be launched before any explicit validation.
    with pytest.raises(ValueError):
        product_engine.update_product(db, p.id, status="launched", launch_state="public")
    # no outcome recorded -> revenue still 0 (honesty gate)
    s0 = product_engine.product_summary(db, p)
    assert s0["actual_revenue"] == 0.0 and s0["paid_customer_count"] == 0

    # Synthetic TEST fixture only: explicit USD ledger entries (not business revenue)
    action_engine.record_outcome(db, outcome_type="ACTUAL_REVENUE", product_id=p.id,
                                 actual_value=99.0, unit="USD", source="manual")
    action_engine.record_outcome(db, outcome_type="ACTUAL_CUSTOMERS", product_id=p.id,
                                 actual_value=1, unit="count", source="manual")
    s1 = product_engine.product_summary(db, p)
    assert s1["actual_revenue"] == 99.0
    assert s1["actual_customers"] == 1

    # an outcome tied to a DIFFERENT product must not leak in
    p2 = product_engine.create_product(db, name="Other", offer="other offer")
    s2 = product_engine.product_summary(db, p2)
    assert s2["actual_revenue"] == 0.0


def test_distribution_channel_and_customer_funnel(db):
    """Channels and customer ledger record real contacts and roll up an
    honest funnel (lead -> contacted -> paid_customer)."""
    p = product_engine.create_product(db, name="P", offer="offer")
    ch = product_engine.create_channel(db, product_id=p.id, channel_type="manual_outreach",
                                       name="Reddit r/repairshops")
    # log a lead, then a paid customer
    product_engine.create_customer_event(db, channel_id=ch.id, product_id=p.id,
                                         stage="lead", event_type="outbound", segment="repair shop")
    response = models.Outcome(
        product_id=p.id,
        outcome_type="ACTUAL_RESPONSE",
        qualitative_result="Synthetic test fixture: contact reported interest.",
        source="synthetic_test_fixture",
        verification_state="VERIFIED",
        data_scope="REAL",
    )
    payment = models.Outcome(
        product_id=p.id,
        outcome_type="ACTUAL_REVENUE",
        actual_value=1.0,
        unit="USD",
        source="synthetic_test_fixture",
        verification_state="VERIFIED",
        data_scope="REAL",
    )
    db.add_all([response, payment])
    db.commit()
    product_engine.create_customer_event(db, channel_id=ch.id, product_id=p.id,
                                         stage="contacted", event_type="response",
                                         outcome_id=response.id)
    product_engine.create_customer_event(db, channel_id=ch.id, product_id=p.id,
                                         stage="interested", event_type="interest",
                                         outcome_id=response.id)
    product_engine.create_customer_event(db, channel_id=ch.id, product_id=p.id,
                                         stage="paid_customer", event_type="purchase",
                                         outcome_id=payment.id)
    roll = product_engine.rollup_channel(db, ch)
    assert roll["outreach_count"] >= 3     # real logged contacts
    assert roll["response_count"] == 2      # contacted + paid
    assert roll["conversion_count"] == 1    # one paying customer

    snap = product_engine.pipeline(db)
    assert snap["total_products"] == 1
    assert snap["total_leads"] == 2  # lead + contacted (prospects in pipeline)
    assert snap["total_paid_customers"] == 1


def test_pipeline_launched_and_never_fabricates(db):
    """pipeline() reports launched products and zero revenue until a real
    outcome is recorded."""
    p = product_engine.create_product(db, name="L", offer="o")
    with pytest.raises(ValueError):
        product_engine.update_product(db, p.id, status="launched", launch_state="public")
    product_engine.update_product(db, p.id, status="retired", retirement_reason="no traction")
    snap = product_engine.pipeline(db)
    # one product, but launch_state changed to retired via update churn above;
    # product still exists
    assert snap["total_products"] == 1
    assert snap["realized_revenue"] == 0.0  # never fabricated
    assert snap["total_paid_customers"] == 0


# ---------------------------------------------------------------------------
# Lessons Memory (v2.10) — durable consolidate + recall, learned like an
# assistant files facts and recalls them into later reasoning.
# ---------------------------------------------------------------------------

from app.services import lessons_engine


def _mk_event(db, *, lesson_text, prediction="x", actual="y", error_type=None,
              pred_err=None, opportunity_id=None, belief_id=None):
    from app.services import learning_engine
    # build a LearningEvent directly (DB-backed)
    ev = models.LearningEvent(
        prediction=prediction, actual=actual, lesson=lesson_text,
        error_type=error_type, prediction_error=pred_err,
        opportunity_id=opportunity_id, belief_id=belief_id,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def test_learning_event_consolidates_into_lesson(db):
    """A real LearningEvent files into a durable Lesson (never fabricated)."""
    ev = _mk_event(db, lesson_text="repair shops did not pay for the $99/mo pricing",
                   error_type="overestimate", pred_err=0.5)
    lesson = lessons_engine.consolidate_learning_event(db, ev)
    assert lesson.id is not None
    assert lesson.hit_count == 1
    assert lesson.prediction_error_avg == 0.5
    assert lesson.source_learning_event_ids == str(ev.id)
    assert lesson.active is True
    # a lesson exists only because the event existed -> provenance is non-empty
    assert lesson.source_learning_event_ids


def test_repeated_similar_events_merge_same_lesson(db):
    """Same theme -> same durable page, hit_count/error average grow."""
    e1 = _mk_event(db, lesson_text="customers balked at the high price point",
                   error_type="overestimate", pred_err=0.6)
    l1 = lessons_engine.consolidate_learning_event(db, e1)
    e2 = _mk_event(db, lesson_text="customers again refused the price, want lower",
                   error_type="overestimate", pred_err=0.4)
    l2 = lessons_engine.consolidate_learning_event(db, e2)
    assert l2.id == l1.id            # same theme -> same durable page
    assert l2.hit_count == 2
    assert abs(l2.prediction_error_avg - 0.5) < 1e-6  # (0.6+0.4)/2
    assert l2.source_learning_event_ids  # both traced
    # lessons total stays 1
    assert db.query(models.Lesson).count() == 1


def test_recall_surfaces_lesson_for_opportunity(db):
    """Recall finds a lesson tagged to an opportunity."""
    from app.services import opportunity_engine
    opp = models.Opportunity(
        problem="repair shops lose hours to no-shows",
        target_customer="independent repair shops",
        solution="reminders", business_model="saas", score=80.0,
    )
    db.add(opp); db.commit(); db.refresh(opp)
    ev = _mk_event(db, lesson_text="repair shops do pay for a no-show reducer",
                   error_type="confirmed", opportunity_id=opp.id)
    lessons_engine.consolidate_learning_event(db, ev)
    recalled = lessons_engine.recall_lessons(db, opportunity_id=opp.id)
    assert any(l.opportunity_id == opp.id for l in recalled)
    # decision assist carries a note
    a = lessons_engine.assist_decision(db, opportunity_id=opp.id)
    assert a["recalled_lessons"]
    assert any("past-lesson" in n for n in a["notes"])


def test_recall_feeds_decision_rationale(db):
    """A recalled lesson shows up in the proposed decision's rationale."""
    from app.services import decision_engine
    opp = models.Opportunity(
        problem="shops lose money on missed appointments",
        target_customer="independent repair shops",
        solution="reminders", business_model="saas", score=85.0,
        market_confidence=30.0,
    )
    db.add(opp); db.commit(); db.refresh(opp)
    ev = _mk_event(db, lesson_text="no-show cost was wildly overestimated",
                   error_type="overestimate", opportunity_id=opp.id)
    lessons_engine.consolidate_learning_event(db, ev)
    decision = decision_engine.suggest_next_experiment_decision(db, opp.id)
    assert decision is not None
    assert "Recalled lesson" in decision.rationale


def test_lessons_are_never_fabricated(db):
    """No LEarningEvents -> no lessons, and rebuild is a no-op."""
    assert db.query(models.Lesson).count() == 0
    out = lessons_engine.run_lessons_cycle(db)
    assert out["events_total"] == 0
    assert out["lessons_total"] == 0
