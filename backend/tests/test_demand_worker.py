from app import models
from app.services import demand_understanding
from app.services.worker_manager import process_worker_tasks


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
