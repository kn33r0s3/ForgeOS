"""Regression proof that a failed Forge stage cannot poison autonomy."""
from types import SimpleNamespace

from app import models
from app.services import collector_runner, research_task_engine, public_feed
from app.services.collectors.base import SourceCollector
from scripts import run_daily_cycle


class FakeSession:
    def __init__(self):
        self.poisoned = False
        self.rollbacks = 0
        self.closed = False

    def rollback(self):
        self.poisoned = False
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_forge_failure_is_rolled_back_before_autonomy(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(run_daily_cycle, "SessionLocal", lambda: session)

    def fail_forge(db):
        db.poisoned = True
        raise RuntimeError("interrupted between stages")

    def autonomy(db):
        assert db.poisoned is False
        return SimpleNamespace(proposed=1, allowed=0, blocked=0, require_approval=1)

    monkeypatch.setattr(run_daily_cycle.forge_loop, "run_cycle", fail_forge)
    monkeypatch.setattr(run_daily_cycle.execution_engine, "run_autonomous_action_cycle", autonomy)

    record = run_daily_cycle.run_once()
    assert record["forge_cycle_recovered"] is True
    assert record["forge_cycle_error"].startswith("RuntimeError:")
    assert record["autonomy_cycle"]["proposed"] == 1
    assert session.rollbacks == 1
    assert session.closed is True


def test_rollback_failure_is_best_effort_and_does_not_escape():
    class BrokenSession:
        def rollback(self):
            raise RuntimeError("rollback itself failed")
        def expunge_all(self):
            raise RuntimeError("expunge failed")

    run_daily_cycle._rollback_if_needed(BrokenSession(), "test")


def test_cycle_scans_open_needs_when_collection_is_disabled(db, monkeypatch):
    row = models.DomainRecord(
        kind="job",
        title="Cycle scan need",
        detail="No provider is recorded for this need.",
        status="open",
        close_token_hash="test",
    )
    db.add(row)
    db.commit()

    monkeypatch.setattr(run_daily_cycle, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        run_daily_cycle.execution_engine,
        "run_autonomous_action_cycle",
        lambda session: {"proposed": 0, "allowed": 0, "blocked": 0, "require_approval": 0},
    )
    monkeypatch.setenv("FORGEOS_COLLECT_LIMIT", "0")

    record = run_daily_cycle.run_once()

    assert record.get("collection") is None
    gap = db.query(models.ResearchQuestion).filter(
        models.ResearchQuestion.question.like("Gap: open job #%")
    ).one()
    assert gap.status == "open"
    assert db.query(models.Opportunity).count() == 0


def test_daily_cycle_runs_one_internal_pass_after_real_collection_results(db, monkeypatch):
    calls = []

    def cycle(_session):
        calls.append(len(calls) + 1)
        return {
            "claims_linked": [len(calls)],
            "network_connection_ids": [],
            "source_addresses_restored": 0,
        }

    monkeypatch.setattr(run_daily_cycle, "SessionLocal", lambda: db)
    monkeypatch.setattr(run_daily_cycle.forge_loop, "run_cycle", cycle)
    monkeypatch.setattr(
        "app.services.collector_runner.run_pending_tasks",
        lambda session, limit: [{"status": "completed", "signals_created": 1}],
    )
    monkeypatch.setattr(
        run_daily_cycle.execution_engine,
        "run_autonomous_action_cycle",
        lambda session: SimpleNamespace(proposed=0, allowed=0, blocked=0, require_approval=0),
    )
    monkeypatch.setenv("FORGEOS_COLLECT_LIMIT", "1")

    record = run_daily_cycle.run_once()

    assert calls == [1, 2]
    assert record["post_collection_cycle"]["claims_linked"] == [2]
    assert record["linked_claims"] == [1, 2]


def test_daily_cycle_collects_no_more_than_existing_batch_limit(db, monkeypatch):
    questions = [
        models.ResearchQuestion(question=f"Bounded cycle research question {index}")
        for index in range(3)
    ]
    db.add_all(questions)
    db.flush()
    tasks = [
        models.ResearchTask(
            question_id=question.id,
            source="pytest-source",
            query=question.question,
            objective=question.question,
            status="planned",
        )
        for question in questions
    ]
    db.add_all(tasks)
    db.commit()
    executed = []

    def execute(_db, task):
        executed.append(task.id)
        return {"task_id": task.id, "status": "completed", "signals_created": 0}

    monkeypatch.setattr(run_daily_cycle, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        run_daily_cycle.forge_loop,
        "run_cycle",
        lambda _db: {"claims_linked": [], "network_connection_ids": [], "source_addresses_restored": 0},
    )
    monkeypatch.setattr(collector_runner, "execute_task", execute)
    monkeypatch.setattr(
        run_daily_cycle.execution_engine,
        "run_autonomous_action_cycle",
        lambda _db: {"proposed": 0, "allowed": 0, "blocked": 0, "require_approval": 0},
    )
    monkeypatch.setenv("FORGEOS_COLLECT_LIMIT", "2")

    record = run_daily_cycle.run_once()

    assert len(record["collection"]) == 2
    assert len(executed) == 2
    assert len({task_id for task_id in executed}) == 2


def test_daily_cycle_structures_collected_external_signals_in_same_run(db, monkeypatch):
    texts = [
        "At least 12 restaurants in Kathmandu still take phone orders and write them on paper tickets. Managers report 3-5 wrong dishes per busy night, losing roughly NPR 8000-15000 each weekend.",
        "Restaurant managers in Kathmandu report that paper kitchen tickets get lost every Friday night. One owner counted 7 lost tickets last week, leading to angry customers who refused to pay for 4 orders.",
        "Three cafe owners near Thamel still use handwritten order pads. Staff make mistakes on 15 percent of orders according to their own count. Customers complain about wrong dishes at least twice per week.",
        "A restaurant owner in Lazimpat said they lose about NPR 12000 every weekend because phone orders are miswritten and kitchen tickets are illegible. They tried hiring more staff but the paper process remains the bottleneck.",
        "Small restaurants need a simple digital order system. Manual phone-to-paper process creates constant operational friction: 5 restaurants interviewed last month all reported the same problem of lost tickets and misheard phone orders.",
    ]

    class PytestSourceCollector(SourceCollector):
        source_name = "pytest-network-source"
        source_type = "test"

        def collect(self, query=None):
            return [
                {
                    "content": text,
                    "metadata": {
                        "url": f"https://evidence.example.test/daily/{index}",
                        "external_id": f"fixture-{index}",
                    },
                }
                for index, text in enumerate(texts, start=1)
            ]

    question = models.ResearchQuestion(question="Pytest fixture source task")
    db.add(question)
    db.commit()
    db.refresh(question)
    research_task_engine.create_task(
        db,
        question_id=question.id,
        source="pytest-network-source",
        query=question.question,
    )
    monkeypatch.setitem(collector_runner.COLLECTORS, "pytest-network-source", PytestSourceCollector)
    monkeypatch.setattr(run_daily_cycle, "SessionLocal", lambda: db)
    monkeypatch.setattr(
        run_daily_cycle.execution_engine,
        "run_autonomous_action_cycle",
        lambda session: {"proposed": 0, "allowed": 0, "blocked": 0, "require_approval": 0},
    )
    monkeypatch.setenv("FORGEOS_COLLECT_LIMIT", "1")

    record = run_daily_cycle.run_once()

    assert "collection" in record, record
    assert record["collection"][0]["signals_created"] == len(texts)
    assert record["post_collection_cycle"]["patterns_found"] >= 1
    assert record["post_collection_cycle"]["beliefs_updated"] >= 1
    assert record["post_collection_cycle"]["opportunities_discovered"] >= 1
    assert record["post_collection_cycle"]["opportunity_questions_linked"] >= 1
    projected = public_feed.build_public_feed(db)
    opportunity_items = [item for item in projected if item.kind == "opportunity"]
    assert opportunity_items
    claim_ids = {
        relation.entity_id
        for item in opportunity_items
        for relation in item.relations
        if relation.entity_type == "claim"
    }
    assert claim_ids
    assert db.query(models.ResearchQuestion).filter(
        models.ResearchQuestion.source_claim_id.in_(claim_ids)
    ).count() >= 1
    assert all("evidence.example.test" in (item.source_url or "") for item in projected if item.kind == "signal")
