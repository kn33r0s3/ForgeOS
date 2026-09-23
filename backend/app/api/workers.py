from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/workers", tags=["workers"])

@router.get("", response_model=list[schemas.WorkerTaskOut])
def list_workers(db: Session = Depends(get_db)):
    tasks = db.query(models.WorkerTask).order_by(models.WorkerTask.created_at.desc()).limit(100).all()
    return tasks

@router.post("", response_model=schemas.WorkerTaskOut)
def create_worker_task(task_in: schemas.WorkerTaskCreate, db: Session = Depends(get_db)):
    task = models.WorkerTask(
        worker_type=task_in.worker_type,
        task_name=task_in.task_name,
        status="queued",
        priority=task_in.priority,
        inputs=task_in.inputs
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
