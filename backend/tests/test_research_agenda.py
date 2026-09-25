from app import models
from app.services import research_planner, research_task_engine


def test_zero_result_question_stays_open_and_reuses_its_task(db):
    question = models.ResearchQuestion(
        question="What public evidence describes current market price?",
        status="planned",
    )
    db.add(question)
    db.flush()
    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        source="rss",
        query=question.question,
        objective=question.question,
    )

    research_task_engine.finish_task(db, task, signal_ids=[], evidence_ids=[])

    assert task.status == "needs_research"
    assert db.get(models.ResearchQuestion, question.id).status == "open"
    retried = research_planner.plan_tasks_for_open_questions(db)
    retried_ids = {row.id for row in retried}
    assert task.id in retried_ids
    assert db.get(models.ResearchTask, task.id).status == "planned"
    assert db.get(models.ResearchQuestion, question.id).status == "planned"
    assert db.query(models.ResearchQuestion).filter_by(question=question.question).count() == 1
    assert db.query(models.ResearchTask).filter_by(question_id=question.id).count() == len(retried_ids)


def test_failed_collection_without_evidence_does_not_close_the_question(db):
    question = models.ResearchQuestion(
        question="What public evidence describes insurance availability?",
        status="planned",
    )
    db.add(question)
    db.flush()
    task = research_task_engine.create_task(
        db,
        question_id=question.id,
        source="rss",
        query=question.question,
    )

    research_task_engine.fail_task(db, task, "No current source clearance")

    assert task.status == "failed"
    assert db.get(models.ResearchQuestion, question.id).status == "open"
