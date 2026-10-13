from app import models
from app.services import collector_runner, research_task_engine
from app.database import get_db
from app.main import app
from app.migrations import run_migrations
from fastapi.testclient import TestClient
from sqlalchemy import inspect


class FakeCollector:
    source_name = "fake"
    source_type = "test"
    calls = 0
    fail_next = False
    items = [{
        "content": "Contractors lose hours manually scheduling repairs.",
        "metadata": {
            "url": "https://example.test/repair/1",
            "external_id": "repair-1",
            "title": "Repair scheduling pain",
        },
    }]

    def collect(self, query=None):
        type(self).calls += 1
        if type(self).fail_next:
            type(self).fail_next = False
            raise RuntimeError("temporary source failure")
        return list(type(self).items)

    def normalize(self, raw_item):
        return {
            "source": self.source_name,
            "content": raw_item["content"],
            "canonical_url": raw_item["metadata"]["url"],
            "external_id": raw_item["metadata"]["external_id"],
            "title": raw_item["metadata"]["title"],
            "metadata": raw_item["metadata"],
        }


def make_task(db):
    question = models.ResearchQuestion(question="Do contractors pay for repair scheduling tools?")
    db.add(question)
    db.commit()
    db.refresh(question)
    return research_task_engine.create_task(
        db,
        question_id=question.id,
        source="fake",
        query=question.question,
        objective=question.question,
    )


def test_running_task_is_planned_again_before_collection(db):
    from datetime import timedelta

    task = make_task(db)
    task.status = "running"
    task.updated_at = research_task_engine.utcnow() - timedelta(minutes=10)
    db.commit()
    resumed = research_task_engine.resume_running_tasks(db, limit=10)
    assert resumed == [task.id]
    assert db.get(models.ResearchTask, task.id).status == "planned"
    assert research_task_engine.resume_running_tasks(db, limit=10) == []


def test_create_persist_and_resume_research_task(db):
    task = make_task(db)
    task_id = task.id
    db.expunge_all()
    restored = db.get(models.ResearchTask, task_id)

    assert restored.objective == "Do contractors pay for repair scheduling tools?"
    assert restored.status == "planned"
    assert [step.name for step in restored.steps] == ["plan", "select_tools", "execute", "evaluate"]

    resumed = research_task_engine.resume_task(db, restored)
    assert resumed.id == task_id
    assert db.query(models.ResearchTaskEvent).filter_by(task_id=task_id, event_type="created").count() == 1


def test_research_task_identity_is_reused_and_backfilled(db):
    task = make_task(db)
    identity = task.idempotency_key

    repeated = research_task_engine.create_task(
        db,
        question_id=task.question_id,
        source=task.source,
        query=task.query,
    )
    assert repeated.id == task.id
    assert repeated.idempotency_key == identity

    task.idempotency_key = None
    db.commit()
    backfilled = research_task_engine.create_task(
        db,
        question_id=task.question_id,
        source=task.source,
        query=task.query,
    )
    assert backfilled.id == task.id
    assert backfilled.idempotency_key == identity


def test_research_task_idempotency_key_is_unique_in_migrated_database(db):
    run_migrations(db.get_bind())

    indexes = inspect(db.get_bind()).get_indexes("research_tasks")

    assert any(
        index["name"] == "uq_research_tasks_idempotency_key"
        and index["unique"]
        and index["column_names"] == ["idempotency_key"]
        for index in indexes
    )


def test_failed_step_can_retry_and_complete(db, monkeypatch):
    task = make_task(db)
    FakeCollector.fail_next = True
    monkeypatch.setitem(collector_runner.COLLECTORS, "fake", FakeCollector)

    failed = collector_runner.execute_task(db, task)
    assert failed["status"] == "failed"
    assert db.get(models.ResearchTask, task.id).errors

    research_task_engine.retry_task(db, db.get(models.ResearchTask, task.id))
    completed = collector_runner.execute_task(db, db.get(models.ResearchTask, task.id))

    assert completed["status"] == "completed"
    assert db.query(models.ResearchTaskEvent).filter_by(task_id=task.id, event_type="retry_queued").count() == 1
    assert db.get(models.ResearchTask, task.id).attempts == 2


def test_duplicate_evidence_is_reused_without_duplicate_work(db, monkeypatch):
    task = make_task(db)
    monkeypatch.setitem(collector_runner.COLLECTORS, "fake", FakeCollector)

    first = collector_runner.execute_task(db, task)
    second = collector_runner.execute_task(db, db.get(models.ResearchTask, task.id))

    assert first["status"] == "completed"
    assert second["reused"] is True
    assert db.query(models.Signal).count() == 1
    assert db.query(models.Evidence).count() == 1
    assert db.query(models.ResearchTaskEvent).filter_by(task_id=task.id, event_type="completed").count() == 1

    persisted = db.get(models.ResearchTask, task.id)
    steps = {step.name: step for step in persisted.steps}
    assert persisted.results["completion_scope"] == "source_collection_only"
    assert "offline-mock" not in (persisted.tools_used or [])
    assert steps["select_tools"].output_data["reasoning_status"] == "not_invoked"
    assert steps["evaluate"].status == "pending"
    assert steps["evaluate"].output_data["status"] == "not_evaluated"


def test_insufficient_evidence_remains_resumable(db, monkeypatch):
    class EmptyCollector(FakeCollector):
        source_name = "empty"

        def collect(self, query=None):
            return []

    task = make_task(db)
    task.source = "empty"
    db.commit()
    monkeypatch.setitem(collector_runner.COLLECTORS, "empty", EmptyCollector)

    result = collector_runner.execute_task(db, task)
    persisted = db.get(models.ResearchTask, task.id)

    assert result["status"] == "needs_research"
    assert persisted.remaining_questions == [persisted.objective]
    assert persisted.completed_at is None
    assert db.query(models.ResearchTaskEvent).filter_by(task_id=task.id, event_type="remaining_question").count() == 1


def test_rate_limited_research_is_deferred_without_consuming_attempt(db, monkeypatch):
    task = make_task(db)
    task.source = "crossref"
    db.commit()

    def rate_limited(*args, **kwargs):
        from app.services.source_clearance_registry import SourceRateLimitError

        raise SourceRateLimitError("Source rate limit is active")

    monkeypatch.setattr(
        collector_runner.source_clearance_registry,
        "authorize_request",
        rate_limited,
    )

    result = collector_runner.execute_task(db, task)

    assert result["status"] == "planned"
    assert result["deferred"] is True
    assert db.get(models.ResearchTask, task.id).attempts == 0
    assert db.query(models.ResearchTaskEvent).filter_by(task_id=task.id, event_type="deferred").count() == 1


def test_task_survives_sqlite_restart(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base

    database_url = f"sqlite:///{tmp_path / 'research.db'}"
    first_engine = create_engine(database_url)
    Base.metadata.create_all(first_engine)
    first_session = sessionmaker(bind=first_engine)()
    question = models.ResearchQuestion(question="What evidence exists for a durable research task?")
    first_session.add(question)
    first_session.commit()
    first_session.refresh(question)
    task = research_task_engine.create_task(
        first_session,
        question_id=question.id,
        source="fake",
        query=question.question,
    )
    task_id = task.id
    first_session.close()
    first_engine.dispose()

    second_engine = create_engine(database_url)
    restored = sessionmaker(bind=second_engine)().get(models.ResearchTask, task_id)

    assert restored is not None
    assert restored.objective == "What evidence exists for a durable research task?"


def test_tasks_endpoint_exposes_failed_and_planned_status(db, monkeypatch):
    from app import security

    monkeypatch.setattr(security.settings, "FORGE_API_KEY", "research-task-test-key")
    planned = make_task(db)
    second_question = models.ResearchQuestion(question="Does a second task expose its failed status?")
    db.add(second_question)
    db.commit()
    failed = research_task_engine.create_task(
        db,
        question_id=second_question.id,
        source="fake",
        query=second_question.question,
    )
    failed.status = "failed"
    db.commit()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get(
            "/forge/tasks",
            headers={"X-API-Key": "research-task-test-key"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    statuses = {item["status"] for item in response.json() if item["id"] in {planned.id, failed.id}}
    assert statuses == {"planned", "failed"}


def test_pending_task_dispatch_covers_questions_before_repeating(db, monkeypatch):
    from types import SimpleNamespace
    from app import models
    from app.services import collector_runner, research_task_engine

    questions = [
        models.ResearchQuestion(question="Track alpha question", priority_score=90),
        models.ResearchQuestion(question="Track beta question", priority_score=80),
        models.ResearchQuestion(question="Track gamma question", priority_score=70),
        models.ResearchQuestion(question="Track delta question has no cleared source", priority_score=100),
    ]
    db.add_all(questions)
    db.commit()
    for q in questions:
        db.refresh(q)
    tasks = [
        research_task_engine.create_task(db, question_id=questions[0].id, source="crossref", query="alpha one"),
        research_task_engine.create_task(db, question_id=questions[0].id, source="crossref", query="alpha two"),
        research_task_engine.create_task(db, question_id=questions[1].id, source="crossref", query="beta"),
        research_task_engine.create_task(db, question_id=questions[2].id, source="crossref", query="gamma"),
        research_task_engine.create_task(db, question_id=questions[3].id, source="openalex", query="delta without source clearance"),
    ]
    monkeypatch.setattr(collector_runner.source_clearance_registry, "source_clearances",
        lambda: [SimpleNamespace(collector="crossref", url="https://api.crossref.org/works")])
    monkeypatch.setattr(collector_runner.source_clearance_registry, "collector_is_cleared", lambda _name: True)
    ids = []
    def execute(_db, task):
        ids.append(task.id)
        task.status = "completed"
        _db.commit()
        return {"task_id": task.id, "status": "completed"}
    monkeypatch.setattr(collector_runner, "execute_task", execute)
    outcomes = collector_runner.run_pending_tasks(db, limit=4)

    assert ids == [tasks[0].id, tasks[2].id, tasks[3].id, tasks[1].id]
    assert [row["portfolio_dispatch"]["pass"] for row in outcomes] == [
        "question_coverage", "question_coverage", "question_coverage", "throughput"
    ]
    # The highest-priority but uncleared track did not consume a coverage slot.
    assert db.get(models.ResearchTask, tasks[4].id).status == "planned"
