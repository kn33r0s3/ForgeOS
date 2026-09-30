from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base
from app.migrations import run_migrations
from app.services import demand_understanding
from app.services.worker_manager import process_worker_task_by_id, process_worker_tasks


def test_demand_understanding_worker_is_idempotent_and_bounded(db):
    observation = demand_understanding.record_raw_observation(
        db,
        "A buyer repeatedly seeks an item unavailable locally.",
        metadata={"identity_key": "worker-observation", "source_type": "synthetic"},
    )
    first = demand_understanding.enqueue_understanding(
        db,
        [observation.id],
        object_description="the unavailable item",
        desired_outcome="obtain the item locally",
    )
    second = demand_understanding.enqueue_understanding(
        db,
        [observation.id],
        object_description="the unavailable item",
        desired_outcome="obtain the item locally",
    )
    assert first.id == second.id
    assert db.query(models.WorkerTask).filter_by(worker_type="demand_understanding").count() == 1

    process_worker_tasks(db)
    db.refresh(first)
    assert first.status == "completed"
    assert first.outputs["state"] == "hypothesized"
    assert first.outputs["external_action"] is False
    assert process_worker_task_by_id(db, first.id) is False
    assert db.query(models.IntegrationDelivery).count() == 0


def test_demand_worker_can_derive_need_without_authorizing_action(db):
    observation = demand_understanding.record_raw_observation(
        db,
        "A business needs recurring access to ingredient X.",
        metadata={"identity_key": "worker-need", "source_type": "synthetic"},
    )
    task = demand_understanding.enqueue_understanding(
        db,
        [observation.id],
        object_description="ingredient X",
        desired_outcome="receive acceptable ingredient X weekly",
        unresolved_questions=[],
        sufficient=True,
    )
    process_worker_tasks(db)
    db.refresh(task)
    assert task.status == "completed"
    assert task.outputs["need_id"] is not None
    assert db.query(models.Action).count() == 0


def test_concurrent_workers_claim_a_demand_task_only_once(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'demand-worker-claim.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    run_migrations(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        observation = demand_understanding.record_raw_observation(
            session,
            "Synthetic fixture: one request for an unavailable item.",
            metadata={"identity_key": "single-claim-observation", "source_type": "synthetic"},
        )
        task = demand_understanding.enqueue_understanding(session, [observation.id])
        task_id = task.id

    def process():
        with factory() as session:
            return process_worker_task_by_id(
                session,
                task_id,
                worker_type="demand_understanding",
            )

    with ThreadPoolExecutor(max_workers=2) as workers:
        claimed = list(workers.map(lambda _: process(), range(2)))
    with factory() as reopened:
        task = reopened.get(models.WorkerTask, task_id)
        assert sum(claimed) == 1
        assert task.status == "completed"
        assert task.outputs["state"] == "possible_demand"
        assert reopened.query(models.WorldEvent).filter_by(
            event_type="demand_understood"
        ).count() == 0
        assert reopened.query(models.Evidence).filter_by(
            source="demand_understanding"
        ).count() == 1
    engine.dispose()


def test_concurrent_demand_enqueue_creates_one_deterministic_task(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'demand-worker.sqlite'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(engine)
    run_migrations(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        observation = demand_understanding.record_raw_observation(
            session,
            "Synthetic fixture: a request describes an unavailable item.",
            metadata={
                "identity_key": "concurrent-demand-observation",
                "source_type": "synthetic",
            },
        )
        observation_id = observation.id

    def enqueue():
        with factory() as session:
            return demand_understanding.enqueue_understanding(
                session,
                [observation_id],
                object_description="an unavailable item",
                desired_outcome="obtain the item",
            ).id

    with ThreadPoolExecutor(max_workers=3) as workers:
        task_ids = list(workers.map(lambda _: enqueue(), range(3)))
    with factory() as reopened:
        assert len(set(task_ids)) == 1
        assert reopened.query(models.WorkerTask).filter_by(
            worker_type="demand_understanding"
        ).count() == 1
    engine.dispose()
