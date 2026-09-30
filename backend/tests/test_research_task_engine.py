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


def test_tasks_endpoint_exposes_failed_and_planned_status(db):
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
        response = TestClient(app).get("/forge/tasks")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    statuses = {item["status"] for item in response.json() if item["id"] in {planned.id, failed.id}}
    assert statuses == {"planned", "failed"}
