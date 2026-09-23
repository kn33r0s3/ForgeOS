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

    # Process again - builder -> qa
    process_worker_tasks(db)
    db.refresh(builder_task)
    assert builder_task.status == "completed"

    qa_task = db.query(models.WorkerTask).filter(models.WorkerTask.worker_type == "qa").first()
    assert qa_task is not None
    assert qa_task.status == "queued"

    # Process again - qa -> evolution
    process_worker_tasks(db)
    db.refresh(qa_task)
    assert qa_task.status == "completed"

    evolution_task = db.query(models.WorkerTask).filter(models.WorkerTask.worker_type == "evolution").first()
    assert evolution_task is not None
    assert evolution_task.status == "queued"

    # Process again - evolution -> discovery (next loop)
    process_worker_tasks(db)
    db.refresh(evolution_task)
    assert evolution_task.status == "completed"
