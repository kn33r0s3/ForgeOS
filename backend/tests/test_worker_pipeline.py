import pytest
from sqlalchemy.orm import Session
from app import models
from app.services.worker_manager import process_worker_tasks

def test_worker_pipeline(db: Session):
    # Seed an initial discovery task
    task = models.WorkerTask(
        worker_type="discovery",
        task_name="initial_discovery",
        priority=1,
        inputs={}
    )
    db.add(task)
    db.commit()

    # Process tasks - should handle discovery and queue research
    process_worker_tasks(db)
    
    # After discovery, it should be marked complete
    discovery_task = db.query(models.WorkerTask).filter(models.WorkerTask.worker_type == "discovery").first()
    assert discovery_task.status == "completed"
    
    # Research task should be queued
    research_task = db.query(models.WorkerTask).filter(models.WorkerTask.worker_type == "research").first()
    assert research_task is not None
    assert research_task.status == "queued"
    
    # Process again - should handle research and queue opportunity
    process_worker_tasks(db)
    db.refresh(research_task)
    assert research_task.status == "completed"
    
    opportunity_task = db.query(models.WorkerTask).filter(models.WorkerTask.worker_type == "opportunity").first()
    assert opportunity_task is not None
    assert opportunity_task.status == "queued"

    # Process again - opportunity -> builder
    process_worker_tasks(db)
    db.refresh(opportunity_task)
    assert opportunity_task.status == "completed"

    builder_task = db.query(models.WorkerTask).filter(models.WorkerTask.worker_type == "builder").first()
    assert builder_task is not None
    assert builder_task.status == "queued"

    # A builder with nothing to build must not claim success or queue QA.
    process_worker_tasks(db)
    db.refresh(builder_task)
    assert builder_task.status == "completed"
    assert builder_task.outputs["build_success"] is False
    assert db.query(models.WorkerTask).filter(models.WorkerTask.worker_type == "qa").count() == 0


def test_qa_does_not_pass_without_an_inspection(db: Session):
    task = models.WorkerTask(
        worker_type="qa",
        task_name="qa_opportunity",
        priority=1,
        inputs={"build_success": True},
    )
    db.add(task)
    db.commit()

    process_worker_tasks(db)
    db.refresh(task)

    assert task.status == "completed"
    assert task.outputs["qa_passed"] is False
    assert db.query(models.WorkerTask).filter(models.WorkerTask.worker_type == "evolution").count() == 0


def test_worker_pipeline_deduplicates_pending_followups(db: Session):
    task = models.WorkerTask(
        worker_type="discovery",
        task_name="initial_discovery",
        priority=1,
        inputs={}
    )
    db.add(task)
    db.commit()

    process_worker_tasks(db)
    process_worker_tasks(db)
    process_worker_tasks(db)
    process_worker_tasks(db)
    process_worker_tasks(db)
    process_worker_tasks(db)

    queued = (
        db.query(models.WorkerTask)
        .filter(models.WorkerTask.status == "queued")
        .all()
    )
    pending_discovery = [
        t for t in queued
        if t.worker_type == "discovery" and t.task_name == "next_discovery_cycle"
    ]

    assert len(pending_discovery) <= 1
